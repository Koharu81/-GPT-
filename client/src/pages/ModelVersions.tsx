import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { trpc } from "@/lib/trpc";
import { GitCompareArrows, Layers3, MonitorSmartphone, TrendingDown } from "lucide-react";
import { useEffect, useState } from "react";

const metric = (value: number | null) => value === null ? "측정 대기" : value.toFixed(4);

export default function ModelVersions() {
  const versions = trpc.studio.models.list.useQuery();
  const [leftId, setLeftId] = useState<string>("");
  const [rightId, setRightId] = useState<string>("");
  useEffect(() => {
    if (versions.data && versions.data.length > 1) {
      setLeftId(String(versions.data[1].id));
      setRightId(String(versions.data[0].id));
    }
  }, [versions.data]);
  const comparison = trpc.studio.models.compare.useQuery(
    { leftId: Number(leftId), rightId: Number(rightId) },
    { enabled: Boolean(leftId && rightId && leftId !== rightId) },
  );

  return <section className="mx-auto max-w-6xl space-y-6">
    <div><p className="mirae-kicker">MODEL ATLAS</p><h1 className="mirae-page-title">성장한 모델을<br />나란히 살펴보세요.</h1></div>
    <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
      <div className="mirae-panel"><Layers3 className="size-5 text-teal-200" /><h2 className="mt-3">저장된 모델</h2><p>새 학습이 끝날 때마다 데이터 수, 손실, 스텝, 체크포인트를 기록합니다.</p><div className="mt-5 space-y-3">{versions.data?.length ? versions.data.map(version => <div key={version.id} className="rounded-xl border border-white/10 bg-black/15 p-3"><div className="flex items-center justify-between"><span className="font-semibold">{version.label}</span>{version.isActive && <Badge className="border-0 bg-teal-200/15 text-teal-100">현재</Badge>}</div><p className="mt-1 text-xs text-violet-200">{version.version} · {version.datasetRecords} pairs · {version.requestedSteps.toLocaleString()} steps</p></div>) : <p className="text-sm text-violet-200">아직 저장된 모델 버전이 없습니다. 로컬 런처에서 학습을 완료하면 이곳에 기록됩니다.</p>}</div></div>
      <div className="mirae-panel"><div className="flex items-center gap-2"><GitCompareArrows className="size-5 text-violet-200" /><h2>버전 비교</h2></div>{versions.data && versions.data.length > 1 ? <><div className="mt-5 grid gap-3 sm:grid-cols-2"><Select value={leftId} onValueChange={setLeftId}><SelectTrigger className="border-white/10 bg-black/15 text-white"><SelectValue placeholder="기준 모델" /></SelectTrigger><SelectContent>{versions.data.map(version => <SelectItem key={version.id} value={String(version.id)}>{version.label}</SelectItem>)}</SelectContent></Select><Select value={rightId} onValueChange={setRightId}><SelectTrigger className="border-white/10 bg-black/15 text-white"><SelectValue placeholder="비교 모델" /></SelectTrigger><SelectContent>{versions.data.map(version => <SelectItem key={version.id} value={String(version.id)}>{version.label}</SelectItem>)}</SelectContent></Select></div>{comparison.data && <div className="mt-5 grid gap-3 sm:grid-cols-2"><Metric label="학습 데이터" left={`${comparison.data.left.datasetRecords} pairs`} right={`${comparison.data.right.datasetRecords} pairs`} delta={`+${comparison.data.deltas.datasetRecords}`} /><Metric label="학습 손실" left={metric(comparison.data.left.trainLoss)} right={metric(comparison.data.right.trainLoss)} delta={comparison.data.deltas.trainLoss <= 0 ? `${comparison.data.deltas.trainLoss.toFixed(4)} ↓` : `+${comparison.data.deltas.trainLoss.toFixed(4)}`} /><Metric label="검증 손실" left={metric(comparison.data.left.validationLoss)} right={metric(comparison.data.right.validationLoss)} delta={comparison.data.deltas.validationLoss <= 0 ? `${comparison.data.deltas.validationLoss.toFixed(4)} ↓` : `+${comparison.data.deltas.validationLoss.toFixed(4)}`} /><Metric label="학습 스텝" left={comparison.data.left.requestedSteps.toLocaleString()} right={comparison.data.right.requestedSteps.toLocaleString()} delta={`+${comparison.data.deltas.requestedSteps.toLocaleString()}`} /></div>}<div className="mt-5 flex gap-3 rounded-xl border border-teal-200/15 bg-teal-200/[0.045] p-4"><MonitorSmartphone className="mt-0.5 size-4 shrink-0 text-teal-200" /><p className="text-sm leading-6 text-violet-100/85"><strong className="text-teal-100">실제 응답 A/B 비교는 Windows 로컬 패널에서 제공됩니다.</strong><br />로컬 런타임은 각 체크포인트를 직접 불러와 같은 프롬프트의 답을 나란히 생성합니다. 이 관리형 패널은 학습 기록·손실·데이터 규모 비교에 집중합니다.</p></div></> : <p className="mt-5 text-sm leading-6 text-violet-200">비교하려면 두 개 이상의 학습 모델 버전이 필요합니다. 다음 학습을 마친 뒤 다시 확인해 보세요.</p>}</div>
    </div>
  </section>;
}

function Metric({ label, left, right, delta }: { label: string; left: string; right: string; delta: string }) {
  return <div className="rounded-xl bg-white/[0.045] p-4"><div className="flex items-center gap-2 text-xs text-violet-200"><TrendingDown className="size-3.5 text-teal-200" />{label}</div><div className="mt-3 flex items-end justify-between gap-2"><div><p className="text-xs text-violet-200/60">기준 {left}</p><p className="text-lg font-bold text-white">비교 {right}</p></div><Badge className="border-0 bg-teal-200/10 text-teal-100">{delta}</Badge></div></div>;
}
