import { createHash, randomBytes } from "node:crypto";

export function hashApiKey(key: string) {
  return createHash("sha256").update(key).digest("hex");
}

export function createRawApiKey() {
  return `mirae_${randomBytes(24).toString("base64url")}`;
}
