/** Layout del lodge: sidebar fijo izquierda + main full-width.
 * El sidebar se queda visible siempre; el main scrollea.
 */
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";

export default async function LodgeLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const lodges = await api.listLodges();
  const lodge = lodges.find((l) => l.code === code);
  if (!lodge) notFound();

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar current={lodge} lodges={lodges} />
      <main className="ml-64 min-h-screen">{children}</main>
    </div>
  );
}
