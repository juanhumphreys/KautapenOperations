/** Lista de movimientos cargados — con filtros por fecha, cuenta y paginación. */
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import Link from "next/link";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

type SearchParams = {
  page?: string;
  from_date?: string;
  to_date?: string;
  account?: string;
};

export default async function MovimientosPage({
  params,
  searchParams,
}: {
  params: Promise<{ code: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { code } = await params;
  const sp = await searchParams;

  const page = Math.max(1, Number(sp.page ?? 1));
  const from_date = sp.from_date || undefined;
  const to_date = sp.to_date || undefined;
  const account = sp.account || undefined;

  const lodges = await api.listLodges();
  const lodge = lodges.find((l) => l.code === code);
  if (!lodge) notFound();

  const data = await api.listMovements(code, {
    page,
    pageSize: PAGE_SIZE,
    from_date,
    to_date,
    account,
  });

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const activeFilters = [from_date, to_date, account].filter(Boolean).length;

  return (
    <>
      <PageHeader
        title="Movimientos cargados"
        subtitle={
          activeFilters
            ? `${data.total.toLocaleString()} resultados con ${activeFilters} filtro${activeFilters > 1 ? "s" : ""} · página ${page} de ${totalPages}`
            : `${data.total.toLocaleString()} en total · página ${page} de ${totalPages}`
        }
      />
      <main id="main" className="px-8 py-6">
        <FilterBar
          code={code}
          from_date={from_date}
          to_date={to_date}
          account={account}
        />

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <Th>Fecha</Th>
                  <Th>Cuenta</Th>
                  <Th>Concepto</Th>
                  <Th>Subdiario</Th>
                  <Th>Proveedor</Th>
                  <Th className="text-right">Monto local</Th>
                  <Th className="text-right">Monto USD</Th>
                  <Th>Origen</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-12 text-center text-sm text-slate-700"
                    >
                      Sin movimientos para los filtros seleccionados.
                    </td>
                  </tr>
                ) : (
                  data.items.map((m) => (
                    <tr
                      key={m.id}
                      className="border-t border-slate-200 hover:bg-slate-50"
                    >
                      <Td className="text-slate-900 tabular-nums">{m.date}</Td>
                      <Td className="font-medium text-slate-900">
                        {m.account_code}
                      </Td>
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
                      <Td>
                        <span
                          className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                            m.source === "web"
                              ? "bg-emerald-100 text-emerald-900"
                              : "bg-slate-200 text-slate-900"
                          }`}
                        >
                          {m.source}
                        </span>
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
            page={page}
            totalPages={totalPages}
            from_date={from_date}
            to_date={to_date}
            account={account}
          />
        )}
      </main>
    </>
  );
}

function FilterBar({
  code,
  from_date,
  to_date,
  account,
}: {
  code: string;
  from_date?: string;
  to_date?: string;
  account?: string;
}) {
  const hasFilters = Boolean(from_date || to_date || account);
  return (
    <form
      method="get"
      action={`/lodges/${code}/movimientos`}
      className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <Field label="Desde" htmlFor="from_date">
        <input
          id="from_date"
          name="from_date"
          type="date"
          defaultValue={from_date ?? ""}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        />
      </Field>
      <Field label="Hasta" htmlFor="to_date">
        <input
          id="to_date"
          name="to_date"
          type="date"
          defaultValue={to_date ?? ""}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        />
      </Field>
      <Field label="Código de cuenta" htmlFor="account">
        <input
          id="account"
          name="account"
          type="text"
          placeholder="ej. 5250"
          defaultValue={account ?? ""}
          className="w-32 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        />
      </Field>
      <button
        type="submit"
        className="rounded-lg bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
      >
        Aplicar
      </button>
      {hasFilters && (
        <Link
          href={`/lodges/${code}/movimientos`}
          className="rounded-lg border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Limpiar
        </Link>
      )}
    </form>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] font-semibold uppercase tracking-wide text-slate-700"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function Pagination({
  code,
  page,
  totalPages,
  from_date,
  to_date,
  account,
}: {
  code: string;
  page: number;
  totalPages: number;
  from_date?: string;
  to_date?: string;
  account?: string;
}) {
  const buildHref = (p: number) => {
    const qs = new URLSearchParams();
    qs.set("page", String(p));
    if (from_date) qs.set("from_date", from_date);
    if (to_date) qs.set("to_date", to_date);
    if (account) qs.set("account", account);
    return `/lodges/${code}/movimientos?${qs.toString()}`;
  };
  return (
    <nav
      aria-label="Paginación"
      className="mt-4 flex items-center justify-between text-sm"
    >
      <div className="text-slate-700">
        Página <span className="font-semibold text-slate-900">{page}</span> de{" "}
        <span className="font-semibold text-slate-900">{totalPages}</span>
      </div>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link
            href={buildHref(page - 1)}
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
            href={buildHref(page + 1)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            Siguiente →
          </Link>
        ) : (
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-400">
            Siguiente →
          </span>
        )}
      </div>
    </nav>
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
  return <td className={`px-4 py-3 ${className}`}>{children}</td>;
}
