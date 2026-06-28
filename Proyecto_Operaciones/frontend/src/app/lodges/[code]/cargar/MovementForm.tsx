/** Formulario reactivo de carga de movimiento.
 * 4 secciones según §7 del plan: datos, montos, comprobante, detalle.
 */
"use client";
import { api, ApiError } from "@/lib/api";
import type { AccountOption, MovementCreate } from "@/lib/types";
import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

const SUBDIARIOS = ["CAJA", "BANCOS", "VENTAS", "COMPRAS", "ASIENTOS"];

type Msg =
  | { kind: "ok"; movementId: string; amountUsd: string }
  | { kind: "error"; text: string }
  | null;

export default function MovementForm({
  lodgeCode,
  currency,
  accounts,
}: {
  lodgeCode: string;
  currency: string;
  accounts: AccountOption[];
}) {
  const [today] = useState(() => new Date().toISOString().slice(0, 10));
  const [date, setDate] = useState(today);
  const [accountCode, setAccountCode] = useState("");
  const [subdiario, setSubdiario] = useState("");
  const [concept, setConcept] = useState("");
  const [amountLocal, setAmountLocal] = useState("");
  const [fxRate, setFxRate] = useState("1450");
  const [comprobante, setComprobante] = useState("");
  const [proveedor, setProveedor] = useState("");
  const [taxId, setTaxId] = useState("");
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [observation, setObservation] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const amountUsdPreview = useMemo(() => {
    const a = parseFloat(amountLocal);
    const f = parseFloat(fxRate);
    if (isNaN(a) || isNaN(f) || f <= 0) return "—";
    return `$${(a / f).toFixed(2)}`;
  }, [amountLocal, fxRate]);

  const grouped = useMemo(() => {
    const g: Record<string, AccountOption[]> = {};
    for (const a of accounts) {
      const key = a.rubro_secundario || "(sin rubro)";
      (g[key] ||= []).push(a);
    }
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [accounts]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    setSubmitting(true);
    const payload: MovementCreate = {
      date,
      account_code: accountCode,
      amount_local: amountLocal,
      fx_rate: fxRate,
      currency,
      subdiario,
      concept: concept || null,
      description: description || null,
      comprobante: comprobante || null,
      proveedor: proveedor || null,
      tax_id: taxId || null,
      observation: observation || null,
      attachment_url: attachmentUrl || null,
    };
    try {
      const created = await api.createMovement(lodgeCode, payload);
      setMsg({
        kind: "ok",
        movementId: created.id,
        amountUsd: created.amount_usd,
      });
      setAccountCode("");
      setSubdiario("");
      setConcept("");
      setAmountLocal("");
      setComprobante("");
      setProveedor("");
      setTaxId("");
      setAttachmentUrl("");
      setObservation("");
      setDescription("");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      const text =
        e instanceof ApiError
          ? Array.isArray(e.detail)
            ? (e.detail as Array<{ loc: string[]; msg: string }>)
                .map((d) => `${d.loc.join(".")}: ${d.msg}`)
                .join(" · ")
            : typeof e.detail === "string"
              ? e.detail
              : e.message
          : (e as Error).message;
      setMsg({ kind: "error", text });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {msg?.kind === "ok" && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-900">
          <span>
            <strong>✓ Movimiento cargado</strong> · USD {msg.amountUsd} · El
            dashboard se actualizó.
          </span>
          <Link
            href={`/lodges/${lodgeCode}/dashboard`}
            className="flex-shrink-0 rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-emerald-800"
          >
            Ver dashboard →
          </Link>
        </div>
      )}
      {msg?.kind === "error" && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-900">
          <strong>✗ Error:</strong> {msg.text}
        </div>
      )}

      <Section
        title="1 · Datos del movimiento"
        desc="Información básica del asiento contable."
      >
        <Row cols={2}>
          <Field label="Fecha" required>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              className={inputCls}
            />
          </Field>
          <Field label="Subdiario" required>
            <select
              value={subdiario}
              onChange={(e) => setSubdiario(e.target.value)}
              required
              className={inputCls}
            >
              <option value="">— elegir —</option>
              {SUBDIARIOS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        </Row>
        <Row>
          <Field
            label="Cuenta contable"
            required
            hint="Agrupada por rubro. Si la cuenta no aparece, pedile al admin que la agregue al plan."
          >
            <select
              value={accountCode}
              onChange={(e) => setAccountCode(e.target.value)}
              required
              className={inputCls}
            >
              <option value="">— elegir cuenta —</option>
              {grouped.map(([rubro, accs]) => (
                <optgroup key={rubro} label={rubro}>
                  {accs.map((a) => (
                    <option key={a.code} value={a.code}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </Field>
        </Row>
        <Row>
          <Field label="Concepto (opcional)">
            <input
              type="text"
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              maxLength={255}
              placeholder="ej. Compra de comida proveedor X"
              className={inputCls}
            />
          </Field>
        </Row>
      </Section>

      <Section
        title="2 · Montos"
        desc="Cargá en moneda local; el sistema calcula el USD."
      >
        <Row cols={3}>
          <Field
            label={`Monto local (${currency})`}
            required
            hint="Acepta negativos (devoluciones/reversas)."
          >
            <input
              type="number"
              step="0.01"
              value={amountLocal}
              onChange={(e) => setAmountLocal(e.target.value)}
              required
              className={inputCls}
            />
          </Field>
          <Field
            label="Tipo de cambio"
            required
            hint="Default: TC del budget de la temporada."
          >
            <input
              type="number"
              step="0.0001"
              min="0.0001"
              value={fxRate}
              onChange={(e) => setFxRate(e.target.value)}
              required
              className={inputCls}
            />
          </Field>
          <Field label="Monto USD (calculado)">
            <input
              type="text"
              readOnly
              value={amountUsdPreview}
              className={`${inputCls} bg-slate-100 font-semibold text-slate-900`}
            />
          </Field>
        </Row>
      </Section>

      <Section title="3 · Comprobante" desc="Documentación para auditar el gasto.">
        <Row cols={2}>
          <Field label="Número de comprobante">
            <input
              type="text"
              value={comprobante}
              onChange={(e) => setComprobante(e.target.value)}
              maxLength={64}
              placeholder="ej. F B 000000007219"
              className={inputCls}
            />
          </Field>
          <Field label="Proveedor / Sujeto">
            <input
              type="text"
              value={proveedor}
              onChange={(e) => setProveedor(e.target.value)}
              maxLength={255}
              placeholder="ej. Astillero Laffranchi"
              className={inputCls}
            />
          </Field>
        </Row>
        <Row cols={2}>
          <Field label="ID fiscal (CUIT / RUT)">
            <input
              type="text"
              value={taxId}
              onChange={(e) => setTaxId(e.target.value)}
              maxLength={32}
              placeholder="ej. 30-12345678-9"
              className={inputCls}
            />
          </Field>
          <Field
            label="URL adjunto (opcional)"
            hint="Subida directa de archivos viene en un próximo slice."
          >
            <input
              type="url"
              value={attachmentUrl}
              onChange={(e) => setAttachmentUrl(e.target.value)}
              placeholder="https://..."
              className={inputCls}
            />
          </Field>
        </Row>
      </Section>

      <Section
        title="4 · Detalle (opcional)"
        desc="Notas y referencias para auditoría futura."
      >
        <Row>
          <Field label="Observación">
            <textarea
              value={observation}
              onChange={(e) => setObservation(e.target.value)}
              placeholder="Texto libre — la observación queda visible en el dashboard."
              className={`${inputCls} min-h-20`}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Descripción del comprobante">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detalle adicional del asiento."
              className={`${inputCls} min-h-20`}
            />
          </Field>
        </Row>
      </Section>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:bg-slate-400"
        >
          {submitting ? "Cargando..." : "Cargar movimiento"}
        </button>
        <button
          type="reset"
          onClick={() => {
            setDate(today);
            setAccountCode("");
            setSubdiario("");
            setConcept("");
            setAmountLocal("");
            setFxRate("1450");
            setComprobante("");
            setProveedor("");
            setTaxId("");
            setAttachmentUrl("");
            setObservation("");
            setDescription("");
            setMsg(null);
          }}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Limpiar
        </button>
      </div>
    </form>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10";

function Section({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {desc && <p className="mt-0.5 mb-5 text-xs text-slate-600">{desc}</p>}
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Row({
  cols = 1,
  children,
}: {
  cols?: 1 | 2 | 3;
  children: React.ReactNode;
}) {
  const cls =
    cols === 3
      ? "md:grid-cols-3"
      : cols === 2
        ? "md:grid-cols-2"
        : "md:grid-cols-1";
  return <div className={`grid grid-cols-1 gap-4 ${cls}`}>{children}</div>;
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">
        {label}
        {required && <span className="ml-1 text-red-600">*</span>}
      </span>
      {children}
      {hint && <span className="text-xs text-slate-600">{hint}</span>}
    </label>
  );
}
