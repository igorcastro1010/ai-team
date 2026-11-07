import { Dashboard } from "@/components/dashboard";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <><Dashboard />{children}</>;
}
