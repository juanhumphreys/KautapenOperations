/** Detalle de una cuenta: mini-dash con totales + breakdown mensual + tabla
 * con todos los movimientos de la cuenta (paginada).
 */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

type SearchParams = { page?: string };

export default async function CuentaDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ code: string; accountCode: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { code, accountCode } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page ?? 1));

  let stats;
  try {
    stats = await api.accountDetail(code, accountCode);
  } catch {
    notFound();
  }

  const movs = await api.listMovements(code, {
    page,
    pageSize: PAGE_SIZE,
    account: accountCode,
  });

  const totalPages = Math.max(1, Math.ceil(movs.total / PAGE_SIZE));
  const monthsCount = stats.monthly.length;
  const avgPerMonth = monthsCount > 0 ? stats.total_usd / monthsCount : 0;
  const maxMonthly = stats.monthly.reduce(
    (max, m) => Math.max(max, Math.abs(m.total_usd)),
    0,
  );

  return (
    <>
      <PageHeader
        title={`${stats.account.code} · ${stats.account.name}`}
        subtitle={
          <>
            <Link
              href={`/lodges/${code}/rubros`}
              className="text-slate-700 hover:underline"
            >
              ← Rubros
            </Link>
            {stats.account.rubro_secundario && (
              <span className="ml-2 text-slate-700">
                · {stats.account.rubro_secundario}
              </span>
            )}
            {stats.account.is_income && (
              <span className="ml-2 inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-900">
                ingreso
              </span>
            )}
          </>
        }
      />
      <main id="main" className="px-8 py-6">
        {/* Mini-dash */}
        <section
          aria-label="Resumen de la cuenta"
          className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4"
        >
          <Kpi
            label="Total USD"
            value={fmtUsd(stats.total_usd)}
            sub={stats.account.is_income ? "ingreso acumulado" : "gasto acumulado"}
          />
          <Kpi
            label="Movimientos"
            value={stats.n_movements.toLocaleString()}
            sub={
              monthsCount > 0 ? `en ${monthsCount} mes${monthsCount > 1 ? "es" : ""}` : ""
            }
          />
          <Kpi
            label="Promedio mensual"
            value={fmtUsd(avgPerMonth)}
            sub={stats.first_date ? `desde ${stats.first_date}` : ""}
          />
          <Kpi
            label="Último movimiento"
            value={stats.last_date ?? "—"}
            sub={
              stats.first_date && stats.last_date
                ? `primero ${stats.first_date}`
                : ""
            }
          />
        </section>

        {/* Mini bar-chart mensual */}
        {stats.monthly.length > 0 && (
          <section className="mb-8">
            <h2 className="mb-3 text-base font-semibold text-slate-900">
              Gasto por mes
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <ul role="list" className="space-y-1.5">
                {stats.monthly.map((m) => {
                  const widthPct =
                    maxMonthly > 0 ? (Math.abs(m.total_usd) / maxMonthly) * 100 : 0;
                  return (
                    <li
                      key={m.month_key}
                      className="flex items-center gap-3 py-1"
                      title={`${m.n_movements} movimientos`}
                    >
                      <div className="w-20 flex-shrink-0 text-sm font-medium text-slate-900 tabular-nums">
                        {m.month_key}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="relative h-5 overflow-hidden rounded bg-slate-100">
                          <div
                            className={`absolute inset-y-0 left-0 rounded transition-all ${
                              stats.account.is_income
                                ? "bg-emerald-500"
                                : "bg-slate-700"
                            }`}
                            style={{ width: `${Math.max(widthPct, 1)}%` }}
                          />
                        </div>
                      </div>
                      <div className="w-28 flex-shrink-0 text-right text-sm font-semibold tabular-nums text-slate-900">
                        {fmtUsd(m.total_usd)}
                      </div>
                      <div className="w-16 flex-shrink-0 text-right text-xs tabular-nums text-slate-700">
                        {m.n_movements} mov
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>
        )}

        {/* Tabla de movimientos */}
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-base font-semibold text-slate-900">
              Movimientos analizados
            </h2>
            <span className="text-xs text-slate-700">
              {movs.total.toLocaleString()} en total · página {page} de{" "}
              {totalPages}
            </span>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <Th>Fecha</Th>
                    <Th>Concepto</Th>
                    <Th>Subdiario</Th>
                    <Th>Proveedor</Th>
                    <Th className="text-right">Monto local</Th>
                    <Th className="text-right">Monto USD</Th>
                  </tr>
                </thead>
                <tbody>
                  {movs.items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-12 text-center text-sm text-slate-700"
                      >
                        Sin movimientos cargados para esta cuenta.
                      </td>
                    </tr>
                  ) : (
                    movs.items.map((m) => (
                      <tr
                        key={m.id}
                        className="border-t border-slate-200 hover:bg-slate-50"
                      >
                        <Td className="text-slate-900 tabular-nums">{m.date}</Td>
                        <Td className="max-w-xs truncate text-slate-700">
                          {m.concept ?? "—"}
                        </Td>
                        <Td className="text-slate-700">{m.subdiario ?? "—"}</Td>
                        <Td className="text-slate-700">{m.proveedor ?? "—"}</Td>
                        <Td className="text-right tabular-nums text-slate-900">
                          {Number(m.amount_local).toLocaleString("en-US", {
                            maximumFractionDigits: 2,
                          })}{" "}
                          <span className="text-xs text-slate-700">
                            {m.currency}
                          </span>
                        </Td>
                        <Td className="text-right font-medium tabular-nums text-slate-900">
                          $
                          {Number(m.amount_usd).toLocaleString("en-US", {
                            maximumFractionDigits: 2,
                          })}
                        </Td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {totalPages > 1 && (
            <Pagination
              code={code}
              accountCode={accountCode}
              page={page}
              totalPages={totalPages}
            />
          )}
        </section>
      </main>
    </>
  );
}

function Pagination({
  code,
  accountCode,
  page,
  totalPages,
}: {
  code: string;
  accountCode: string;
  page: number;
  totalPages: number;
}) {
  const href = (p: number) =>
    `/lodges/${code}/cuentas/${accountCode}?page=${p}`;
  return (
    <nav
      aria-label="Paginación"
      className="mt-4 flex items-center justify-end gap-2 text-sm"
    >
      {page > 1 ? (
        <Link
          href={href(page - 1)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
        >
          ← Anterior
        </Link>
      ) : (
        <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-400">
          ← Anterior
        </span>
      )}
      {page < totalPages ? (
        <Link
          href={href(page + 1)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
        >
          Siguiente →
        </Link>
      ) : (
        <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-400">
          Siguiente →
        </span>
      )}
    </nav>
  );
}

function Kpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-700">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs text-slate-700">{sub}</div>}
    </div>
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
      scope="col"
      className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-800 ${className}`}
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
  return <td className={`px-4 py-2.5 ${className}`}>{children}</td>;
}
