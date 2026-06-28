"""Seed de la base con la dimensión: plan de cuentas, rubros, regiones, Delta.

Lee del Excel actual y lo persiste. Idempotente: si vuelve a correr no duplica.

Uso:
    python scripts/seed_db.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from decimal import Decimal

from sqlalchemy import delete, select

from db.models import (
    Account, BudgetLine, Lodge, Observation, Region, Rubro, RubroAccount, Season,
)
from db.session import get_session
from operaciones.discovery import discover_delta
from operaciones.ingest.budget_comparativo import parse_comparativo
from operaciones.ingest.budget_lodge import parse_lodge_budget
from operaciones.ingest.plan_cuentas import load_accounts


def upsert_region(session, code: str, name: str, default_currency: str) -> Region:
    existing = session.scalar(select(Region).where(Region.code == code))
    if existing:
        return existing
    region = Region(code=code, name=name, default_currency=default_currency)
    session.add(region)
    session.flush()
    return region


def upsert_lodge(session, code: str, name: str, region_id, currency: str) -> Lodge:
    existing = session.scalar(select(Lodge).where(Lodge.code == code))
    if existing:
        return existing
    lodge = Lodge(code=code, name=name, region_id=region_id, currency=currency)
    session.add(lodge)
    session.flush()
    return lodge


def upsert_account(session, code: str, name: str, rp: str, rs: str, rf: str) -> Account:
    existing = session.get(Account, code)
    if existing:
        return existing
    acc = Account(code=code, name=name, rubro_principal=rp,
                  rubro_secundario=rs, rubro_final=rf)
    session.add(acc)
    return acc


def upsert_rubro(
    session, name: str, criterio: str | None, order: int, account_codes: list[str],
) -> Rubro:
    existing = session.scalar(select(Rubro).where(Rubro.name == name))
    if existing:
        return existing
    rubro = Rubro(name=name, criterio=criterio, display_order=order)
    session.add(rubro)
    session.flush()
    for code in account_codes:
        # Solo M2M si la cuenta existe en el plan.
        if session.get(Account, code):
            session.add(RubroAccount(rubro_id=rubro.id, account_code=code))
    return rubro


def upsert_season(session, lodge: Lodge, params, comp) -> Season:
    """Upsert: crea o actualiza. Los campos del Comparativo (BN real, meses)
    se refrescan cada vez que corremos el seed para reflejar el último archivo."""
    existing = session.scalar(
        select(Season).where(
            Season.lodge_id == lodge.id,
            Season.year_start == 2025,
        )
    )
    bn_real = Decimal(str(comp.denominators.bednights)) if comp.denominators.bednights else None
    pax_real = Decimal(str(comp.denominators.pax)) if comp.denominators.pax else None
    me = Decimal(str(comp.months_elapsed)) if comp.months_elapsed else None
    mt = Decimal(str(comp.months_total)) if comp.months_total else None

    if existing:
        existing.bn_budget = Decimal(str(params.bn_budget)) if params.bn_budget else existing.bn_budget
        existing.fd_budget = Decimal(str(params.fd_budget)) if params.fd_budget else existing.fd_budget
        existing.pax_budget = Decimal(str(params.pax_budget)) if params.pax_budget else existing.pax_budget
        existing.fx_budget = Decimal(str(params.tc)) if params.tc else existing.fx_budget
        existing.bn_real_std = bn_real
        existing.pax_real_std = pax_real
        existing.months_elapsed = me
        existing.months_total = mt
        return existing
    s = Season(
        lodge_id=lodge.id,
        year_start=2025,
        bn_budget=Decimal(str(params.bn_budget)) if params.bn_budget else None,
        fd_budget=Decimal(str(params.fd_budget)) if params.fd_budget else None,
        pax_budget=Decimal(str(params.pax_budget)) if params.pax_budget else None,
        fx_budget=Decimal(str(params.tc)) if params.tc else None,
        bn_real_std=bn_real,
        pax_real_std=pax_real,
        months_elapsed=me,
        months_total=mt,
    )
    session.add(s)
    session.flush()
    return s


def upsert_budget_lines_and_observations(
    session, lodge: Lodge, season: Season, comp,
) -> tuple[int, int]:
    """Por cada línea del Budget Comparativo del Excel, persiste:
       - BudgetLine: budget_usd + budget_per_bn por (season, rubro)
       - Observation: el texto manual del manager por (lodge, rubro, period='season-to-date')
    """
    # Limpiar previas para que el seed sea idempotente.
    session.execute(delete(BudgetLine).where(BudgetLine.season_id == season.id))
    session.execute(
        delete(Observation).where(
            Observation.lodge_id == lodge.id,
            Observation.period == "season-to-date",
        )
    )

    n_bl = n_obs = 0
    for line in comp.lines:
        rubro = session.scalar(select(Rubro).where(Rubro.name == line.rubro))
        if rubro is None:
            continue   # rubro no presente en el seed (raro pero defensivo)

        if line.budget_usd is not None or line.budget_per_bn is not None:
            session.add(BudgetLine(
                season_id=season.id,
                rubro_id=rubro.id,
                budget_usd=Decimal(str(line.budget_usd)) if line.budget_usd is not None else None,
                budget_per_bn=Decimal(str(line.budget_per_bn)) if line.budget_per_bn is not None else None,
            ))
            n_bl += 1

        if line.observacion:
            session.add(Observation(
                lodge_id=lodge.id,
                rubro_id=rubro.id,
                period="season-to-date",
                body=line.observacion,
            ))
            n_obs += 1
    return n_bl, n_obs


def main() -> None:
    delta_files = discover_delta(ROOT)
    assert delta_files.control_xlsx and delta_files.budget_xlsx, (
        "Faltan archivos de Delta. Copiá los .xlsx a la raíz o data/raw/.")

    print(f"Seed desde:")
    print(f"  control: {delta_files.control_xlsx.name}")
    print(f"  budget:  {delta_files.budget_xlsx.name}")

    # Cargar desde Excel
    accounts = load_accounts(delta_files.control_xlsx)
    comp = parse_comparativo(delta_files.control_xlsx, lodge_code="DEL",
                              valid_account_codes={a.code for a in accounts})
    params = parse_lodge_budget(delta_files.budget_xlsx)

    with get_session() as session:
        # Regiones operativas
        region_arn = upsert_region(session, "AR-NORTE", "Argentina Norte", "ARS")
        region_pat = upsert_region(session, "AR-PAT", "Patagonia Argentina", "ARS")
        region_uru = upsert_region(session, "UY", "Uruguay", "UYU")

        # Lodges del grupo (Delta es el único con datos cargados por ahora;
        # los demás se siembran para que el switcher tenga opciones).
        lodge = upsert_lodge(session, "DEL", "Delta", region_arn.id, "ARS")
        upsert_lodge(session, "JAC", "Jacana", region_arn.id, "ARS")
        upsert_lodge(session, "TOB", "El Tobar", region_pat.id, "ARS")
        upsert_lodge(session, "CAR", "Carmelo", region_uru.id, "UYU")
        upsert_lodge(session, "SJ", "San Juan", region_uru.id, "UYU")

        # Plan de cuentas
        for a in accounts:
            upsert_account(session, a.code, a.name,
                            a.rubro_principal, a.rubro_secundario, a.rubro_final)

        # Rubros del Budget Comparativo
        for i, line in enumerate(comp.lines):
            upsert_rubro(session, line.rubro, line.criterio, i, list(line.account_codes))

        # Temporada 2025-2026 de Delta + budget + observaciones
        season = upsert_season(session, lodge, params, comp)
        n_bl, n_obs = upsert_budget_lines_and_observations(session, lodge, season, comp)

        session.commit()

        # Reporte
        n_accs = len(session.scalars(select(Account)).all())
        n_rubros = len(session.scalars(select(Rubro)).all())
        n_lodges = len(session.scalars(select(Lodge)).all())
        n_seasons = len(session.scalars(select(Season)).all())
        print(f"\n  Cuentas:        {n_accs}")
        print(f"  Rubros:         {n_rubros}")
        print(f"  Lodges:         {n_lodges}")
        print(f"  Seasons:        {n_seasons}")
        print(f"  Budget lines:   {n_bl}")
        print(f"  Observaciones:  {n_obs}")
        print(f"  Season BN real: {season.bn_real_std} / budget {season.bn_budget}")
        print(f"  Meses:          {season.months_elapsed}/{season.months_total}")
        print("  Seed OK.")


if __name__ == "__main__":
    main()
