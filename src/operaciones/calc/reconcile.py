"""Reconciliación: comparar nuestro real (sum de movimientos) vs el real declarado
por el cliente en 'Resumen_Base'. Detectar cuentas donde difieren y listar los
movimientos sospechosos.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from ..models import Movement


@dataclass(frozen=True)
class ReconcileAccount:
    """Comparación a nivel cuenta-total (acumulado de toda la temporada)."""
    lodge_code: str
    account_code: str
    account_name: str
    rubro: str
    calculated_usd: float    # suma de nuestros movimientos
    declared_usd: float      # lo que el cliente puso en Resumen_Base
    gap_usd: float           # declared - calculated (positivo = ellos restaron a mano)
    gap_pct: float           # gap / declared


@dataclass(frozen=True)
class ReconcileAccountMonth:
    """Comparación a nivel cuenta-mes."""
    lodge_code: str
    account_code: str
    month_key: str
    calculated_usd: float
    declared_usd: float
    gap_usd: float


def reconcile_total(
    movements: Iterable[Movement],
    declared_total: dict[str, float],   # {account_code: usd}
    accounts_meta: dict[str, tuple[str, str]],   # {code: (name, rubro)}
    lodge_code: str = "DEL",
    min_abs_usd: float = 1.0,   # ignora gaps menores a $1
) -> list[ReconcileAccount]:
    calc = defaultdict(float)
    for m in movements:
        if m.lodge_code != lodge_code:
            continue
        calc[m.account_code] += m.amount_usd

    all_codes = set(calc) | set(declared_total)
    out = []
    for code in all_codes:
        c = calc.get(code, 0.0)
        d = declared_total.get(code, 0.0)
        gap = d - c
        if abs(gap) < min_abs_usd and abs(c) < min_abs_usd and abs(d) < min_abs_usd:
            continue
        name, rubro = accounts_meta.get(code, ("", ""))
        gap_pct = gap / d if d else (1.0 if c else 0.0)
        out.append(ReconcileAccount(
            lodge_code=lodge_code,
            account_code=code,
            account_name=name,
            rubro=rubro,
            calculated_usd=c,
            declared_usd=d,
            gap_usd=gap,
            gap_pct=gap_pct,
        ))
    out.sort(key=lambda r: -abs(r.gap_usd))
    return out


def reconcile_monthly(
    movements: Iterable[Movement],
    declared_month: dict[tuple[str, str], float],
    lodge_code: str = "DEL",
    min_abs_usd: float = 50.0,
) -> list[ReconcileAccountMonth]:
    calc = defaultdict(float)
    for m in movements:
        if m.lodge_code != lodge_code or not m.month_key:
            continue
        calc[(m.account_code, m.month_key)] += m.amount_usd
    out = []
    keys = set(calc) | set(declared_month)
    for key in keys:
        c = calc.get(key, 0.0)
        d = declared_month.get(key, 0.0)
        gap = d - c
        if abs(gap) < min_abs_usd:
            continue
        out.append(ReconcileAccountMonth(
            lodge_code=lodge_code,
            account_code=key[0],
            month_key=key[1],
            calculated_usd=c,
            declared_usd=d,
            gap_usd=gap,
        ))
    out.sort(key=lambda r: -abs(r.gap_usd))
    return out


def suspicious_movements(
    movements: Iterable[Movement],
    account_code: str,
    lodge_code: str = "DEL",
    top_n: int = 10,
) -> list[Movement]:
    """Devuelve los movimientos más grandes (en valor absoluto) de una cuenta —
    los candidatos para inspección manual cuando hay gap. Las descripciones suelen
    delatar si es una provisión, reversa o ajuste de cierre.
    """
    movs = [m for m in movements
            if m.lodge_code == lodge_code and m.account_code == account_code]
    movs.sort(key=lambda m: -abs(m.amount_usd))
    return movs[:top_n]
