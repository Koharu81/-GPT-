import { describe, expect, it } from "vitest";
import { createLocalSuggestion, replyFromLearningPairs } from "./engine";

describe("replyFromLearningPairs", () => {
  it("returns the closest approved learning-pair response", () => {
    const reply = replyFromLearningPairs("How do I say thank you?", [
      { prompt: "How do I say thank you in Korean?", response: "고맙습니다 또는 감사합니다라고 말할 수 있어요." },
      { prompt: "What is a loop?", response: "A loop repeats work." },
    ]);
    expect(reply).toBe("고맙습니다 또는 감사합니다라고 말할 수 있어요.");
  });

  it("uses an honest bilingual fallback when no learned pair matches", () => {
    const reply = replyFromLearningPairs("Tell me about galaxies", []);
    expect(reply).toContain("작은 AI");
    expect(reply).toContain("I am still learning");
  });
});

describe("createLocalSuggestion", () => {
  it("creates editable Korean and English-oriented training pair drafts", () => {
    const suggestions = createLocalSuggestion("오늘 너무 지쳤어");
    expect(suggestions).toHaveLength(2);
    expect(suggestions[0]?.prompt).toBe("오늘 너무 지쳤어");
    expect(suggestions[1]?.response).toContain("Thank you");
  });
});
