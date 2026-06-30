"""Cálculo de gasto por (lodge, cuenta, mes) y por rubro agrupado.

Dos niveles de agregación:

1) Por cuenta individual: suma de movimientos en USD por (lodge, account_code, month).
   Esto es el detalle granular para la auditoría.

2) Por rubro (agrupando varias cuentas) — para empatar con el Budget Comparativo,
   donde el budget está expresado por GRUPO de cuentas (ej. 'Food & Wine' = 5250+5251+5213+5291+5289).

Normalización por bednight: el costo USD del rubro / BN real season-to-date.
Para una vista mes-a-mes, usamos BN mensual si lo tenemos; si no, se omite.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from ..models import BudgetLine, Movement


@dataclass(frozen=True)
class AccountMonthlySpend:
    lodge_code: str
    account_code: str
    account_name: str
    month_key: str        # "2026-04" (vacío = sin fecha)
    amount_usd: float
    n_movements: int


@dataclass(frozen=True)
class RubroComparison:
    """Comparativo budget-vs-real para un rubro del Budget Comparativo.

    El budget per_bn y real per_bn vienen pre-calculados desde la planilla;
    el real_calculado_usd es nuestro recálculo agregando movimientos para
    auditar que coincide con el real declarado.
    """
    lodge_code: str
    rubro: str
    criterio: Optional[str]
    account_codes: tuple[str, ...]
    budget_usd: Optional[float]
    real_usd_declarado: Optional[float]
    real_usd_calculado: float
    bn: Optional[float]
    budget_per_bn: Optional[float]
    real_per_bn: Optional[float]
    variance_per_bn: Optional[float]   # real - budget (USD/BN)
    variance_pct: Optional[float]      # (real - budget) / budget
    observacion: Optional[str]
    is_income: bool = False            # True para rubros de Other Income (Shop, Extras, Gun Rental)
    rubro_id: Optional[str] = None     # UUID del rubro en DB — para drilldown desde el dashboard


def aggregate_by_account_month(
    movs: Iterable[Movement],
) -> list[AccountMonthlySpend]:
    """Suma USD por (lodge, account, month_key). Filas sin month_key se omiten."""
    buckets: dict[tuple, list[Movement]] = defaultdict(list)
    for m in movs:
        if not m.month_key:
            continue
        buckets[(m.lodge_code, m.account_code, m.month_key)].append(m)
    out = []
    for (lodge, acc, mk), bucket in buckets.items():
        total = sum(m.amount_usd for m in bucket)
        name = bucket[0].account_name
        out.append(AccountMonthlySpend(
            lodge_code=lodge,
            account_code=acc,
            account_name=name,
            month_key=mk,
            amount_usd=total,
            n_movements=len(bucket),
        ))
    out.sort(key=lambda r: (r.lodge_code, r.month_key, r.account_code))
    return out


def aggregate_by_account_total(
    movs: Iterable[Movement], lodge_code: str | None = None,
) -> dict[str, float]:
    """Suma USD por account_code (sin desglose mensual). Para empatar con totales del Budget Comparativo."""
    out: dict[str, float] = defaultdict(float)
    for m in movs:
        if lodge_code and m.lodge_code != lodge_code:
            continue
        out[m.account_code] += m.amount_usd
    return dict(out)


def compare_rubro_to_budget(
    budget_lines: Iterable[BudgetLine],
    real_by_account: dict[str, float],
    bednights: Optional[float],
) -> list[RubroComparison]:
    """Empareja cada línea del Budget Comparativo con la suma de sus cuentas en el real."""
    out = []
    for line in budget_lines:
        real_calc = sum(real_by_account.get(c, 0.0) for c in line.account_codes)
        var_pct = None
        if line.budget_usd not in (None, 0):
            var_pct = (real_calc - line.budget_usd) / line.budget_usd
        var_per_bn = None
        if line.budget_per_bn is not None and line.real_per_bn is not None:
            var_per_bn = line.real_per_bn - line.budget_per_bn
        out.append(RubroComparison(
            lodge_code=line.lodge_code,
            rubro=line.rubro,
            criterio=line.criterio,
            account_codes=line.account_codes,
            budget_usd=line.budget_usd,
            real_usd_declarado=line.real_usd,
            real_usd_calculado=real_calc,
            bn=bednights,
            budget_per_bn=line.budget_per_bn,
            real_per_bn=line.real_per_bn,
            variance_per_bn=var_per_bn,
            variance_pct=var_pct,
            observacion=line.observacion,
        ))
    return out
