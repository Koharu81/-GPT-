import { boolean, float, index, int, mysqlEnum, mysqlTable, text, timestamp, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

export const trainingPairs = mysqlTable("trainingPairs", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  prompt: text("prompt").notNull(),
  response: text("response").notNull(),
  language: mysqlEnum("language", ["ko", "en", "mixed"]).default("mixed").notNull(),
  source: mysqlEnum("source", ["manual", "local_suggestion"]).default("manual").notNull(),
  status: mysqlEnum("status", ["draft", "approved"]).default("approved").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [index("trainingPairs_userId_idx").on(table.userId)]);

export const trainingRuns = mysqlTable("trainingRuns", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  status: mysqlEnum("status", ["queued", "running", "completed", "failed"]).default("queued").notNull(),
  requestedSteps: int("requestedSteps").notNull(),
  currentStep: int("currentStep").default(0).notNull(),
  progress: int("progress").default(0).notNull(),
  loss: float("loss"),
  note: text("note"),
  startedAt: timestamp("startedAt"),
  completedAt: timestamp("completedAt"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("trainingRuns_userId_idx").on(table.userId)]);

export const apiKeys = mysqlTable("apiKeys", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  name: varchar("name", { length: 80 }).notNull(),
  keyPrefix: varchar("keyPrefix", { length: 24 }).notNull(),
  keyHash: varchar("keyHash", { length: 64 }).notNull().unique(),
  state: mysqlEnum("state", ["active", "revoked"]).default("active").notNull(),
  lastUsedAt: timestamp("lastUsedAt"),
  revokedAt: timestamp("revokedAt"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("apiKeys_userId_idx").on(table.userId)]);

export const apiUsageLogs = mysqlTable("apiUsageLogs", {
  id: int("id").autoincrement().primaryKey(),
  apiKeyId: int("apiKeyId").notNull(),
  userId: int("userId").notNull(),
  endpoint: varchar("endpoint", { length: 120 }).notNull(),
  statusCode: int("statusCode").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  index("apiUsageLogs_apiKeyId_idx").on(table.apiKeyId),
  index("apiUsageLogs_userId_idx").on(table.userId),
]);

export const chatHistory = mysqlTable("chatHistory", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  role: mysqlEnum("role", ["user", "assistant"]).notNull(),
  content: text("content").notNull(),
  mode: varchar("mode", { length: 40 }),
  modelVersion: varchar("modelVersion", { length: 80 }),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("chatHistory_userId_createdAt_idx").on(table.userId, table.createdAt)]);

export const modelVersions = mysqlTable("modelVersions", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  version: varchar("version", { length: 80 }).notNull(),
  label: varchar("label", { length: 120 }).notNull(),
  description: text("description"),
  datasetRecords: int("datasetRecords").default(0).notNull(),
  requestedSteps: int("requestedSteps").default(0).notNull(),
  parameterCount: int("parameterCount").default(0).notNull(),
  trainLoss: float("trainLoss"),
  validationLoss: float("validationLoss"),
  artifactPath: varchar("artifactPath", { length: 500 }),
  isActive: boolean("isActive").default(false).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [index("modelVersions_userId_createdAt_idx").on(table.userId, table.createdAt)]);

export type TrainingPair = typeof trainingPairs.$inferSelect;
export type TrainingRun = typeof trainingRuns.$inferSelect;
export type ApiKey = typeof apiKeys.$inferSelect;
export type ChatHistoryEntry = typeof chatHistory.$inferSelect;
export type ModelVersion = typeof modelVersions.$inferSelect;
