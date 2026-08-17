export type ChatCompletion = {
  object: "chat.completion";
  model: string;
  mode: string;
  choices: Array<{ index: number; message: { role: "assistant"; content: string } }>;
};

export class MiraeApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly body?: unknown) {
    super(message);
    this.name = "MiraeApiError";
  }
}

export type MiraeClientOptions = {
  apiKey: string;
  baseUrl?: string;
  fetcher?: typeof fetch;
};

/** Dependency-free client for the locally running Mirae AI Studio API. */
export class MiraeClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(options: MiraeClientOptions) {
    if (!options.apiKey.trim()) throw new Error("apiKey is required.");
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    this.fetcher = options.fetcher ?? fetch;
  }

  async chat(message: string): Promise<ChatCompletion> {
    if (!message.trim()) throw new Error("message is required.");
    const response = await this.fetcher(`${this.baseUrl}/api/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({ message }),
    });
    const body: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      const detail = typeof body === "object" && body && "detail" in body ? String(body.detail) : response.statusText;
      throw new MiraeApiError(detail || "Mirae API request failed.", response.status, body);
    }
    return body as ChatCompletion;
  }

  async reply(message: string): Promise<string> {
    const completion = await this.chat(message);
    return completion.choices[0]?.message.content ?? "";
  }
}
