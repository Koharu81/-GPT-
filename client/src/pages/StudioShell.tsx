import DashboardLayout from "@/components/DashboardLayout";

export default function StudioShell({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
