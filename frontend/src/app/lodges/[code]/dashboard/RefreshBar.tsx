/** Indicador compacto de auto-refresh con estados live/refrescando + accesibilidad. */
"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

const PERIOD_S = 30;
const CIRC = 2 * Math.PI * 9; // r=9 → circumferencia para el ring del countdown

export default function RefreshBar() {
  const router = useRouter();
  const [secs, setSecs] = useState(PERIOD_S);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    const id = setInterval(() => {
      setSecs((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (secs === 0) {
      startTransition(() => router.refresh());
      setSecs(PERIOD_S);
    }
  }, [secs, router]);

  function manualRefresh() {
    startTransition(() => router.refresh());
    setSecs(PERIOD_S);
  }

  const status = isPending ? "Actualizando datos…" : `En vivo. Próxima actualización en ${secs} segundos.`;
  const dashOffset = CIRC * (1 - secs / PERIOD_S);

  return (
    <div className="flex items-center gap-2" role="status" aria-live="polite">
      <span className="sr-only">{status}</span>
      <div
        className={[
          "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium tabular-nums transition-colors",
          isPending
            ? "border-amber-300 bg-amber-50 text-amber-800"
            : "border-emerald-200 bg-emerald-50 text-emerald-800",
        ].join(" ")}
        title={isPending ? "Actualizando…" : `Auto-refresh cada ${PERIOD_S}s. Próxima en ${secs}s.`}
      >
        <span className="relative inline-flex h-2.5 w-2.5" aria-hidden="true">
          {!isPending && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
          )}
          <span
            className={[
              "relative inline-flex h-2.5 w-2.5 rounded-full",
              isPending ? "bg-amber-500 animate-pulse" : "bg-emerald-500",
            ].join(" ")}
          />
        </span>
        <span>{isPending ? "actualizando" : "en vivo"}</span>
        <span aria-hidden="true" className="text-slate-400">·</span>
        <span aria-hidden="true">{secs}s</span>
      </div>
      <button
        type="button"
        onClick={manualRefresh}
        disabled={isPending}
        aria-label={isPending ? "Actualizando datos" : "Refrescar datos ahora"}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 22 22"
          aria-hidden="true"
          className="absolute inset-0 m-auto"
        >
          <circle cx="11" cy="11" r="9" fill="none" stroke="#e2e8f0" strokeWidth="2" />
          <circle
            cx="11"
            cy="11"
            r="9"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 11 11)"
            className={isPending ? "text-amber-500" : "text-emerald-500"}
            style={{ transition: "stroke-dashoffset 0.9s linear" }}
          />
        </svg>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
          className={isPending ? "animate-spin" : ""}
        >
          <path
            d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
