/** Dashboard de un lodge — consume /api/lodges/{code}/dashboard. */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import type { Flag } from "@/lib/types";
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

  const hasData =
    data.season.bn_real !== null || data.comparisons.length > 0;

  if (!hasData) {
    return (
      <>
        <PageHeader
          title="Dashboard"
          subtitle="Este lodge todavía no tiene datos cargados."
        />
        <main id="main" className="px-8 py-12">
          <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-600">
              <IconChart />
            </div>
            <h2 className="text-base font-semibold text-slate-900">
              Sin datos para mostrar todavía
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              Este lodge no tiene movimientos cargados ni budget de temporada.
              Cargá el primer movimiento para empezar a ver el dashboard.
            </p>
            <a
              href={`/lodges/${code}/cargar`}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            >
              <IconPlus />
              Cargar primer movimiento
            </a>
          </div>
        </main>
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

  // Para gastos: value > 0 (real > budget) es mala noticia (sobrecosto).
  // Para ingresos: value < 0 (real < budget) es mala noticia (ventas bajas).
  const isBadNews = (f: Flag) =>
    f.is_income ? (f.value ?? 0) < 0 : (f.value ?? 0) > 0;

  const overspend = notTiming.filter(isBadNews);
  const savings = notTiming.filter((f) => !isBadNews(f));
  const missed = overspend.filter((f) => !f.obs_cliente).slice(0, 4);
  const timing = budgetFlags.filter((f) => f.severity === "timing");

  const bnDelta =
    data.season.bn_real !== null && data.season.bn_budget !== null
      ? data.season.bn_real - data.season.bn_budget
      : null;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={`Temporada 2025-2026 · ${data.season.months_elapsed ?? 0} de ${data.season.months_total ?? 0} meses transcurridos`}
        actions={<RefreshBar />}
      />

      <main id="main" className="px-8 py-6">
        {/* KPIs principales */}
        <section
          aria-label="Indicadores principales"
          className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4"
        >
          <Kpi
            label="BN real"
            value={data.season.bn_real?.toFixed(0) ?? "—"}
            subtitle={`budget ${data.season.bn_budget?.toFixed(0) ?? "—"}`}
            delta={bnDelta}
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
            icon={<IconArrowUp />}
          />
          <Kpi
            label="Ahorros"
            value={savings.length.toString()}
            subtitle="gastaron menos del budget"
            tone="ok"
            icon={<IconArrowDown />}
          />
        </section>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Section title="Desvíos vs Budget (top 12)">
            <BarChart flags={byUsd.slice(0, 12)} />
          </Section>

          {data.mom_flags && data.mom_flags.length > 0 && (
            <Section title="Saltos mes a mes (top 12)">
              <BarChart flags={data.mom_flags.slice(0, 12)} />
            </Section>
          )}
        </div>

        {missed.length > 0 && (
          <Section
            title="Sin observación del cliente"
            description="Sobrecostos que el cliente no comentó. Candidatos a revisión."
          >
            <Cards flags={missed} />
          </Section>
        )}

        {timing.length > 0 && (
          <Section
            title="Cuotas anuales"
            description="Rubros que se pagan en pocas cuotas al año (patentes, seguros, licencias). Un desvío negativo suele ser timing, no ahorro real."
          >
            <Cards flags={timing} />
          </Section>
        )}

      </main>
    </>
  );
}

/* ============================ Sub-componentes ============================ */

type Tone = "alert" | "warn" | "ok" | "timing" | "neutral";

