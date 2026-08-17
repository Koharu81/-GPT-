export type LearningPairLike = {
  prompt: string;
  response: string;
};

function normalizedTokens(text: string): string[] {
  return text
    .toLocaleLowerCase()
    .replace(/[^A-Za-z0-9가-힣\s]/g, " ")
    .split(/\s+/)
    .filter(token => token.length > 1);
}

/**
 * This is a transparent local fallback, not an external LLM. The Windows
 * package replaces this path with the directly trained small model once a
 * checkpoint is available.
 */
export function replyFromLearningPairs(message: string, pairs: LearningPairLike[]): string {
  const queryTokens = new Set(normalizedTokens(message));
  let best: LearningPairLike | undefined;
  let bestScore = 0;

  for (const pair of pairs) {
    const score = normalizedTokens(pair.prompt).reduce(
      (total, token) => total + (queryTokens.has(token) ? 1 : 0),
      0,
    );
    if (score > bestScore) {
      best = pair;
      bestScore = score;
    }
  }

  if (best && bestScore > 0) return best.response;
  return "아직은 당신이 만든 대화 데이터에서 배우는 작은 AI예요. 같은 주제의 대화 쌍을 추가해 주시면 더 자연스러운 답을 만들 수 있어요.\n\nI am still learning from the conversation pairs you create. Add a related pair and train again so I can answer more naturally.";
}

export function createLocalSuggestion(seed: string): { prompt: string; response: string }[] {
  const cleanSeed = seed.trim();
  if (!cleanSeed) return [];
  return [
    {
      prompt: cleanSeed,
      response: "그 이야기를 꺼내 준 것만으로도 이미 중요한 시작이에요. 지금 느끼는 마음을 한 문장 더 들려주실래요?",
    },
    {
      prompt: `Could you respond with care? ${cleanSeed}`,
      response: "Thank you for sharing that. We can take this one small step at a time, in Korean, English, or both.",
    },
  ];
}
