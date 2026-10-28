import { notFound } from "next/navigation";
import { Dashboard } from "@/components/dashboard";
import { views, type View } from "@/lib/navigation";
export default async function Page({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!Object.hasOwn(views, view)) notFound();
  return <Dashboard view={view as View} />;
}
