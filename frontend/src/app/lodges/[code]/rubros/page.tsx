/** Listado de todos los rubros del Budget Comparativo, con sus desvíos vs budget.
 * Cada fila es un Link entero al detalle del rubro (que muestra las cuentas
 * componentes del cálculo).
 */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

// Grid columns compartidas por header y rows.
// La última columna es el indicador "→" de fila clickeable.
const GRID =
  "grid grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_120px_120px_120px_110px_110px_100px_24px] gap-3 px-4 py-2.5 items-center";

export default async function RubrosPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  let data;
  try {
    data = await api.dashboard(code);
  } catch {
    notFound();
  }

  const rows = [...data.comparisons].sort(
    (a, b) =>
      Math.abs((b.real_usd ?? 0) - (b.budget_usd ?? 0)) -
      Math.abs((a.real_usd ?? 0) - (a.budget_usd ?? 0)),
  );

  return (
    <>
      <PageHeader
        title="Rubros"
        subtitle={`${rows.length} rubros · ordenados por impacto USD absoluto · % vs Budget calculado por bednight · click para ver el detalle de cuentas`}
      />
      <main id="main" className="px-8 py-6">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          {/* Header */}
          <div
            className={`${GRID} border-b border-slate-200 bg-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-800`}
            role="row"
          >
            <div role="columnheader">Rubro</div>
            <div role="columnheader">Cuentas</div>
            <div role="columnheader" className="text-right">
              Budget USD
            </div>
            <div role="columnheader" className="text-right">
              Real USD
            </div>
            <div role="columnheader" className="text-right">
              Δ USD
            </div>
            <div role="columnheader" className="text-right">
              Bud USD/BN
            </div>
            <div role="columnheader" className="text-right">
              Real USD/BN
            </div>
            <div role="columnheader" className="text-right">
              % vs Budget
            </div>
            <div role="columnheader" aria-hidden="true" />
          </div>

          {/* Rows */}
          {rows.map((c) => {
            const delta = (c.real_usd ?? 0) - (c.budget_usd ?? 0);
            const pct = c.variance_pct;
            const goodPct = pct !== null ? (c.is_income ? pct : -pct) : null;
            const rowBg =
              goodPct !== null && goodPct <= -0.3
                ? "bg-red-50/60 hover:bg-red-100/60"
                : goodPct !== null && goodPct <= -0.15
                  ? "bg-orange-50/60 hover:bg-orange-100/60"
                  : goodPct !== null && goodPct > 0.1
                    ? "bg-emerald-50/60 hover:bg-emerald-100/60"
                    : "hover:bg-slate-50";
            const pctColor =
              goodPct !== null && goodPct <= -0.3
                ? "text-red-800"
                : goodPct !== null && goodPct <= -0.15
                  ? "text-orange-800"
                  : goodPct !== null && goodPct > 0.1
                    ? "text-emerald-800"
                    : "text-slate-900";

            const isClickable = Boolean(c.rubro_id);
            const inner = (
              <>
                <div
                  className={`truncate font-medium ${
                    isClickable
                      ? "text-slate-900 underline decoration-slate-400 underline-offset-4 group-hover:decoration-slate-700"
                      : "text-slate-900"
                  }`}
                >
                  {c.rubro}
                </div>
                <div className="truncate text-xs text-slate-700">
                  {c.account_codes.join("+") || "—"}
                </div>
                <div className="text-right tabular-nums text-sm text-slate-900">
                  {fmtUsd(c.budget_usd)}
                </div>
                <div className="text-right tabular-nums text-sm text-slate-900">
                  {fmtUsd(c.real_usd)}
                </div>
                <div className="text-right tabular-nums text-sm text-slate-900">
                  {fmtUsd(delta, true)}
                </div>
                <div className="text-right tabular-nums text-sm text-slate-700">
                  {fmtUsd(c.budget_per_bn)}
                </div>
                <div className="text-right tabular-nums text-sm text-slate-700">
                  {fmtUsd(c.real_per_bn)}
                </div>
                <div
                  className={`text-right font-semibold tabular-nums text-sm ${pctColor}`}
                >
                  {fmtPct(pct)}
                </div>
                <div
                  aria-hidden="true"
                  className={`text-right text-sm ${
                    isClickable
                      ? "text-slate-400 group-hover:text-slate-800"
                      : "text-transparent"
                  }`}
                >
                  →
                </div>
              </>
            );

            if (c.rubro_id) {
              return (
                <Link
                  key={c.rubro_id}
                  href={`/lodges/${code}/rubros/${c.rubro_id}`}
                  className={`group ${GRID} border-t border-slate-200 transition-colors ${rowBg}`}
                  role="row"
                  aria-label={`Ver cuentas del rubro ${c.rubro}`}
                >
                  {inner}
                </Link>
              );
            }
            return (
              <div
                key={c.rubro}
                className={`${GRID} border-t border-slate-200 ${rowBg}`}
                role="row"
              >
                {inner}
              </div>
            );
          })}
        </div>
      </main>
    </>
  );
}
