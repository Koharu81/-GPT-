import type { Express } from "express";
import * as db from "./db";
import { replyFromLearningPairs } from "./studio/engine";

function extractApiKey(authorization: string | undefined, headerKey: string | undefined): string | null {
  if (headerKey?.trim()) return headerKey.trim();
  const token = authorization?.match(/^Bearer\s+(.+)$/i)?.[1]?.trim();
  return token || null;
}

export function registerPublicApi(app: Express) {
  app.post("/api/v1/chat/completions", async (req, res) => {
    const apiKey = extractApiKey(req.header("authorization"), req.header("x-api-key"));
    if (!apiKey) {
      return res.status(401).json({ error: { message: "API key is required.", type: "authentication_error" } });
    }
    const record = await db.findActiveApiKey(apiKey);
    if (!record) {
      return res.status(401).json({ error: { message: "Invalid or revoked API key.", type: "authentication_error" } });
    }
    const message = typeof req.body?.message === "string" ? req.body.message.trim() : "";
    if (!message || message.length > 4000) {
      await db.recordApiUsage(record.id, record.userId, 400, "/api/v1/chat/completions");
      return res.status(400).json({ error: { message: "message must be between 1 and 4000 characters.", type: "invalid_request_error" } });
    }
    const pairs = await db.listApprovedPairs(record.userId);
    const reply = replyFromLearningPairs(message, pairs);
    await db.touchApiKey(record.id);
    await db.recordApiUsage(record.id, record.userId, 200, "/api/v1/chat/completions");
    return res.json({ object: "chat.completion", model: "mirae-local-small", choices: [{ index: 0, message: { role: "assistant", content: reply } }] });
  });
}
