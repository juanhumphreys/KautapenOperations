"""Service que arma el payload completo del dashboard desde la DB.

Reusa los modelos de cálculo de operaciones.calc.* (RubroComparison, Flag) para
mantener una sola fuente de verdad de la lógica. La diferencia con Fase 1 es
que aquí los datos vienen de la DB en vez de los Excel.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    Account, BudgetLine, Lodge, Movement, Observation, Region, Rubro,
    RubroAccount, Season,
)
from operaciones.calc.flags import Flag, flag_budget_deviations, flag_month_over_month
from operaciones.calc.per_bednight import AccountMonthlySpend, RubroComparison
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
    mom_flags: list[Flag]
    reconcile: list[ReconcileAccount]


@dataclass
class AccountBreakdown:
    """Un cuenta dentro de un rubro: cuánto se gastó en el período."""
    code: str
    name: str
    total_usd: float
    n_movements: int


@dataclass
class RubroDetailPayload:
    """Detalle de un rubro: budget vs real + breakdown por cuenta componente."""
    lodge_code: str
    lodge_name: str
    rubro_id: str
    rubro_name: str
    criterio: Optional[str]
    budget_usd: Optional[float]
    real_usd: float
    budget_per_bn: Optional[float]
    real_per_bn: Optional[float]
    variance_pct: Optional[float]
    bn_real: Optional[float]
    bn_budget: Optional[float]
    observation: Optional[str]
    is_income: bool
    accounts: list[AccountBreakdown]


@dataclass
class MonthlySpend:
    """USD gastado por una cuenta en un mes calendario."""
    month_key: str        # "2026-04"
    total_usd: float
    n_movements: int


@dataclass
class AccountDetailPayload:
    """Mini-dashboard de una cuenta: totales + breakdown mensual."""
    lodge_code: str
    lodge_name: str
    code: str
    name: str
    rubro_principal: Optional[str]
    rubro_secundario: Optional[str]
    rubro_final: Optional[str]
    is_income: bool
    total_usd: float
    n_movements: int
    first_date: Optional[str]
    last_date: Optional[str]
    monthly: list[MonthlySpend]


def _monthly_spend_by_account(
    session: Session, lodge: Lodge,
) -> list[AccountMonthlySpend]:
    """Agrupa movimientos por (cuenta, mes) en USD para alimentar el cálculo MoM.

    Replica el sign-flip de _real_usd_by_account: cuentas de Other Income se
    devuelven en positivo (las ventas se asientan negativas en el libro mayor).
    """
    rows = session.execute(
        select(
            Movement.account_code,
            Account.name,
            Account.rubro_principal,
            func.to_char(Movement.date, "YYYY-MM").label("month_key"),
            func.sum(Movement.amount_usd).label("total"),
            func.count().label("n"),
        )
        .join(Account, Account.code == Movement.account_code)
        .where(Movement.lodge_id == lodge.id, Movement.void == False)
        .group_by(
            Movement.account_code,
            Account.name,
            Account.rubro_principal,
            "month_key",
        )
    ).all()
    out: list[AccountMonthlySpend] = []
    for code, name, principal, month_key, total, n in rows:
        sign = -1 if principal == "Other Income" else 1
        out.append(AccountMonthlySpend(
            lodge_code=lodge.code,
            account_code=code,
            account_name=name,
            month_key=month_key or "",
            amount_usd=float(total) * sign,
            n_movements=int(n),
        ))
    return out


def _real_usd_by_account(session: Session, lodge_id) -> dict[str, Decimal]:
    """Suma USD por cuenta para un lodge (excluyendo voids).

    Las cuentas de ingreso (rubro_principal='Other Income') en el libro mayor están
    asentadas con signo negativo (créditos). El Excel del cliente las invierte con
    `-SUMIF(...)` para que el "Real" sea comparable al budget. Replicamos lo mismo
    acá: si la cuenta es de ingreso, le invertimos el signo a la suma.
    """
    rows = session.execute(
        select(
            Movement.account_code,
            Account.rubro_principal,
            func.sum(Movement.amount_usd),
        )
        .join(Account, Account.code == Movement.account_code)
        .where(Movement.lodge_id == lodge_id, Movement.void == False)
        .group_by(Movement.account_code, Account.rubro_principal)
    ).all()
    result: dict[str, Decimal] = {}
    for code, principal, total in rows:
        sign = -1 if principal == "Other Income" else 1
        result[code] = Decimal(str(total)) * sign
    return result


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
            comparisons=[], flags=[], mom_flags=[], reconcile=[],
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

    # Para saber si un rubro es de ingreso, miramos rubro_principal de sus cuentas.
    account_principal: dict[str, str] = {
        a.code: (a.rubro_principal or "")
        for a in session.scalars(select(Account)).all()
    }

    comparisons: list[RubroComparison] = []
    for rubro in rubros:
        codes = tuple(rubro_accounts.get(rubro.id, []))
        bl = budget_by_rubro.get(rubro.id)
        real_calc = sum((real_by_acc.get(c, Decimal(0)) for c in codes), Decimal(0))
        # Un rubro es de ingreso si alguna de sus cuentas componentes está marcada
        # como "Other Income" en el plan de cuentas. Suficiente con uno: el cliente
        # nunca mezcla ingresos con gastos en un mismo rubro del Comparativo.
        is_income = any(
            account_principal.get(c, "") == "Other Income" for c in codes
        )
        budget_per_bn = float(bl.budget_per_bn) if bl and bl.budget_per_bn else None
        # Para mantener la métrica USD/BN del dashboard, recalculamos real_per_bn
        # como real_calc / bn_real (si tenemos BN).
        real_per_bn = None
        if bn_real_dec and bn_real_dec != 0:
            real_per_bn = float(real_calc / bn_real_dec)
        budget_usd = float(bl.budget_usd) if bl and bl.budget_usd else None
        # variance_pct unificada a per-BN: misma fórmula que usan los flags en
        # operaciones.calc.flags.flag_budget_deviations. Antes era USD-based y
        # producía números distintos al chart para rubros "Acumulado" (donde BN
        # real ≠ BN budget). Métrica preferida del cliente: gasto "por vez".
        var_pct = None
        if budget_per_bn not in (None, 0) and real_per_bn is not None:
            var_pct = (real_per_bn - budget_per_bn) / budget_per_bn
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
            is_income=is_income,
            rubro_id=str(rubro.id),
        ))

    flags = flag_budget_deviations(comparisons)

    # MoM: saltos mes-a-mes por cuenta, agregando movimientos por (cuenta, mes).
    monthly = _monthly_spend_by_account(session, lodge)
    mom_flags = flag_month_over_month(monthly)

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
        mom_flags=mom_flags,
        reconcile=reconcile,
    )


def build_rubro_detail(
    session: Session, lodge_code: str, rubro_id: str,
) -> Optional[RubroDetailPayload]:
    """Detalle de un rubro: KPIs + breakdown por cuenta componente.

    Devuelve None si el lodge o el rubro no existen.
    """
    try:
        rubro_uuid = UUID(rubro_id)
    except ValueError:
        return None
    lodge = session.scalar(select(Lodge).where(Lodge.code == lodge_code))
    rubro = session.get(Rubro, rubro_uuid)
    if lodge is None or rubro is None:
        return None

    season = session.scalar(
        select(Season).where(Season.lodge_id == lodge.id).order_by(Season.year_start.desc())
    )
    bn_real_dec = season.bn_real_std if season else None
    bn_budget = float(season.bn_budget) if season and season.bn_budget else None

    bl = None
    if season:
        bl = session.scalar(
            select(BudgetLine).where(
                BudgetLine.season_id == season.id,
                BudgetLine.rubro_id == rubro.id,
            )
        )
    budget_usd = float(bl.budget_usd) if bl and bl.budget_usd else None
    budget_per_bn = float(bl.budget_per_bn) if bl and bl.budget_per_bn else None

    codes = [
        ra.account_code for ra in session.scalars(
            select(RubroAccount).where(RubroAccount.rubro_id == rubro.id)
        ).all()
    ]

    # Suma por cuenta (con sign-flip para ingresos), reusa la helper del dashboard.
    real_by_acc = _real_usd_by_account(session, lodge.id)

    # Conteo de movimientos por cuenta del rubro.
    n_by_acc: dict[str, int] = {}
    if codes:
        rows = session.execute(
            select(Movement.account_code, func.count())
            .where(
                Movement.lodge_id == lodge.id,
                Movement.void == False,
                Movement.account_code.in_(codes),
            )
            .group_by(Movement.account_code)
        ).all()
        n_by_acc = {code: int(n) for code, n in rows}

    accounts_info = {}
    if codes:
        accounts_info = {
            a.code: a for a in session.scalars(
                select(Account).where(Account.code.in_(codes))
            ).all()
        }
    is_income = any(
        (accounts_info.get(c).rubro_principal if c in accounts_info else "") == "Other Income"
        for c in codes
    )

    breakdown = [
        AccountBreakdown(
            code=c,
            name=accounts_info[c].name if c in accounts_info else c,
            total_usd=float(real_by_acc.get(c, Decimal(0))),
            n_movements=n_by_acc.get(c, 0),
        )
        for c in codes
    ]
    breakdown.sort(key=lambda b: -abs(b.total_usd))

    real_calc = float(sum(b.total_usd for b in breakdown))
    real_per_bn = (
        real_calc / float(bn_real_dec)
        if bn_real_dec and float(bn_real_dec) != 0 else None
    )
    var_pct = None
    if budget_per_bn not in (None, 0) and real_per_bn is not None:
        var_pct = (real_per_bn - budget_per_bn) / budget_per_bn

    obs = session.scalar(
        select(Observation).where(
            Observation.lodge_id == lodge.id,
            Observation.rubro_id == rubro.id,
            Observation.period == "season-to-date",
        )
    )

    return RubroDetailPayload(
        lodge_code=lodge.code,
        lodge_name=lodge.name,
        rubro_id=str(rubro.id),
        rubro_name=rubro.name,
        criterio=rubro.criterio,
        budget_usd=budget_usd,
        real_usd=real_calc,
        budget_per_bn=budget_per_bn,
        real_per_bn=real_per_bn,
        variance_pct=var_pct,
        bn_real=float(bn_real_dec) if bn_real_dec else None,
        bn_budget=bn_budget,
        observation=obs.body if obs else None,
        is_income=is_income,
        accounts=breakdown,
    )


def build_account_detail(
    session: Session, lodge_code: str, account_code: str,
) -> Optional[AccountDetailPayload]:
    """Mini-dashboard de una cuenta: total USD, breakdown mensual, etc.

    Devuelve None si el lodge o la cuenta no existen.
    """
    lodge = session.scalar(select(Lodge).where(Lodge.code == lodge_code))
    account = session.get(Account, account_code)
    if lodge is None or account is None:
        return None

    is_income = (account.rubro_principal or "") == "Other Income"
    sign = -1 if is_income else 1

    # Stats agregados (total, count, fechas extremas).
    row = session.execute(
        select(
            func.sum(Movement.amount_usd),
            func.count(),
            func.min(Movement.date),
            func.max(Movement.date),
        )
        .where(
            Movement.lodge_id == lodge.id,
            Movement.account_code == account_code,
            Movement.void == False,
        )
    ).one()
    total_raw, n_mov, first_dt, last_dt = row
    total_usd = float(total_raw or 0) * sign
    n_movements = int(n_mov or 0)

    # Breakdown mensual.
    rows = session.execute(
        select(
            func.to_char(Movement.date, "YYYY-MM").label("month_key"),
            func.sum(Movement.amount_usd),
            func.count(),
        )
        .where(
            Movement.lodge_id == lodge.id,
            Movement.account_code == account_code,
            Movement.void == False,
        )
        .group_by("month_key")
        .order_by("month_key")
    ).all()
    monthly = [
        MonthlySpend(
            month_key=mk or "",
            total_usd=float(amt or 0) * sign,
            n_movements=int(n or 0),
        )
        for mk, amt, n in rows
    ]

    return AccountDetailPayload(
        lodge_code=lodge.code,
        lodge_name=lodge.name,
        code=account.code,
        name=account.name,
        rubro_principal=account.rubro_principal or None,
        rubro_secundario=account.rubro_secundario or None,
        rubro_final=account.rubro_final or None,
        is_income=is_income,
        total_usd=total_usd,
        n_movements=n_movements,
        first_date=first_dt.isoformat() if first_dt else None,
        last_date=last_dt.isoformat() if last_dt else None,
        monthly=monthly,
    )
