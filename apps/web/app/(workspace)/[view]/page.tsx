import { notFound } from "next/navigation";
import { views } from "@/lib/navigation";
export default async function Page({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!Object.hasOwn(views, view)) notFound();
  return null;
}
