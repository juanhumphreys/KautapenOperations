/** Detalle de un rubro: mini-dash con budget vs real + breakdown por cuenta.
 * Cada cuenta es link al detalle de la misma (movimientos + stats).
 */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

// Grid de la tabla de cuentas — última columna es el chevron clickeable.
const ACCOUNTS_GRID =
  "grid grid-cols-[120px_minmax(0,2fr)_140px_120px_140px_24px] gap-3 px-4 py-2.5 items-center";

export default async function RubroDetailPage({
  params,
}: {
  params: Promise<{ code: string; rubroId: string }>;
}) {
  const { code, rubroId } = await params;
  let data;
  try {
    data = await api.rubroDetail(code, rubroId);
  } catch {
    notFound();
  }

  const delta = data.real_usd - (data.budget_usd ?? 0);
  const pct = data.variance_pct;
  const goodPct = pct !== null ? (data.is_income ? pct : -pct) : null;
  const pctColor =
    goodPct === null
      ? "text-slate-900"
      : goodPct <= -0.3
        ? "text-red-700"
        : goodPct <= -0.15
          ? "text-orange-700"
          : goodPct > 0.1
            ? "text-emerald-700"
            : "text-slate-900";

  return (
    <>
      <PageHeader
        title={data.rubro.name}
        subtitle={
          <>
            <Link
              href={`/lodges/${code}/rubros`}
              className="text-slate-700 hover:underline"
            >
              ← Volver a rubros
            </Link>
            {data.rubro.criterio && (
              <span className="ml-2 text-slate-700">
                · criterio {data.rubro.criterio}
              </span>
            )}
          </>
        }
      />
      <main id="main" className="px-8 py-6">
        {/* Mini-dash KPIs */}
        <section
          aria-label="Resumen del rubro"
          className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5"
        >
          <Kpi label="Budget USD" value={fmtUsd(data.budget_usd)} />
          <Kpi label="Real USD" value={fmtUsd(data.real_usd)} />
          <Kpi label="Δ USD" value={fmtUsd(delta, true)} />
          <Kpi
            label="Budget USD/BN"
            value={fmtUsd(data.budget_per_bn)}
            sub={`real ${fmtUsd(data.real_per_bn)}`}
          />
          <Kpi
            label="% vs Budget"
            value={fmtPct(pct)}
            valueClass={pctColor}
            sub={data.is_income ? "rubro de ingreso" : undefined}
          />
        </section>

        {data.observation && (
          <section className="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
              Observación del cliente
            </div>
            {data.observation}
          </section>
        )}

        {/* Tabla de cuentas — cada fila es link al detalle (movimientos). */}
        <section>
          <h2 className="mb-3 text-base font-semibold text-slate-900">
            Cuentas del rubro
          </h2>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div
              className={`${ACCOUNTS_GRID} border-b border-slate-200 bg-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-800`}
              role="row"
            >
              <div role="columnheader">Código</div>
              <div role="columnheader">Nombre</div>
              <div role="columnheader" className="text-right">
                Real USD
              </div>
              <div role="columnheader" className="text-right">
                % del rubro
              </div>
              <div role="columnheader" className="text-right">
                # movimientos
              </div>
              <div role="columnheader" aria-hidden="true" />
            </div>
            {data.accounts.length === 0 ? (
              <div className="px-4 py-12 text-center text-sm text-slate-700">
                Este rubro no tiene cuentas asignadas.
              </div>
            ) : (
              data.accounts.map((a) => {
                const share =
                  data.real_usd !== 0 ? a.total_usd / data.real_usd : 0;
                return (
                  <Link
                    key={a.code}
                    href={`/lodges/${code}/cuentas/${a.code}`}
                    className={`group ${ACCOUNTS_GRID} border-t border-slate-200 transition-colors hover:bg-slate-50`}
                    role="row"
                    aria-label={`Ver movimientos de la cuenta ${a.code} ${a.name}`}
                  >
                    <div className="truncate font-medium text-slate-900 underline decoration-slate-400 underline-offset-4 group-hover:decoration-slate-700">
                      {a.code}
                    </div>
                    <div className="truncate text-slate-900">{a.name}</div>
                    <div className="text-right tabular-nums text-slate-900">
                      {fmtUsd(a.total_usd)}
                    </div>
                    <div className="text-right tabular-nums text-slate-700">
                      {(share * 100).toFixed(1)}%
                    </div>
                    <div className="text-right tabular-nums text-slate-700">
                      {a.n_movements.toLocaleString()}
                    </div>
                    <div
                      aria-hidden="true"
                      className="text-right text-sm text-slate-400 group-hover:text-slate-800"
                    >
                      →
                    </div>
                  </Link>
                );
              })
            )}
          </div>
        </section>
      </main>
    </>
  );
}

function Kpi({
  label,
  value,
  sub,
  valueClass = "text-slate-900",
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-700">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${valueClass}`}>
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs text-slate-700">{sub}</div>}
    </div>
  );
}

