import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { trpc } from "@/lib/trpc";
import { History, Search, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export default function ConversationHistory() {
  const [query, setQuery] = useState("");
  const history = trpc.studio.chat.history.useQuery(query.trim() ? { query: query.trim() } : undefined);
  const utils = trpc.useUtils();
  const reuse = trpc.studio.chat.reuseHistory.useMutation({ onSuccess: () => { toast.success("검토용 학습 초안으로 가져왔어요."); utils.studio.trainingData.list.invalidate(); } });
  return <section className="mx-auto max-w-6xl space-y-6"><div className="flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="mirae-kicker">MEMORY TRACE</p><h1 className="mirae-page-title">대화의 흔적을<br />다시 찾아보세요.</h1></div><Badge className="w-fit border-0 bg-teal-300/15 px-3 py-1.5 text-teal-100"><History className="mr-1.5 size-3.5" />내 PC와 스튜디오 기록</Badge></div><div className="mirae-panel"><div className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-teal-200" /><Input value={query} onChange={event => setQuery(event.target.value)} placeholder="대화 속 단어를 검색하세요" className="border-white/10 bg-black/15 pl-10 text-white placeholder:text-violet-200/45" /></div><p className="mt-3 text-xs text-violet-200/70">사용자 문장은 버튼 하나로 검토용 학습 초안에 다시 담을 수 있습니다.</p></div><div className="mirae-panel overflow-hidden p-0"><div className="border-b border-white/10 px-5 py-4"><h2>{query ? `“${query}” 검색 결과` : "최근 대화"}</h2></div><div className="divide-y divide-white/8">{history.isLoading ? <p className="p-6 text-sm text-violet-200">기억을 불러오는 중...</p> : history.data?.length ? history.data.map(item => <article key={item.id} className="p-5"><div className="flex items-center justify-between gap-3"><Badge className={item.role === "user" ? "border-0 bg-teal-200/15 text-teal-100" : "border-0 bg-violet-300/15 text-violet-100"}>{item.role === "user" ? "나" : "AI"}</Badge><span className="text-xs text-violet-200/60">{new Date(item.createdAt).toLocaleString()}</span></div><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-white">{item.content}</p>{item.modelVersion && <p className="mt-2 text-xs text-teal-200/70">{item.modelVersion} · {item.mode ?? "conversation"}</p>}{item.role === "user" && <Button variant="outline" size="sm" onClick={() => reuse.mutate({ historyId: item.id })} disabled={reuse.isPending} className="mt-4 border-teal-200/25 bg-teal-200/5 text-teal-100 hover:bg-teal-200/10 hover:text-white"><Sparkles className="mr-1.5 size-3.5" />학습 초안으로 재사용</Button>}</article>) : <p className="p-8 text-sm text-violet-200">아직 저장된 대화가 없어요. 대화 패널에서 첫 이야기를 시작해 보세요.</p>}</div></div></section>;
}
