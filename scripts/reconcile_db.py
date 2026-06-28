"""Verifica que la suma USD por cuenta en DB coincide con lo declarado por el
cliente en Resumen_Base.

Debe seguir dando 36/36 al centavo (mismo invariante que validamos en Fase 1
sin DB). Si rompe, hay un problema en el import.

Uso:
    python scripts/reconcile_db.py
"""
from __future__ import annotations
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select

from db.models import Lodge, Movement
from db.session import get_session
from operaciones.discovery import discover_delta
from operaciones.ingest.resumen_base import declared_by_account_total, load_declared


TOLERANCE = Decimal("1.00")   # $1 USD


def main() -> None:
    delta = discover_delta(ROOT)
    declared = load_declared(delta.control_xlsx, lodge_code="DEL")
    declared_total = declared_by_account_total(declared)

    with get_session() as session:
        lodge = session.scalar(select(Lodge).where(Lodge.code == "DEL"))
        if not lodge:
            raise SystemExit("✗ Lodge DEL no existe en DB.")

        # Suma USD por cuenta en DB
        rows = session.execute(
            select(Movement.account_code, func.sum(Movement.amount_usd))
            .where(Movement.lodge_id == lodge.id, Movement.void == False)
            .group_by(Movement.account_code)
        ).all()
        db_total = {code: Decimal(str(total)) for code, total in rows}

    all_codes = set(db_total) | set(declared_total)
    matches = mismatches = 0
    detail = []
    for code in sorted(all_codes):
        d = Decimal(str(declared_total.get(code, 0)))
        c = db_total.get(code, Decimal(0))
        gap = d - c
        if abs(gap) < TOLERANCE:
            matches += 1
        else:
            mismatches += 1
            detail.append((code, c, d, gap))

    print(f"== Reconciliación DB vs Resumen_Base (Delta) ==\n")
    print(f"Cuentas con match al centavo: {matches}/{len(all_codes)}")
    if mismatches:
        print(f"Cuentas con gap > ${TOLERANCE}: {mismatches}")
        print(f"\n{'Cuenta':>10} {'DB calc':>14} {'Decl':>14} {'Gap':>12}")
        print("-" * 60)
        for code, c, d, gap in detail:
            print(f"{code:>10} {c:>14,.2f} {d:>14,.2f} {gap:>+12,.2f}")
    else:
        print("✓ Todas las cuentas coinciden al centavo.")


if __name__ == "__main__":
    main()
