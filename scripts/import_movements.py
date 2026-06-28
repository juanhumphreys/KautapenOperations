"""Importa los movimientos del Excel a la tabla movements de la DB.

- Reutiliza load_movements() de Fase 1 (parser).
- Inserta con source='excel_import'.
- Estrategia de idempotencia: TRUNCATE de los movimientos de este lodge
  con source='excel_import' antes de re-cargar. Es lo más correcto para
  imports legacy (en Fase 2 la carga real va por la webapp y usa UUIDs
  desde el cliente).
- Auditoría: cada batch deja una entrada en audit_log.

Uso:
    python scripts/import_movements.py
"""
from __future__ import annotations
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from collections import Counter
from sqlalchemy import delete, select, func

from db.models import Account, AuditLog, Lodge, Movement
from db.session import get_session
from operaciones.discovery import discover_delta
from operaciones.ingest.movements import load_movements


BATCH_SIZE = 1000   # insert en chunks


def main() -> None:
    delta_files = discover_delta(ROOT)
    assert delta_files.control_xlsx, "Falta el .xlsx de Delta."

    print(f"Importando movimientos de: {delta_files.control_xlsx.name}")
    movs, stats = load_movements(delta_files.control_xlsx)
    print(f"  Parseados: {len(movs)} movimientos (broken={stats.rows_broken}, "
          f"sin_cuenta={stats.rows_no_account})")

    with get_session() as session:
        lodge = session.scalar(select(Lodge).where(Lodge.code == "DEL"))
        if lodge is None:
            raise SystemExit("✗ Lodge DEL no existe en DB. Corré scripts/seed_db.py primero.")

        # Plan de cuentas válido — sólo importamos movimientos cuyas cuentas
        # están en el plan. Las 1101xx (caja/bancos) son asientos de
        # contrapartida que el cliente NO tracea en el control de costos.
        valid_codes = {a.code for a in session.scalars(select(Account)).all()}

        # Idempotencia: borramos los imports previos de este lodge antes de re-cargar.
        deleted = session.execute(
            delete(Movement).where(
                Movement.lodge_id == lodge.id,
                Movement.source == "excel_import",
            )
        ).rowcount
        print(f"  Borrados imports previos: {deleted}")

        new_count = 0
        unknown_accounts: Counter[str] = Counter()
        no_date = 0
        batch: list[Movement] = []
        for m in movs:
            if not m.date:
                no_date += 1
                continue
            if m.account_code not in valid_codes:
                unknown_accounts[m.account_code] += 1
                continue
            amount_usd = Decimal(str(m.amount_usd)).quantize(Decimal("0.0001"))

            mov = Movement(
                lodge_id=lodge.id,
                account_code=m.account_code,
                date=m.date,
                amount_local=Decimal(str(m.amount_ars)),
                currency=lodge.currency,
                fx_rate=Decimal(str(m.fx_rate or 1)),
                amount_usd=amount_usd,
                concept=m.concept[:255] if m.concept else None,
                description=None,
                source="excel_import",
            )
            batch.append(mov)
            new_count += 1

            if len(batch) >= BATCH_SIZE:
                session.add_all(batch)
                session.flush()
                batch = []

        if batch:
            session.add_all(batch)
            session.flush()

        # Audit log del batch
        session.add(AuditLog(
            action="bulk_import",
            entity="movement",
            after={
                "source": "excel_import",
                "file": delta_files.control_xlsx.name,
                "count": new_count,
                "deleted_previous": deleted,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ))
        session.commit()

        total = session.scalar(select(func.count(Movement.id)).where(Movement.lodge_id == lodge.id))
        print(f"\n  Insertados: {new_count}")
        print(f"  Saltados (sin fecha): {no_date}")
        if unknown_accounts:
            print(f"  Saltados (cuentas fuera del plan): {sum(unknown_accounts.values())}")
            print(f"    top cuentas no-plan:")
            for code, n in unknown_accounts.most_common(5):
                print(f"      {code}: {n}")
        print(f"  Total en DB para Delta: {total}")


if __name__ == "__main__":
    main()
