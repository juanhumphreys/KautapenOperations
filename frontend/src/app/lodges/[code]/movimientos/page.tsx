/** Lista de movimientos cargados. */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function MovimientosPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const lodges = await api.listLodges();
  const lodge = lodges.find((l) => l.code === code);
  if (!lodge) notFound();

  const data = await api.listMovements(code, 1, 50);

  return (
    <>
      <PageHeader
        title="Movimientos cargados"
        subtitle={`${data.total.toLocaleString()} en total · mostrando los últimos ${data.items.length}`}
      />
      <div className="px-8 py-6">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <Th>Fecha</Th>
                  <Th>Cuenta</Th>
                  <Th>Concepto</Th>
                  <Th>Subdiario</Th>
                  <Th>Proveedor</Th>
                  <Th className="text-right">Monto local</Th>
                  <Th className="text-right">Monto USD</Th>
                  <Th>Origen</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-12 text-center text-sm text-slate-600"
                    >
                      Sin movimientos cargados todavía.
                    </td>
                  </tr>
                ) : (
                  data.items.map((m) => (
                    <tr
                      key={m.id}
                      className="border-t border-slate-200 hover:bg-slate-50"
                    >
                      <Td className="text-slate-900">{m.date}</Td>
                      <Td className="font-medium text-slate-900">
                        {m.account_code}
                      </Td>
                      <Td className="max-w-xs truncate text-slate-700">
                        {m.concept ?? "—"}
                      </Td>
                      <Td className="text-slate-700">{m.subdiario ?? "—"}</Td>
                      <Td className="text-slate-700">{m.proveedor ?? "—"}</Td>
                      <Td className="text-right tabular-nums text-slate-900">
                        {Number(m.amount_local).toLocaleString("en-US", {
                          maximumFractionDigits: 2,
                        })}{" "}
                        <span className="text-xs text-slate-600">
                          {m.currency}
                        </span>
                      </Td>
                      <Td className="text-right font-medium tabular-nums text-slate-900">
                        $
                        {Number(m.amount_usd).toLocaleString("en-US", {
                          maximumFractionDigits: 2,
                        })}
                      </Td>
                      <Td>
                        <span
                          className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                            m.source === "web"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-200 text-slate-800"
                          }`}
                        >
                          {m.source}
                        </span>
                      </Td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-700 ${className}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-4 py-3 ${className}`}>{children}</td>;
}
