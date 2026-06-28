/** Dashboard de un lodge — consume /api/lodges/{code}/dashboard. */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import type { Flag, RubroComparison } from "@/lib/types";
import { notFound } from "next/navigation";
import RefreshBar from "./RefreshBar";

const HIGH_IMPACT = 2500;

export const dynamic = "force-dynamic";

export default async function DashboardPage({
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

  // Lodge sin season / sin datos: mostramos empty state amigable.
  const hasData =
    data.season.bn_real !== null || data.comparisons.length > 0;

  if (!hasData) {
    return (
      <>
        <PageHeader
          title="Dashboard"
          subtitle="Este lodge todavía no tiene datos cargados."
        />
        <div className="px-8 py-12">
          <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path
                  d="M3 3v18h18M7 14l3-3 3 3 5-7"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-slate-900">
              Sin datos para mostrar todavía
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Este lodge no tiene movimientos cargados ni budget de temporada.
              Cargá el primer movimiento para empezar a ver el dashboard.
            </p>
            <a
              href={`/lodges/${code}/cargar`}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 5v14M5 12h14"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                />
              </svg>
              Cargar primer movimiento
            </a>
          </div>
        </div>
      </>
    );
  }

  const progressPct =
    data.season.months_elapsed && data.season.months_total
      ? Math.round(
          (data.season.months_elapsed / data.season.months_total) * 100,
        )
      : 0;

  const budgetFlags = data.flags.filter((f) => f.rule === "DESVIO_BUDGET");
  const notTiming = budgetFlags.filter(
    (f) => !f.is_seasonal && (f.severity === "alert" || f.severity === "warn"),
  );

  const byUsd = [...notTiming].sort(
    (a, b) => Math.abs(b.impact_usd ?? 0) - Math.abs(a.impact_usd ?? 0),
  );
  const highImpact = byUsd.filter(
    (f) => Math.abs(f.impact_usd ?? 0) >= HIGH_IMPACT,
  );
  const highPctOnly = [...notTiming]
    .filter(
      (f) =>
        Math.abs(f.impact_usd ?? 0) < HIGH_IMPACT &&
        Math.abs(f.value ?? 0) >= 0.3,
    )
    .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0));

  const overspend = notTiming.filter((f) => (f.value ?? 0) > 0);
  const savings = notTiming.filter((f) => (f.value ?? 0) < 0);
  const missed = overspend.filter((f) => !f.obs_cliente).slice(0, 4);
  const timing = budgetFlags.filter((f) => f.severity === "timing");

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={`Temporada 2025-2026 · ${data.season.months_elapsed ?? 0} de ${data.season.months_total ?? 0} meses transcurridos`}
        actions={<RefreshBar />}
      />

      <div className="px-8 py-6">
        {/* KPIs */}
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Kpi
            label="BN real"
            value={data.season.bn_real?.toFixed(0) ?? "—"}
            subtitle={`budget ${data.season.bn_budget?.toFixed(0) ?? "—"}`}
          />
          <Kpi
            label="Avance temporada"
            value={`${progressPct}%`}
            subtitle={`${data.season.months_elapsed ?? 0} / ${data.season.months_total ?? 0} meses`}
            progress={progressPct}
          />
          <Kpi
            label="Sobrecostos"
            value={overspend.length.toString()}
            subtitle={`${missed.length} sin observación`}
            tone="alert"
          />
          <Kpi
            label="Ahorros"
            value={savings.length.toString()}
            subtitle="gastaron menos del budget"
            tone="ok"
          />
        </div>

        <Section
          title="Desvíos críticos por impacto USD"
          description={`Rubros con más de USD ${HIGH_IMPACT.toLocaleString()} de diferencia vs budget. Ordenados por monto absoluto.`}
        >
          <Cards flags={highImpact.slice(0, 6)} />
        </Section>

        {highPctOnly.length > 0 && (
          <Section
            title="Desvíos altos por porcentaje (rubros chicos en USD)"
            description={`Rubros con desvío > 30% pero menos de USD ${HIGH_IMPACT.toLocaleString()} de impacto. El budget original quedó subdimensionado.`}
          >
            <Cards flags={highPctOnly.slice(0, 6)} />
          </Section>
        )}

        {missed.length > 0 && (
          <Section
            title="Sobrecostos sin observación del cliente"
            description="El cliente no comentó estos. Posibles 'se les pasó'."
          >
            <Cards flags={missed} />
          </Section>
        )}

        {timing.length > 0 && (
          <Section
            title="Posibles 'timing' (cuotas anuales pendientes)"
            description="Patentes, seguros y licencias se pagan en pocas cuotas al año. Un desvío negativo aquí suele ser plata que todavía no se pagó."
          >
            <Cards flags={timing} />
          </Section>
        )}

        <Section
          title="Detalle por rubro"
          description="Todos los rubros, ordenados por impacto absoluto."
        >
          <ComparisonTable rows={data.comparisons} />
        </Section>
      </div>
    </>
  );
}

