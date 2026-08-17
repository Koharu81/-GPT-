import { useAuth } from "@/_core/hooks/useAuth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { startLogin } from "@/const";
import { useIsMobile } from "@/hooks/useMobile";
import {
  Activity, Bot, Database, GitCompareArrows, History, KeyRound, LayoutDashboard, LogOut, Menu, MessageCircle,
  PanelLeft, Shield, Sparkles,
} from "lucide-react";
import { CSSProperties, useEffect, useRef, useState } from "react";
import { useLocation } from "wouter";
import { DashboardLayoutSkeleton } from "./DashboardLayoutSkeleton";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from "./ui/sidebar";

const baseMenuItems = [
  { icon: LayoutDashboard, label: "스튜디오", path: "/studio/chat" },
  { icon: MessageCircle, label: "대화", path: "/studio/chat" },
  { icon: History, label: "대화 기록", path: "/studio/history" },
  { icon: Database, label: "학습 데이터", path: "/studio/data" },
  { icon: Activity, label: "학습 모니터", path: "/studio/training" },
  { icon: GitCompareArrows, label: "모델 버전", path: "/studio/models" },
  { icon: KeyRound, label: "API 키", path: "/studio/keys" },
];

const SIDEBAR_WIDTH_KEY = "mirae-sidebar-width";
const DEFAULT_WIDTH = 268;

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarWidth, setSidebarWidth] = useState(() => Number(localStorage.getItem(SIDEBAR_WIDTH_KEY)) || DEFAULT_WIDTH);
  const { loading, user } = useAuth();
  useEffect(() => localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth)), [sidebarWidth]);

  if (loading) return <DashboardLayoutSkeleton />;
  if (!user) {
    return <div className="mirae-screen-grid min-h-screen bg-[#100722] text-white flex items-center justify-center p-6">
      <div className="max-w-md rounded-[2rem] border border-white/15 bg-white/[0.07] p-8 text-center backdrop-blur-xl shadow-2xl">
        <Sparkles className="mx-auto mb-5 size-9 text-teal-200" />
        <p className="text-xs font-semibold tracking-[0.22em] text-teal-100">MIRAE AI STUDIO</p>
        <h1 className="mt-4 text-3xl font-bold">나만의 AI를 만나려면<br />로그인이 필요해요.</h1>
        <p className="mt-4 text-sm leading-6 text-violet-100/75">대화, 학습 데이터, API 키는 당신의 스튜디오 안에서만 관리됩니다.</p>
        <Button onClick={() => startLogin()} className="mt-7 w-full rounded-full bg-teal-300 text-[#102323] hover:bg-teal-200">스튜디오로 들어가기</Button>
      </div>
    </div>;
  }
  return <SidebarProvider style={{ "--sidebar-width": `${sidebarWidth}px` } as CSSProperties}>
    <DashboardContent setSidebarWidth={setSidebarWidth}>{children}</DashboardContent>
  </SidebarProvider>;
}

function DashboardContent({ children, setSidebarWidth }: { children: React.ReactNode; setSidebarWidth: (width: number) => void }) {
  const { user, logout } = useAuth();
  const [location, setLocation] = useLocation();
  const { state, toggleSidebar } = useSidebar();
  const [resizing, setResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();
  const menuItems = user?.role === "admin" ? [...baseMenuItems, { icon: Shield, label: "관리자", path: "/studio/admin" }] : baseMenuItems;
  const active = menuItems.find(item => item.path === location)?.label ?? "Mirae AI Studio";

  useEffect(() => {
    const move = (event: MouseEvent) => {
      if (!resizing || state === "collapsed") return;
      const left = sidebarRef.current?.getBoundingClientRect().left ?? 0;
      const next = event.clientX - left;
      if (next >= 220 && next <= 360) setSidebarWidth(next);
    };
    const up = () => setResizing(false);
    if (resizing) { document.addEventListener("mousemove", move); document.addEventListener("mouseup", up); }
    return () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
  }, [resizing, setSidebarWidth, state]);

  return <>
    <div className="relative" ref={sidebarRef}>
      <Sidebar collapsible="icon" className="border-r border-white/10 bg-[#12072b] text-white">
        <SidebarHeader className="px-3 pt-5">
          <div className="flex items-center gap-3 rounded-2xl px-2 py-2">
            <button onClick={toggleSidebar} aria-label="메뉴 접기" className="grid size-9 place-items-center rounded-xl bg-white/10 hover:bg-white/15"><PanelLeft className="size-4" /></button>
            <div className="min-w-0 group-data-[collapsible=icon]:hidden"><p className="text-xs font-medium tracking-[0.18em] text-teal-200">MIRAE</p><p className="truncate text-sm font-bold">AI Studio</p></div>
          </div>
        </SidebarHeader>
        <SidebarContent className="mt-5">
          <SidebarMenu className="px-3">
            {menuItems.map(item => <SidebarMenuItem key={`${item.label}-${item.path}`}>
              <SidebarMenuButton isActive={location === item.path} tooltip={item.label} onClick={() => setLocation(item.path)} className="h-11 rounded-xl text-violet-100 hover:bg-white/10 hover:text-white data-[active=true]:bg-teal-300 data-[active=true]:text-[#102323]">
                <item.icon className="size-4" /><span>{item.label}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>)}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter className="p-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-2">
            <div className="flex items-center gap-2 px-1 py-1.5 group-data-[collapsible=icon]:justify-center"><Avatar className="size-8"><AvatarFallback className="bg-violet-400 text-xs text-white">{user?.name?.slice(0, 1).toUpperCase()}</AvatarFallback></Avatar><div className="min-w-0 group-data-[collapsible=icon]:hidden"><p className="truncate text-xs font-semibold">{user?.name ?? "Creator"}</p><p className="text-[10px] text-violet-200">{user?.role === "admin" ? "Studio admin" : "AI creator"}</p></div></div>
            <button onClick={logout} className="mt-1 flex w-full items-center gap-2 rounded-xl px-2 py-2 text-xs text-violet-200 hover:bg-white/10 hover:text-white group-data-[collapsible=icon]:justify-center"><LogOut className="size-3.5" /><span className="group-data-[collapsible=icon]:hidden">로그아웃</span></button>
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className={`absolute right-0 top-0 z-50 h-full w-1 cursor-col-resize hover:bg-teal-300/40 ${state === "collapsed" ? "hidden" : ""}`} onMouseDown={() => setResizing(true)} />
    </div>
    <SidebarInset className="min-h-screen bg-[#0c0619] text-white">
      {isMobile && <div className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-white/10 bg-[#12072b]/90 px-4 backdrop-blur"><SidebarTrigger className="text-white" /><span className="text-sm font-semibold">{active}</span></div>}
      <main className="min-h-screen p-4 md:p-7">{children}</main>
    </SidebarInset>
  </>;
}
