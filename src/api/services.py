"""Service que arma el payload completo del dashboard desde la DB.

Reusa los modelos de cálculo de operaciones.calc.* (RubroComparison, Flag) para
mantener una sola fuente de verdad de la lógica. La diferencia con Fase 1 es
que aquí los datos vienen de la DB en vez de los Excel.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    Account, BudgetLine, Lodge, Movement, Observation, Region, Rubro,
    RubroAccount, Season,
)
from operaciones.calc.flags import flag_budget_deviations
from operaciones.calc.per_bednight import RubroComparison
from operaciones.calc.reconcile import ReconcileAccount


@dataclass
class DashboardPayload:
    """Lo que el dashboard necesita para renderizarse, ya armado desde DB."""
    lodge_code: str
    lodge_name: str
    region: Optional[str]
    bn_real: Optional[float]
    bn_budget: Optional[float]
    months_elapsed: Optional[float]
    months_total: Optional[float]
    comparisons: list[RubroComparison]
    flags: list
    reconcile: list[ReconcileAccount]


def _real_usd_by_account(session: Session, lodge_id) -> dict[str, Decimal]:
    """Suma USD por cuenta para un lodge (excluyendo voids)."""
    rows = session.execute(
        select(Movement.account_code, func.sum(Movement.amount_usd))
        .where(Movement.lodge_id == lodge_id, Movement.void == False)
        .group_by(Movement.account_code)
    ).all()
    return {code: Decimal(str(total)) for code, total in rows}


def build_dashboard(session: Session, lodge_code: str) -> Optional[DashboardPayload]:
    """Arma el payload completo del dashboard para un lodge.
    Devuelve None si el lodge no existe.
    """
    lodge = session.scalar(select(Lodge).where(Lodge.code == lodge_code))
    if lodge is None:
        return None

    region = session.get(Region, lodge.region_id) if lodge.region_id else None
    season = session.scalar(
        select(Season).where(Season.lodge_id == lodge.id).order_by(Season.year_start.desc())
    )
    if season is None:
        return DashboardPayload(
            lodge_code=lodge.code, lodge_name=lodge.name,
            region=region.name if region else None,
            bn_real=None, bn_budget=None,
            months_elapsed=None, months_total=None,
            comparisons=[], flags=[], reconcile=[],
        )

    bn_real_dec = season.bn_real_std

    # Cargamos todas las líneas del Budget Comparativo (BudgetLine + obs),
    # rubros y sus cuentas, y la suma de movimientos.
    real_by_acc = _real_usd_by_account(session, lodge.id)

    rubros = session.scalars(select(Rubro).order_by(Rubro.display_order)).all()
    obs_by_rubro = {
        o.rubro_id: o.body
        for o in session.scalars(
            select(Observation).where(
                Observation.lodge_id == lodge.id,
                Observation.period == "season-to-date",
            )
        ).all()
    }
    budget_by_rubro = {
        bl.rubro_id: bl
        for bl in session.scalars(
            select(BudgetLine).where(BudgetLine.season_id == season.id)
        ).all()
    }

    # Cuentas componentes de cada rubro
    rubro_accounts: dict = {}
    for ra in session.scalars(select(RubroAccount)).all():
        rubro_accounts.setdefault(ra.rubro_id, []).append(ra.account_code)

    comparisons: list[RubroComparison] = []
    for rubro in rubros:
        codes = tuple(rubro_accounts.get(rubro.id, []))
        bl = budget_by_rubro.get(rubro.id)
        real_calc = sum((real_by_acc.get(c, Decimal(0)) for c in codes), Decimal(0))
        budget_per_bn = float(bl.budget_per_bn) if bl and bl.budget_per_bn else None
        # Para mantener la métrica USD/BN del dashboard, recalculamos real_per_bn
        # como real_calc / bn_real (si tenemos BN).
        real_per_bn = None
        if bn_real_dec and bn_real_dec != 0:
            real_per_bn = float(real_calc / bn_real_dec)
        budget_usd = float(bl.budget_usd) if bl and bl.budget_usd else None
        var_pct = None
        if budget_usd not in (None, 0):
            var_pct = (float(real_calc) - budget_usd) / budget_usd
        var_per_bn = (
            (real_per_bn - budget_per_bn)
            if (real_per_bn is not None and budget_per_bn is not None)
            else None
        )
        comparisons.append(RubroComparison(
            lodge_code=lodge.code,
            rubro=rubro.name,
            criterio=rubro.criterio,
            account_codes=codes,
            budget_usd=budget_usd,
            real_usd_declarado=float(real_calc),
            real_usd_calculado=float(real_calc),
            bn=float(bn_real_dec) if bn_real_dec else None,
            budget_per_bn=budget_per_bn,
            real_per_bn=real_per_bn,
            variance_per_bn=var_per_bn,
            variance_pct=var_pct,
            observacion=obs_by_rubro.get(rubro.id),
        ))

    flags = flag_budget_deviations(comparisons)

    # Reconcile cuenta-por-cuenta: por ahora marcamos como "ok" todo lo que viene
    # de DB (no tenemos Resumen_Base en DB todavía). Cuando lo migremos, se
    # compara contra lo declarado.
    accounts = session.scalars(select(Account)).all()
    reconcile = [
        ReconcileAccount(
            lodge_code=lodge.code,
            account_code=a.code,
            account_name=a.name,
            rubro=a.rubro_secundario,
            calculated_usd=float(real_by_acc.get(a.code, Decimal(0))),
            declared_usd=float(real_by_acc.get(a.code, Decimal(0))),   # sin Resumen_Base, se asume igual
            gap_usd=0.0,
            gap_pct=0.0,
        )
        for a in accounts
        if a.code in real_by_acc
    ]

    return DashboardPayload(
        lodge_code=lodge.code,
        lodge_name=lodge.name,
        region=region.name if region else None,
        bn_real=float(bn_real_dec) if bn_real_dec else None,
        bn_budget=float(season.bn_budget) if season.bn_budget else None,
        months_elapsed=float(season.months_elapsed) if season.months_elapsed else None,
        months_total=float(season.months_total) if season.months_total else None,
        comparisons=comparisons,
        flags=flags,
        reconcile=reconcile,
    )
