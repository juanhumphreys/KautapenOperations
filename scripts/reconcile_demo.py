"""Reconciliación Delta: nuestro real (movimientos crudos) vs el real declarado
por el cliente en Resumen_Base. Imprime los gaps por cuenta y, para los top-3,
los movimientos sospechosos.

Uso:
    python scripts/reconcile_demo.py                       # autodetect
    python scripts/reconcile_demo.py --control X.xlsx      # path explícito
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from operaciones.calc.reconcile import (
    reconcile_total, reconcile_monthly, suspicious_movements,
)
from operaciones.discovery import discover_delta, explain_missing
from operaciones.ingest.movements import load_movements
from operaciones.ingest.plan_cuentas import load_accounts
from operaciones.ingest.resumen_base import (
    declared_by_account_month, declared_by_account_total, load_declared,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--control", help="Path al .xlsx de movimientos del lodge.")
    args = parser.parse_args()

    delta = discover_delta(ROOT)
    DELTA = Path(args.control) if args.control else delta.control_xlsx
    if DELTA is None or not DELTA.exists():
        raise SystemExit(f"✗ No se encontró el archivo de control. " + explain_missing(delta))
    print(f"  Archivo control: {DELTA.name}\n")

    movs, _ = load_movements(DELTA)
    accs = load_accounts(DELTA)
    accs_meta = {a.code: (a.name, a.rubro_secundario) for a in accs}

    declared = load_declared(DELTA, lodge_code="DEL")
    declared_total = declared_by_account_total(declared)
    declared_month = declared_by_account_month(declared)

    print("== RECONCILIACIÓN TOTAL TEMPORADA (cuenta por cuenta) ==\n")
    print(f"{'Cuenta':>8} {'Rubro':30s} {'Nombre':35s} "
          f"{'Calc USD':>12} {'Decl USD':>12} {'Gap USD':>12} {'Gap %':>8}")
    print("-" * 130)

    total_lines = reconcile_total(movs, declared_total, accs_meta, "DEL", min_abs_usd=10)
    for r in total_lines:
        rubro = (r.rubro or "—")[:30]
        name = (r.account_name or "—")[:35]
        print(f"{r.account_code:>8} {rubro:30s} {name:35s} "
              f"{r.calculated_usd:>12,.0f} {r.declared_usd:>12,.0f} "
              f"{r.gap_usd:>+12,.0f} {r.gap_pct:>+7.1%}")

    print(f"\n  Total cuentas con gap > $10: {len(total_lines)}")

    # Top-3 con gap absoluto y drilldown.
    print("\n\n== TOP CUENTAS CON GAP (drill-down de movimientos grandes) ==\n")
    for r in total_lines[:5]:
        if abs(r.gap_usd) < 100:
            break
        print(f"--- {r.account_code} {r.account_name} ({r.rubro}) ---")
        print(f"    Calc=${r.calculated_usd:,.0f}  Decl=${r.declared_usd:,.0f}  "
              f"Gap=${r.gap_usd:+,.0f}")

        # Reconcile mes a mes para esa cuenta
        m_lines = reconcile_monthly(movs, declared_month, "DEL", min_abs_usd=10)
        m_for_acc = [m for m in m_lines if m.account_code == r.account_code]
        if m_for_acc:
            print("    Por mes (donde gap > $10):")
            for mi in m_for_acc:
                print(f"      {mi.month_key}: calc=${mi.calculated_usd:>9,.0f}  "
                      f"decl=${mi.declared_usd:>9,.0f}  gap=${mi.gap_usd:>+9,.0f}")

        # Top movimientos: muestran si hay provisiones / asientos grandes raros
        susp = suspicious_movements(movs, r.account_code, "DEL", top_n=5)
        print("    Top 5 movimientos por monto:")
        for m in susp:
            d = m.date.isoformat() if m.date else "?"
            print(f"      {d}  ${m.amount_usd:>+9,.0f}  {m.concept[:40]:40s}  ")
        print()


if __name__ == "__main__":
    main()
