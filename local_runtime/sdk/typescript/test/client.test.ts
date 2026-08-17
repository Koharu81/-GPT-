import { describe, expect, it } from "vitest";
import { MiraeApiError, MiraeClient } from "../src/index.js";

describe("MiraeClient", () => {
  it("sends a bearer key and returns assistant text", async () => {
    const calls: RequestInit[] = [];
    const client = new MiraeClient({ apiKey: "mirae_test", fetcher: async (_url, init) => {
      calls.push(init ?? {});
      return new Response(JSON.stringify({ object: "chat.completion", model: "mirae-v2", mode: "local-data", choices: [{ index: 0, message: { role: "assistant", content: "반가워요." } }] }), { status: 200 });
    } });
    await expect(client.reply("안녕")).resolves.toBe("반가워요.");
    expect(calls[0]?.headers).toMatchObject({ Authorization: "Bearer mirae_test" });
  });

  it("exposes API errors with status", async () => {
    const client = new MiraeClient({ apiKey: "bad", fetcher: async () => new Response(JSON.stringify({ detail: "Invalid API key." }), { status: 401, statusText: "Unauthorized" }) });
    await expect(client.chat("hello")).rejects.toBeInstanceOf(MiraeApiError);
  });
});
