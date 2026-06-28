/** Dropdown para cambiar de lodge desde el sidebar.
 * Mantiene la sub-página actual (dashboard/cargar/movimientos) al cambiar.
 */
"use client";
import type { LodgeSummary } from "@/lib/types";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function LodgeSwitcher({
  current,
  lodges,
}: {
  current: LodgeSummary;
  lodges: LodgeSummary[];
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const wrapRef = useRef<HTMLDivElement>(null);

  // Sub-página actual: dashboard | cargar | movimientos
  const subPage =
    pathname.split("/").pop() === current.code
      ? "dashboard"
      : pathname.split("/").pop() || "dashboard";

  // Cerrar al click afuera
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  function go(code: string) {
    setOpen(false);
    router.push(`/lodges/${code}/${subPage}`);
  }

  // Agrupar por región
  const grouped: Record<string, LodgeSummary[]> = {};
  for (const l of lodges) {
    const key = l.region ?? "Sin región";
    (grouped[key] ||= []).push(l);
  }
  const sortedRegions = Object.keys(grouped).sort();

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-slate-800"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Lodge actual
          </div>
          <div className="mt-0.5 flex items-baseline gap-2">
            <span className="truncate text-base font-semibold text-white">
              {current.name}
            </span>
            <span className="text-xs font-medium text-slate-400">
              {current.code}
            </span>
          </div>
          <div className="mt-0.5 truncate text-xs text-slate-400">
            {current.region ?? "Sin región"} · {current.currency}
          </div>
        </div>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          className={`flex-shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M6 9l6 6 6-6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-2 right-2 top-full z-50 mt-1 max-h-96 overflow-y-auto rounded-lg border border-slate-700 bg-slate-800 py-1 shadow-2xl">
          {sortedRegions.map((region) => (
            <div key={region}>
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {region}
              </div>
              {grouped[region].map((l) => {
                const isCurrent = l.code === current.code;
                return (
                  <button
                    key={l.code}
                    onClick={() => go(l.code)}
                    className={[
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors",
                      isCurrent
                        ? "bg-slate-700 text-white"
                        : "text-slate-200 hover:bg-slate-700/60",
                    ].join(" ")}
                  >
                    <div>
                      <span className="font-medium">{l.name}</span>{" "}
                      <span className="text-xs text-slate-400">
                        · {l.currency}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">{l.code}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
