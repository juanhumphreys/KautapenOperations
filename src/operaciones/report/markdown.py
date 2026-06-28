"""Render del reporte de demo en Markdown y CSV."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable

from ..calc.flags import Flag
from ..calc.per_bednight import AccountMonthlySpend, RubroComparison


def _fmt_usd(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v:,.0f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1%}"


def write_rubro_csv(comparisons: Iterable[RubroComparison], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(comparisons)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "lodge", "rubro", "criterio", "cuentas",
            "budget_usd", "real_usd_declarado", "real_usd_calculado",
            "bn", "budget_per_bn", "real_per_bn",
            "variance_per_bn", "variance_pct", "observacion",
        ])
        for c in rows:
            w.writerow([
                c.lodge_code, c.rubro, c.criterio or "",
                "+".join(c.account_codes),
                c.budget_usd, c.real_usd_declarado, round(c.real_usd_calculado, 2),
                c.bn, c.budget_per_bn, c.real_per_bn,
                c.variance_per_bn, c.variance_pct, c.observacion or "",
            ])


def write_account_month_csv(spends: Iterable[AccountMonthlySpend], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lodge", "month", "account_code", "account_name", "usd", "n_movements"])
        for s in spends:
            w.writerow([
                s.lodge_code, s.month_key, s.account_code, s.account_name,
                round(s.amount_usd, 2), s.n_movements,
            ])


def write_flags_csv(flags: Iterable[Flag], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lodge", "rubro_or_account", "rule", "severity",
                    "value", "reason", "obs_cliente"])
        for fl in flags:
            w.writerow([
                fl.lodge_code, fl.rubro_or_account, fl.rule, fl.severity,
                fl.value, fl.reason, fl.obs_cliente or "",
            ])


def render_markdown(
    lodge_code: str,
    bn_real: float | None,
    bn_budget: float | None,
    comparisons: list[RubroComparison],
    flags: list[Flag],
    out_path: Path,
) -> None:
    """Reporte resumido para mostrar en el demo (curar a mano antes de presentar)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    L = []
    L.append(f"# Control de costos por bednight — {lodge_code}")
    L.append("")
    L.append(f"- BN real season-to-date: **{bn_real or '?'}**  ·  BN budget temporada: **{bn_budget or '?'}**")
    L.append(f"- Rubros comparados: **{len(comparisons)}**")
    L.append(f"- Flags generados: **{len(flags)}** "
             f"(alert: {sum(1 for f in flags if f.severity=='alert')}, "
             f"warn: {sum(1 for f in flags if f.severity=='warn')}, "
             f"info: {sum(1 for f in flags if f.severity=='info')})")
    L.append("")

    L.append("## Flags con observación manual del cliente (validación)")
    L.append("")
    L.append("Comparamos cada flag contra la columna *Observación* del Budget Comparativo "
             "del cliente. Si hay observación → el cliente también lo vio; sin observación → "
             "candidato a 'se les pasó'.")
    L.append("")
    L.append("| Severidad | Rubro | Desvío | Razón | Obs. cliente |")
    L.append("|---|---|---|---|---|")
    for f in sorted(flags, key=lambda x: (-_severity_rank(x.severity), -abs(x.value or 0))):
        if f.rule != "DESVIO_BUDGET":
            continue
        obs = (f.obs_cliente or "").replace("|", "\\|").replace("\n", " ")
        if len(obs) > 80:
            obs = obs[:77] + "..."
        L.append(f"| {f.severity} | {f.rubro_or_account} | {_fmt_pct(f.value)} | {f.reason} | {obs or '_sin observación_'} |")
    L.append("")

    L.append("## Comparativo budget-vs-real por rubro (todos los renglones)")
    L.append("")
    L.append("| Rubro | Cuentas | Budget USD | Real USD (decl.) | Real USD (calc.) | "
             "Budget USD/BN | Real USD/BN | Δ% |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in comparisons:
        L.append(
            f"| {c.rubro} | {'+'.join(c.account_codes)} | {_fmt_usd(c.budget_usd)} | "
            f"{_fmt_usd(c.real_usd_declarado)} | {_fmt_usd(c.real_usd_calculado)} | "
            f"{_fmt_usd(c.budget_per_bn)} | {_fmt_usd(c.real_per_bn)} | "
            f"{_fmt_pct(c.variance_pct)} |"
        )
    L.append("")

    L.append("## Saltos mes a mes (por cuenta)")
    L.append("")
    L.append("| Severidad | Cuenta | Desvío | Razón |")
    L.append("|---|---|---|---|")
    for f in sorted(flags, key=lambda x: (-_severity_rank(x.severity), -abs(x.value or 0))):
        if f.rule != "SALTO_MOM":
            continue
        L.append(f"| {f.severity} | {f.rubro_or_account} | {_fmt_pct(f.value)} | {f.reason} |")

    out_path.write_text("\n".join(L), encoding="utf-8")


def _severity_rank(s: str) -> int:
    return {"alert": 3, "warn": 2, "info": 1}.get(s, 0)
