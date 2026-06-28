/** Formatters compartidos para mostrar plata y porcentajes. */

export function fmtUsd(v: number | null | undefined, sign = false): string {
  if (v === null || v === undefined) return "—";
  const opts: Intl.NumberFormatOptions = {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
    signDisplay: sign ? "exceptZero" : "auto",
  };
  return v.toLocaleString("en-US", opts);
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const s = (v * 100).toFixed(1);
  return v > 0 ? `+${s}%` : `${s}%`;
}

export function severityClass(sev: string): string {
  switch (sev) {
    case "alert":
      return "border-l-4 border-red-700 bg-red-50";
    case "warn":
      return "border-l-4 border-orange-700 bg-orange-50";
    case "timing":
      return "border-l-4 border-indigo-500 bg-indigo-50";
    case "ok":
      return "border-l-4 border-emerald-600 bg-emerald-50";
    default:
      return "border-l-4 border-slate-300 bg-slate-50";
  }
}

export function severityText(sev: string): string {
  switch (sev) {
    case "alert":
      return "text-red-700";
    case "warn":
      return "text-orange-700";
    case "timing":
      return "text-indigo-500";
    case "ok":
      return "text-emerald-700";
    default:
      return "text-slate-700";
  }
}