function Kpi({
  label,
  value,
  subtitle,
  tone,
  progress,
}: {
  label: string;
  value: string;
  subtitle?: string;
  tone?: "alert" | "ok" | "timing";
  progress?: number;
}) {
  const valueColor =
    tone === "alert"
      ? "text-red-700"
      : tone === "ok"
        ? "text-emerald-700"
        : tone === "timing"
          ? "text-indigo-600"
          : "text-slate-900";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-600">
        {label}
      </div>
      <div className={`mt-2 text-3xl font-bold leading-none ${valueColor}`}>
        {value}
      </div>
      {subtitle && (
        <div className="mt-2 text-xs text-slate-600">{subtitle}</div>
      )}
      {progress !== undefined && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-slate-800 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-slate-600">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

function Cards({ flags }: { flags: Flag[] }) {
  if (flags.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
        Sin desvíos en esta categoría.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {flags.map((f, i) => (
        <Card key={i} flag={f} />
      ))}
    </div>
  );
}

function Card({ flag }: { flag: Flag }) {
  const visualSev =
    flag.severity === "timing"
      ? "timing"
      : (flag.value ?? 0) < 0
        ? "ok"
        : flag.severity;

  const badgeLabel =
    visualSev === "timing"
      ? "posible timing"
      : visualSev === "ok"
        ? "ahorro"
        : "sobrecosto";

  const accent =
    visualSev === "alert"
      ? "border-l-red-600"
      : visualSev === "warn"
        ? "border-l-orange-500"
        : visualSev === "ok"
          ? "border-l-emerald-500"
          : visualSev === "timing"
            ? "border-l-indigo-500"
            : "border-l-slate-300";

  const pctColor =
    visualSev === "alert"
      ? "text-red-700"
      : visualSev === "warn"
        ? "text-orange-700"
        : visualSev === "ok"
          ? "text-emerald-700"
          : visualSev === "timing"
            ? "text-indigo-600"
            : "text-slate-900";

  return (
    <div
      className={`flex flex-col gap-3 rounded-xl border-l-4 border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md ${accent}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-semibold leading-tight text-slate-900">
          {flag.rubro}
        </div>
        <div className="flex flex-shrink-0 gap-1.5">
          <Badge variant={visualSev}>{badgeLabel}</Badge>
          {flag.obs_cliente ? (
            <Badge variant="ok">visto</Badge>
          ) : visualSev === "alert" || visualSev === "warn" ? (
            <Badge variant="alert">sin ver</Badge>
          ) : null}
        </div>
      </div>
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold ${pctColor}`}>
          {fmtPct(flag.value)}
        </span>
        {flag.impact_usd !== null && (
          <span className="text-sm font-medium tabular-nums text-slate-700">
            {fmtUsd(flag.impact_usd, true)} USD
          </span>
        )}
      </div>
      <div className="text-xs leading-relaxed text-slate-700">{flag.reason}</div>
      {flag.obs_cliente ? (
        <div className="rounded-lg bg-slate-100 px-3 py-2.5 text-xs text-slate-800">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
            Observación del cliente
          </div>
          {flag.obs_cliente}
        </div>
      ) : visualSev === "alert" || visualSev === "warn" ? (
        <div className="rounded-lg bg-red-50 px-3 py-2.5 text-xs text-red-900">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-red-700">
            Sin observación del cliente
          </div>
          El sistema detectó este sobrecosto pero el cliente no lo comentó.
          Candidato a revisión.
        </div>
      ) : null}
    </div>
  );
}

function Badge({
  variant,
  children,
}: {
  variant: string;
  children: React.ReactNode;
}) {
  const cls =
    variant === "alert"
      ? "bg-red-100 text-red-800"
      : variant === "warn"
        ? "bg-orange-100 text-orange-800"
        : variant === "ok"
          ? "bg-emerald-100 text-emerald-800"
          : variant === "timing"
            ? "bg-indigo-100 text-indigo-800"
            : "bg-slate-200 text-slate-800";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${cls}`}
    >
      {children}
    </span>
  );
}

function ComparisonTable({ rows }: { rows: RubroComparison[] }) {
  const sorted = [...rows].sort(
    (a, b) =>
      Math.abs((b.real_usd ?? 0) - (b.budget_usd ?? 0)) -
      Math.abs((a.real_usd ?? 0) - (a.budget_usd ?? 0)),
  );
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <Th>Rubro</Th>
              <Th>Cuentas</Th>
              <Th className="text-right">Budget USD</Th>
              <Th className="text-right">Real USD</Th>
              <Th className="text-right">Δ USD</Th>
              <Th className="text-right">Budget USD/BN</Th>
              <Th className="text-right">Real USD/BN</Th>
              <Th className="text-right">Δ %</Th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => {
              const delta = (c.real_usd ?? 0) - (c.budget_usd ?? 0);
              const pct = c.variance_pct;
              const rowBg =
                pct !== null && pct < -0.1
                  ? "bg-emerald-50/60"
                  : pct !== null && pct >= 0.3
                    ? "bg-red-50/60"
                    : pct !== null && pct >= 0.15
                      ? "bg-orange-50/60"
                      : pct !== null && pct >= 0.1
                        ? "bg-yellow-50/60"
                        : "";
              const pctColor =
                pct !== null && pct < -0.1
                  ? "text-emerald-700"
                  : pct !== null && pct >= 0.3
                    ? "text-red-700"
                    : pct !== null && pct >= 0.15
                      ? "text-orange-700"
                      : "text-slate-900";
              return (
                <tr
                  key={i}
                  className={`border-t border-slate-200 ${rowBg}`}
                >
                  <Td className="font-medium text-slate-900">{c.rubro}</Td>
                  <Td className="text-xs text-slate-600">
                    {c.account_codes.join("+")}
                  </Td>
                  <Td className="text-right tabular-nums text-slate-900">
                    {fmtUsd(c.budget_usd)}
                  </Td>
                  <Td className="text-right tabular-nums text-slate-900">
                    {fmtUsd(c.real_usd)}
                  </Td>
                  <Td className="text-right tabular-nums text-slate-900">
                    {fmtUsd(delta, true)}
                  </Td>
                  <Td className="text-right tabular-nums text-slate-700">
                    {fmtUsd(c.budget_per_bn)}
                  </Td>
                  <Td className="text-right tabular-nums text-slate-700">
                    {fmtUsd(c.real_per_bn)}
                  </Td>
                  <Td className={`text-right font-semibold tabular-nums ${pctColor}`}>
                    {fmtPct(pct)}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
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
  return <td className={`px-4 py-2.5 ${className}`}>{children}</td>;
}
