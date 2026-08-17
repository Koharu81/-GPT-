import { and, desc, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { apiKeys, apiUsageLogs, InsertUser, trainingPairs, trainingRuns, users } from "../drizzle/schema";
import { ENV } from './_core/env';
import { createRawApiKey, hashApiKey } from "./studio/security";

let _db: ReturnType<typeof drizzle> | null = null;

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

async function requireDb() {
  const db = await getDb();
  if (!db) throw new Error("데이터베이스에 연결할 수 없습니다.");
  return db;
}

export async function listTrainingPairs(userId: number) {
  const db = await requireDb();
  return db.select().from(trainingPairs).where(eq(trainingPairs.userId, userId)).orderBy(desc(trainingPairs.updatedAt));
}

export async function listApprovedPairs(userId: number) {
  const db = await requireDb();
  return db.select({ prompt: trainingPairs.prompt, response: trainingPairs.response })
    .from(trainingPairs)
    .where(and(eq(trainingPairs.userId, userId), eq(trainingPairs.status, "approved")));
}

export async function createTrainingPair(input: {
  userId: number;
  prompt: string;
  response: string;
  language: "ko" | "en" | "mixed";
  status: "draft" | "approved";
  source: "manual" | "local_suggestion";
}) {
  const db = await requireDb();
  await db.insert(trainingPairs).values(input);
}

export async function updateTrainingPair(
  userId: number,
  id: number,
  input: { prompt: string; response: string; language: "ko" | "en" | "mixed"; status: "draft" | "approved" },
) {
  const db = await requireDb();
  const found = await db.select({ id: trainingPairs.id }).from(trainingPairs)
    .where(and(eq(trainingPairs.id, id), eq(trainingPairs.userId, userId))).limit(1);
  if (!found.length) return false;
  await db.update(trainingPairs).set(input).where(eq(trainingPairs.id, id));
  return true;
}

export async function deleteTrainingPair(userId: number, id: number) {
  const db = await requireDb();
  const found = await db.select({ id: trainingPairs.id }).from(trainingPairs)
    .where(and(eq(trainingPairs.id, id), eq(trainingPairs.userId, userId))).limit(1);
  if (!found.length) return false;
  await db.delete(trainingPairs).where(eq(trainingPairs.id, id));
  return true;
}

export async function listTrainingRuns(userId: number) {
  const db = await requireDb();
  return db.select().from(trainingRuns).where(eq(trainingRuns.userId, userId)).orderBy(desc(trainingRuns.createdAt));
}

export async function createTrainingRun(userId: number, requestedSteps: number) {
  const db = await requireDb();
  await db.insert(trainingRuns).values({
    userId,
    requestedSteps,
    status: "queued",
    note: "Windows 로컬 런처가 실제 학습을 시작할 때까지 대기 중입니다.",
  });
}

export async function createApiKey(userId: number, name: string) {
  const db = await requireDb();
  const raw = createRawApiKey();
  await db.insert(apiKeys).values({
    userId,
    name,
    keyPrefix: raw.slice(0, 18),
    keyHash: hashApiKey(raw),
    state: "active",
  });
  return raw;
}

export async function listApiKeys(userId: number) {
  const db = await requireDb();
  return db.select({
    id: apiKeys.id,
    name: apiKeys.name,
    keyPrefix: apiKeys.keyPrefix,
    state: apiKeys.state,
    lastUsedAt: apiKeys.lastUsedAt,
    revokedAt: apiKeys.revokedAt,
    createdAt: apiKeys.createdAt,
  }).from(apiKeys).where(eq(apiKeys.userId, userId)).orderBy(desc(apiKeys.createdAt));
}

export async function revokeApiKey(userId: number, id: number) {
  const db = await requireDb();
  const found = await db.select({ id: apiKeys.id }).from(apiKeys)
    .where(and(eq(apiKeys.id, id), eq(apiKeys.userId, userId))).limit(1);
  if (!found.length) return false;
  await db.update(apiKeys).set({ state: "revoked", revokedAt: new Date() }).where(eq(apiKeys.id, id));
  return true;
}

export async function findActiveApiKey(rawKey: string) {
  const db = await requireDb();
  const rows = await db.select().from(apiKeys)
    .where(and(eq(apiKeys.keyHash, hashApiKey(rawKey)), eq(apiKeys.state, "active"))).limit(1);
  return rows[0];
}

export async function touchApiKey(id: number) {
  const db = await requireDb();
  await db.update(apiKeys).set({ lastUsedAt: new Date() }).where(eq(apiKeys.id, id));
}

export async function recordApiUsage(apiKeyId: number, userId: number, statusCode: number, endpoint: string) {
  const db = await requireDb();
  await db.insert(apiUsageLogs).values({ apiKeyId, userId, statusCode, endpoint });
}

export async function getAdminOverview() {
  const db = await requireDb();
  const [allUsers, allKeys, allUsage, allRuns] = await Promise.all([
    db.select({ id: users.id, openId: users.openId, name: users.name, email: users.email, role: users.role, createdAt: users.createdAt, lastSignedIn: users.lastSignedIn }).from(users).orderBy(desc(users.lastSignedIn)),
    db.select({ id: apiKeys.id, userId: apiKeys.userId, state: apiKeys.state }).from(apiKeys),
    db.select({ id: apiUsageLogs.id, statusCode: apiUsageLogs.statusCode, createdAt: apiUsageLogs.createdAt }).from(apiUsageLogs).orderBy(desc(apiUsageLogs.createdAt)).limit(20),
    db.select({ id: trainingRuns.id, status: trainingRuns.status }).from(trainingRuns),
  ]);
  return {
    userCount: allUsers.length,
    activeKeyCount: allKeys.filter(key => key.state === "active").length,
    requestCount: allUsage.length,
    runningTrainingCount: allRuns.filter(run => run.status === "running" || run.status === "queued").length,
    users: allUsers,
    recentUsage: allUsage,
  };
}
