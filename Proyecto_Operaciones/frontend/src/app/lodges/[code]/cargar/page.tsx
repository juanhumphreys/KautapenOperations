/** Página: carga de movimientos. */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import MovementForm from "./MovementForm";

export const dynamic = "force-dynamic";

export default async function CargarPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const lodges = await api.listLodges();
  const lodge = lodges.find((l) => l.code === code);
  if (!lodge) notFound();

  const accounts = await api.accounts(code);

  return (
    <>
      <PageHeader
        title="Cargar movimiento"
        subtitle="Registrar un gasto, ingreso o asiento contable."
      />
      <div className="px-8 py-6">
        <div className="mx-auto max-w-4xl">
          <MovementForm
            lodgeCode={lodge.code}
            currency={lodge.currency}
            accounts={accounts}
          />
        </div>
      </div>
    </>
  );
}
