import { useAuth } from "@/_core/hooks/useAuth";
import { Badge } from "@/components/ui/badge";
import { trpc } from "@/lib/trpc";
import { BarChart3, KeyRound, ShieldAlert, Users } from "lucide-react";

export default function Admin() {
  const { user, loading } = useAuth(); const overview = trpc.studio.admin.overview.useQuery(undefined, { enabled: user?.role === "admin" });
  if (loading) return null;
  if (user?.role !== "admin") return <section className="mx-auto max-w-3xl py-20 text-center"><ShieldAlert className="mx-auto size-10 text-violet-300" /><h1 className="mt-5 text-3xl font-bold">관리자 전용 공간입니다.</h1><p className="mt-3 text-violet-200">이 페이지는 스튜디오 관리 권한이 있는 사용자만 볼 수 있어요.</p></section>;
  const stats = [{ icon: Users, label: "전체 사용자", value: overview.data?.userCount ?? 0 }, { icon: KeyRound, label: "활성 API 키", value: overview.data?.activeKeyCount ?? 0 }, { icon: BarChart3, label: "최근 호출", value: overview.data?.requestCount ?? 0 }];
  return <section className="mx-auto max-w-6xl space-y-6"><div><p className="mirae-kicker">STUDIO STEWARDSHIP</p><h1 className="mirae-page-title">전체 스튜디오의<br />온도를 살핍니다.</h1></div><div className="grid gap-4 md:grid-cols-3">{stats.map(stat => <div key={stat.label} className="mirae-panel"><stat.icon className="size-5 text-teal-200" /><p className="mt-5 text-sm text-violet-200">{stat.label}</p><p className="mt-1 text-4xl font-bold">{stat.value.toLocaleString()}</p></div>)}</div><div className="mirae-panel overflow-hidden p-0"><div className="border-b border-white/10 px-5 py-4"><h2>사용자 현황</h2></div><div className="divide-y divide-white/8">{overview.data?.users.map(member => <div key={member.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-medium">{member.name ?? "Unnamed creator"}</p><p className="mt-1 text-xs text-violet-200">{member.email ?? member.openId}</p></div><Badge className="border-0 bg-violet-300/15 text-violet-100">{member.role}</Badge></div>)}</div></div></section>;
}
