/** Indicador compacto de auto-refresh: badge con tiempo + botón icon-only. */
"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const PERIOD_S = 30;

export default function RefreshBar() {
  const router = useRouter();
  const [secs, setSecs] = useState(PERIOD_S);

  useEffect(() => {
    const id = setInterval(() => {
      setSecs((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (secs === 0) {
      router.refresh();
      setSecs(PERIOD_S);
    }
  }, [secs, router]);

  function manualRefresh() {
    router.refresh();
    setSecs(PERIOD_S);
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-600"
        title={`Auto-actualiza cada ${PERIOD_S}s. Próxima en ${secs}s.`}
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
        <span className="tabular-nums">{secs}s</span>
      </div>
      <button
        onClick={manualRefresh}
        title="Refrescar ahora"
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition-colors hover:bg-slate-100"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
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
