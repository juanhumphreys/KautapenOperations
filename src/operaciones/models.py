"""Modelos de dominio. Todo en USD; el ARS sólo se mantiene para auditoría."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Account:
    """Una fila del Plan de Cuentas Link Armado."""
    code: str           # ej. "5250"
    name: str           # "Comidas y refrigerios"
    rubro_principal: str   # "Operative Expenses"
    rubro_secundario: str  # "Food & Wine"
    rubro_final: str       # "Food & Wine"


@dataclass(frozen=True)
class Movement:
    """Una fila de Mov_Analizados_<mes>. Lo único que normalizamos a USD."""
    lodge_code: str      # "DEL" / "CAR" / "SJ"
    lodge_name: str      # "Delta"
    account_code: str    # "5250"
    account_name: str    # "Comidas y refrigerios"
    concept: str         # rubro libre que figura en el movimiento ("Food & Wine")
    amount_usd: float
    amount_ars: float
    fx_rate: Optional[float]   # TC del movimiento
    date: Optional[date]
    month_key: str       # "2026-04"  (yyyy-mm para agregar)
    source_sheet: str


@dataclass(frozen=True)
class Denominators:
    """BN/Pax/FD para (lodge, ventana temporal). El demo trabaja a temporada,
    pero la estructura admite mes una vez que tengamos el dato."""
    lodge_code: str
    period: str          # "season" para budget anual; "2026-04" si llega mensual
    bednights: Optional[float]
    pax: Optional[float]
    fishing_days: Optional[float]
    source: str          # "budget" | "real" | "comparativo"


@dataclass(frozen=True)
class BudgetLine:
    """Una fila de Budget Comparativo: budget y real por cuenta agrupada."""
    lodge_code: str
    rubro: str                  # nombre del rubro tal cual figura ("Food & Wine")
    criterio: Optional[str]     # "BN" | "Acumulado" | None — fija el denominador
    account_codes: tuple[str, ...]   # cuentas que componen el rubro
    budget_usd: Optional[float]
    real_usd: Optional[float]
    budget_per_bn: Optional[float]
    real_per_bn: Optional[float]
    observacion: Optional[str]
    source_row: int             # para trazabilidad
