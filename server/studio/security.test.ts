import { describe, expect, it } from "vitest";
import { createRawApiKey, hashApiKey } from "./security";

describe("API key security helpers", () => {
  it("creates a random key and stores a stable non-reversible hash representation", () => {
    const key = createRawApiKey();
    expect(key).toMatch(/^mirae_[A-Za-z0-9_-]+$/);
    expect(key.length).toBeGreaterThan(30);
    const hash = hashApiKey(key);
    expect(hash).toMatch(/^[a-f0-9]{64}$/);
    expect(hash).toBe(hashApiKey(key));
    expect(hash).not.toContain(key);
  });
});
