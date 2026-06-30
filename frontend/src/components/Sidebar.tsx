/** Sidebar fijo a la izquierda con navegación + selector de lodge. */
"use client";
import LodgeSwitcher from "@/components/LodgeSwitcher";
import type { LodgeSummary } from "@/lib/types";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
};

export default function Sidebar({
  current,
  lodges,
}: {
  current: LodgeSummary;
  lodges: LodgeSummary[];
}) {
  const pathname = usePathname();
  const nav: NavItem[] = [
    {
      href: `/lodges/${current.code}/dashboard`,
      label: "Dashboard",
      icon: <IconChart />,
    },
    {
      href: `/lodges/${current.code}/rubros`,
      label: "Rubros",
      icon: <IconStack />,
    },
    {
      href: `/lodges/${current.code}/cargar`,
      label: "Cargar movimiento",
      icon: <IconPlus />,
    },
    {
      href: `/lodges/${current.code}/movimientos`,
      label: "Movimientos",
      icon: <IconList />,
    },
  ];
  // Las páginas de cuenta-detalle viven en /cuentas/[code] pero conceptualmente
  // se entra desde el rubro, así que resaltamos "Rubros".
  const activeHref = pathname.includes(`/cuentas/`)
    ? `/lodges/${current.code}/rubros`
    : null;

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col bg-slate-900 text-slate-100">
      {/* Brand */}
      <div className="border-b border-slate-800 px-6 py-5">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Kautapen
        </div>
        <div className="mt-0.5 text-base font-semibold text-white">
          Operaciones
        </div>
      </div>

      {/* Lodge switcher */}
      <div className="border-b border-slate-800 px-2 py-2">
        <LodgeSwitcher current={current} lodges={lodges} />
      </div>

      {/* Nav principal */}
      <nav className="flex-1 px-3 py-4">
        <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Lodge
        </div>
        <ul className="space-y-0.5">
          {nav.map((item) => {
            const isActive =
              activeHref === item.href ||
              pathname === item.href ||
              pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={[
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-800 text-white"
                      : "text-slate-300 hover:bg-slate-800/60 hover:text-white",
                  ].join(" ")}
                >
                  <span className={isActive ? "text-white" : "text-slate-400"}>
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-800 px-6 py-4 text-xs text-slate-500">
        v0.3 · Fase 2B
      </div>
    </aside>
  );
}

function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M3 3v18h18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M7 14l3-3 3 3 5-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconList() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconStack() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 3l9 5-9 5-9-5 9-5z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M3 13l9 5 9-5M3 17l9 5 9-5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}
