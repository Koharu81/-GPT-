import { AIChatBox, type Message } from "@/components/AIChatBox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { trpc } from "@/lib/trpc";
import { BrainCircuit, Database, Sparkles } from "lucide-react";
import { useState } from "react";

export default function StudioChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const chat = trpc.studio.chat.send.useMutation({ onSuccess: data => setMessages(current => [...current, { role: "assistant", content: data.reply }]) });
  const send = (content: string) => { setMessages(current => [...current, { role: "user", content }]); chat.mutate({ message: content }); };
  return <section className="mx-auto max-w-6xl space-y-5">
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="mirae-kicker">CONVERSATION GARDEN</p><h1 className="mirae-page-title">오늘, 내 AI에게<br />무엇을 가르칠까요?</h1></div><Badge className="w-fit border-0 bg-teal-300/15 px-3 py-1.5 text-teal-200"><Database className="mr-1.5 size-3.5" />내 데이터 기반 · 외부 API 없음</Badge></div>
    <div className="grid gap-5 lg:grid-cols-[1fr_300px]"><AIChatBox messages={messages} onSendMessage={send} isLoading={chat.isPending} height="min(66vh,700px)" placeholder="Korean, English, or both..." emptyStateMessage="첫 문장을 건네며 당신만의 AI를 깨워보세요." suggestedPrompts={["오늘 마음이 조금 복잡해.", "Help me plan a small game project.", "한국어와 English를 섞어서 답해 줘."]} className="border-white/10 bg-white/[0.06] shadow-2xl shadow-violet-950/40" />
      <aside className="space-y-4"><div className="mirae-panel"><Sparkles className="size-5 text-teal-200" /><h2>작은 AI, 큰 대화</h2><p>현재 응답은 승인한 학습 대화 쌍에서 가장 가까운 맥락을 찾아 만듭니다. 데이터를 더할수록 당신의 언어에 가까워집니다.</p></div><div className="mirae-panel"><BrainCircuit className="size-5 text-violet-200" /><h2>다음 한 걸음</h2><p>좋았던 대화는 학습 데이터 페이지에 옮겨 JSONL로 내보내고, Windows 로컬 런처에서 직접 학습하세요.</p></div><Button variant="outline" className="w-full border-white/15 bg-white/[0.04] text-white hover:bg-white/10 hover:text-white" onClick={() => setMessages([])}>대화 비우기</Button></aside>
    </div>
  </section>;
}
