import { TRPCError } from "@trpc/server";
import { z } from "zod";
import * as db from "../db";
import { createLocalSuggestion, replyFromLearningPairs } from "../studio/engine";
import { protectedProcedure, adminProcedure, router } from "../_core/trpc";

const pairInput = z.object({
  prompt: z.string().trim().min(1).max(8000),
  response: z.string().trim().min(1).max(8000),
  language: z.enum(["ko", "en", "mixed"]).default("mixed"),
  status: z.enum(["draft", "approved"]).default("approved"),
});

export const studioRouter = router({
  chat: router({
    send: protectedProcedure
      .input(z.object({ message: z.string().trim().min(1).max(4000) }))
      .mutation(async ({ ctx, input }) => {
        const pairs = await db.listApprovedPairs(ctx.user.id);
        const reply = replyFromLearningPairs(input.message, pairs);
        const mode = "local-data" as const;
        await db.recordChatExchange({ userId: ctx.user.id, message: input.message, reply, mode });
        return { reply, mode };
      }),
    history: protectedProcedure
      .input(z.object({ query: z.string().trim().max(200).optional() }).optional())
      .query(({ ctx, input }) => input?.query ? db.searchChatHistory(ctx.user.id, input.query) : db.listChatHistory(ctx.user.id)),
    reuseHistory: protectedProcedure
      .input(z.object({ historyId: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const draft = await db.reuseHistoryAsTrainingDraft(ctx.user.id, input.historyId);
        if (!draft) throw new TRPCError({ code: "BAD_REQUEST", message: "재사용할 대화 쌍을 찾을 수 없습니다." });
        return { success: true, draft };
      }),
  }),
  trainingData: router({
    list: protectedProcedure.query(({ ctx }) => db.listTrainingPairs(ctx.user.id)),
    create: protectedProcedure.input(pairInput).mutation(async ({ ctx, input }) => {
      await db.createTrainingPair({ userId: ctx.user.id, ...input, source: "manual" });
      return { success: true } as const;
    }),
    update: protectedProcedure
      .input(pairInput.extend({ id: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const updated = await db.updateTrainingPair(ctx.user.id, input.id, input);
        if (!updated) throw new TRPCError({ code: "NOT_FOUND", message: "학습 데이터를 찾을 수 없습니다." });
        return { success: true } as const;
      }),
    remove: protectedProcedure
      .input(z.object({ id: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => {
        const removed = await db.deleteTrainingPair(ctx.user.id, input.id);
        if (!removed) throw new TRPCError({ code: "NOT_FOUND", message: "학습 데이터를 찾을 수 없습니다." });
        return { success: true } as const;
      }),
    exportJsonl: protectedProcedure.query(async ({ ctx }) => {
      const pairs = await db.listTrainingPairs(ctx.user.id);
      const jsonl = pairs
        .filter(pair => pair.status === "approved")
        .map(pair => JSON.stringify({
          id: `studio-${pair.id}`,
          source: pair.source,
          messages: [
            { role: "user", text: pair.prompt },
            { role: "assistant", text: pair.response },
          ],
        }))
        .join("\n");
      return { filename: "mirae-training-pairs.jsonl", jsonl };
    }),
    suggest: protectedProcedure
      .input(z.object({ seed: z.string().trim().min(1).max(2000) }))
      .mutation(({ input }) => ({ suggestions: createLocalSuggestion(input.seed) })),
  }),
  training: router({
    list: protectedProcedure.query(({ ctx }) => db.listTrainingRuns(ctx.user.id)),
    start: protectedProcedure
      .input(z.object({ steps: z.number().int().min(100).max(20000).default(1000) }))
      .mutation(async ({ ctx, input }) => {
        await db.createTrainingRun(ctx.user.id, input.steps);
        return {
          success: true,
          note: "학습 요청을 기록했습니다. Windows 로컬 런처가 이 요청을 실제 PyTorch 학습으로 실행합니다.",
        } as const;
      }),
  }),
  models: router({
    list: protectedProcedure.query(({ ctx }) => db.listModelVersions(ctx.user.id)),
    compare: protectedProcedure
      .input(z.object({ leftId: z.number().int().positive(), rightId: z.number().int().positive() }))
      .query(async ({ ctx, input }) => {
        const result = await db.compareModelVersions(ctx.user.id, input.leftId, input.rightId);
        if (!result) throw new TRPCError({ code: "NOT_FOUND", message: "비교할 모델 버전을 찾을 수 없습니다." });
        return result;
      }),
    comparePrompt: protectedProcedure
      .input(z.object({ leftId: z.number().int().positive(), rightId: z.number().int().positive(), message: z.string().trim().min(1).max(4000) }))
      .query(() => {
        throw new TRPCError({ code: "PRECONDITION_FAILED", message: "체크포인트별 실제 응답 비교는 Windows 로컬 Mirae AI Studio에서 제공됩니다." });
      }),
  }),
  apiKeys: router({
    list: protectedProcedure.query(({ ctx }) => db.listApiKeys(ctx.user.id)),
    create: protectedProcedure
      .input(z.object({ name: z.string().trim().min(2).max(80) }))
      .mutation(async ({ ctx, input }) => {
        const key = await db.createApiKey(ctx.user.id, input.name);
        return { key };
      }),
    revoke: protectedProcedure
      .input(z.object({ id: z.number().int().positive() }))
      .mutation(async ({ ctx, input }) => ({ success: await db.revokeApiKey(ctx.user.id, input.id) })),
  }),
  admin: router({
    overview: adminProcedure.query(() => db.getAdminOverview()),
  }),
});