function DiagChip({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number | string;
  tone: Tone;
  icon: React.ReactNode;
}) {
  const cls =
    tone === "alert"
      ? "bg-red-50 text-red-800 border-red-200"
      : tone === "warn"
        ? "bg-orange-50 text-orange-800 border-orange-200"
        : tone === "ok"
          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
          : tone === "timing"
            ? "bg-indigo-50 text-indigo-800 border-indigo-200"
            : "bg-slate-50 text-slate-800 border-slate-200";
  return (
    <div
      className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 ${cls}`}
    >
      <span aria-hidden="true" className="flex-shrink-0">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
          {label}
        </div>
        <div className="text-base font-bold tabular-nums leading-tight">
          {value}
        </div>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  subtitle,
  tone,
  progress,
  delta,
  icon,
}: {
  label: string;
  value: string;
  subtitle?: string;
  tone?: "alert" | "ok" | "timing";
  progress?: number;
  delta?: number | null;
  icon?: React.ReactNode;
}) {
  const valueColor =
    tone === "alert"
      ? "text-red-700"
      : tone === "ok"
        ? "text-emerald-700"
        : tone === "timing"
          ? "text-indigo-700"
          : "text-slate-900";

  const deltaTone =
    delta === null || delta === undefined || delta === 0
      ? "text-slate-600"
      : delta > 0
        ? "text-red-700"
        : "text-emerald-700";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow">
      <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-700">
        <span>{label}</span>
        {icon && <span aria-hidden="true">{icon}</span>}
      </div>
      <div className={`mt-2 text-3xl font-bold leading-none tabular-nums ${valueColor}`}>
        {value}
      </div>
      {subtitle && (
        <div className="mt-2 text-xs text-slate-700">{subtitle}</div>
      )}
      {delta !== undefined && delta !== null && (
        <div
          className={`mt-1 flex items-center gap-1 text-xs font-semibold tabular-nums ${deltaTone}`}
        >
          <span aria-hidden="true">
            {delta > 0 ? <IconArrowUp /> : delta < 0 ? <IconArrowDown /> : null}
          </span>
          <span>
            {delta > 0 ? "+" : ""}
            {delta.toFixed(0)} vs budget
          </span>
        </div>
      )}
      {progress !== undefined && (
        <div
          className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200"
          role="progressbar"
          aria-valuenow={Math.min(100, Math.max(0, progress))}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${progress}%`}
        >
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
          <p className="mt-1 text-sm text-slate-700">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

function Cards({ flags }: { flags: Flag[] }) {
  if (flags.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-700">
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
  // Semántica: para gastos, "ok" = real bajo budget; para ingresos, "ok" = real
  // sobre budget. La asignación de visualSev se hace mirando is_income.
  const isGoodNews = flag.is_income
    ? (flag.value ?? 0) > 0
    : (flag.value ?? 0) < 0;

  const visualSev =
    flag.severity === "timing"
      ? "timing"
      : isGoodNews
        ? "ok"
        : flag.severity;

  const badgeLabel =
    visualSev === "timing"
      ? "posible timing"
      : visualSev === "ok"
        ? flag.is_income
          ? "más ventas"
          : "ahorro"
        : flag.is_income
          ? "ventas bajas"
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
            ? "text-indigo-700"
            : "text-slate-900";

  const severityIcon =
    visualSev === "alert" || visualSev === "warn" ? (
      <IconArrowUp />
    ) : visualSev === "ok" ? (
      <IconArrowDown />
    ) : visualSev === "timing" ? (
      <IconClock />
    ) : null;

  const isOverspend = visualSev === "alert" || visualSev === "warn";

  return (
    <article
      className={`flex flex-col gap-3 rounded-xl border border-l-4 border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md ${accent}`}
      aria-label={`${flag.rubro}: ${badgeLabel}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-tight text-slate-900">
          {flag.rubro}
        </h3>
        <div className="flex flex-shrink-0 gap-1.5">
          <Badge variant={visualSev}>
            <span aria-hidden="true" className="mr-1 inline-flex items-center">
              {severityIcon}
            </span>
            {badgeLabel}
          </Badge>
          {flag.obs_cliente ? (
            <Badge variant="ok">
              <IconCheck />
              <span className="ml-1">visto</span>
            </Badge>
          ) : isOverspend ? (
            <Badge variant="alert">
              <IconEyeOff />
              <span className="ml-1">sin ver</span>
            </Badge>
          ) : null}
        </div>
      </div>
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold tabular-nums ${pctColor}`}>
          {fmtPct(flag.value)}
        </span>
        {flag.impact_usd !== null && (
          <span className="text-sm font-medium tabular-nums text-slate-800">
            {fmtUsd(flag.impact_usd, true)} USD
          </span>
        )}
      </div>
      <div className="text-xs leading-relaxed text-slate-700">{flag.reason}</div>
      {flag.obs_cliente ? (
        <div className="rounded-lg bg-slate-100 px-3 py-2.5 text-xs text-slate-800">
          <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
            <IconCheck />
            Observación del cliente
          </div>
          {flag.obs_cliente}
        </div>
      ) : isOverspend ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-900">
          <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-red-800">
            <IconEyeOff />
            Sin observación del cliente
          </div>
          El sistema detectó este sobrecosto pero el cliente no lo comentó.
          Candidato a revisión.
        </div>
      ) : null}
    </article>
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
      ? "bg-red-100 text-red-900"
      : variant === "warn"
        ? "bg-orange-100 text-orange-900"
        : variant === "ok"
          ? "bg-emerald-100 text-emerald-900"
          : variant === "timing"
            ? "bg-indigo-100 text-indigo-900"
            : "bg-slate-200 text-slate-900";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${cls}`}
    >
      {children}
    </span>
  );
}

function BarChart({ flags }: { flags: Flag[] }) {
  if (flags.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-700">
        Sin alertas en esta categoría.
      </div>
    );
  }
  const max = Math.max(...flags.map((f) => Math.abs(f.impact_usd ?? 0)), 1);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <ul role="list" className="space-y-1.5">
        {flags.map((f, i) => (
          <BarRow key={i} flag={f} max={max} />
        ))}
      </ul>
    </div>
  );
}

function BarRow({ flag, max }: { flag: Flag; max: number }) {
  const impact = flag.impact_usd ?? 0;
  const absImpact = Math.abs(impact);
  const widthPct = max > 0 ? (absImpact / max) * 100 : 0;

  // Para gastos: impact > 0 = mala noticia. Para ingresos: impact < 0 = mala noticia.
  const isBadNews = flag.is_income ? impact < 0 : impact > 0;
  const barColor = isBadNews
    ? flag.severity === "alert"
      ? "bg-red-500"
      : flag.severity === "warn"
        ? "bg-orange-400"
        : "bg-amber-400"
    : "bg-emerald-500";
  const usdColor = isBadNews ? "text-red-800" : "text-emerald-800";
  const noObsBadge =
    !flag.obs_cliente && isBadNews && flag.rule === "DESVIO_BUDGET";

  return (
    <li
      className="flex items-center gap-3 py-1"
      title={flag.reason}
      aria-label={`${flag.rubro}: ${flag.reason}`}
    >
      <div className="w-48 flex-shrink-0 truncate text-sm font-medium text-slate-900">
        {flag.rubro}
      </div>
      <div className="flex-1 min-w-0">
        <div
          className="relative h-5 overflow-hidden rounded bg-slate-100"
          role="progressbar"
          aria-valuenow={Math.round(widthPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Impacto relativo: ${widthPct.toFixed(0)}%`}
        >
          <div
            className={`absolute inset-y-0 left-0 rounded transition-all ${barColor}`}
            style={{ width: `${Math.max(widthPct, 1)}%` }}
          />
        </div>
      </div>
      <div
        className={`w-24 flex-shrink-0 text-right text-sm font-semibold tabular-nums ${usdColor}`}
      >
        {fmtUsd(impact, true)}
      </div>
      <div className="w-16 flex-shrink-0 text-right text-xs tabular-nums text-slate-700">
        {fmtPct(flag.value)}
      </div>
      {noObsBadge ? (
        <span
          aria-label="Sin observación del cliente"
          className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-900"
          title="Sin observación del cliente"
        >
          sin ver
        </span>
      ) : (
        <span className="w-12 flex-shrink-0" aria-hidden="true" />
      )}
    </li>
  );
}

function CompactSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {description && (
        <p className="mt-0.5 text-xs text-slate-700">{description}</p>
      )}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function ChipList({
  flags,
  tone,
}: {
  flags: Flag[];
  tone: "alert" | "timing";
}) {
  if (flags.length === 0) return null;
  const cls =
    tone === "alert"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-indigo-200 bg-indigo-50 text-indigo-900";
  return (
    <ul role="list" className="flex flex-col gap-1.5">
      {flags.map((f, i) => (
        <li
          key={i}
          className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-1.5 text-xs ${cls}`}
          title={f.reason}
        >
          <span className="truncate font-semibold">{f.rubro}</span>
          <span className="flex-shrink-0 tabular-nums">
            {fmtUsd(f.impact_usd, true)}{" "}
            <span className="opacity-70">({fmtPct(f.value)})</span>
          </span>
        </li>
      ))}
    </ul>
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

/* ================================ Iconos ================================ */

function IconArrowUp() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconArrowDown() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 5v14M19 12l-7 7-7-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 7v5l3 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3l10 18H2L12 3z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M12 10v5M12 18h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconEyeOff() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 3l18 18M10.6 6.1A9.4 9.4 0 0 1 12 6c5 0 9 6 9 6a17 17 0 0 1-3.1 3.6M6.1 6.1A17 17 0 0 0 3 12s4 6 9 6c1.4 0 2.7-.4 3.9-1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 12l5 5L20 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconCalendar() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 9h18M8 3v4M16 3v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 3v18h18M7 14l3-3 3 3 5-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}
