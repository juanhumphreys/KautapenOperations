"""Entrypoint del demo: corre el pipeline completo sobre Delta.

Uso:
    python scripts/run_demo.py                                     # autodetecta archivos
    python scripts/run_demo.py --control X.xlsx --budget Y.xlsx    # paths explícitos

Autodetecta los .xlsx por patrón en data/raw/. El más reciente gana si hay varios.

Salidas en data/out/:
  - movements_delta.csv         todos los movimientos USD por (lodge, cuenta, mes)
  - rubro_comparativo_delta.csv comparativo budget-vs-real por rubro agrupado
  - flags_delta.csv             flags (DESVIO_BUDGET + SALTO_MOM)
  - demo_delta.md               reporte markdown
  - demo_delta.html             dashboard HTML para mostrar
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from operaciones.calc.flags import flag_budget_deviations, flag_month_over_month
from operaciones.calc.per_bednight import (
    aggregate_by_account_month,
    aggregate_by_account_total,
    compare_rubro_to_budget,
)
from operaciones.calc.reconcile import reconcile_total
from operaciones.discovery import discover_delta, explain_missing
from operaciones.ingest.budget_comparativo import parse_comparativo
from operaciones.ingest.budget_lodge import parse_lodge_budget
from operaciones.ingest.movements import load_movements
from operaciones.ingest.plan_cuentas import load_accounts, index_by_code
from operaciones.ingest.resumen_base import declared_by_account_total, load_declared
from operaciones.report.html import render_html
from operaciones.report.markdown import (
    render_markdown,
    write_account_month_csv,
    write_flags_csv,
    write_rubro_csv,
)

OUT = ROOT / "data" / "out"


def _resolve_files(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resuelve los paths: respeta lo pasado por CLI; si no, autodetecta."""
    delta = discover_delta(ROOT)
    control = Path(args.control) if args.control else delta.control_xlsx
    budget = Path(args.budget) if args.budget else delta.budget_xlsx
    if control is None or budget is None:
        # Reconstruimos un LodgeFiles con lo que tenemos para el mensaje de error.
        from operaciones.discovery import LodgeFiles
        lf = LodgeFiles(code="DEL", name="Delta",
                        control_xlsx=control, budget_xlsx=budget)
        raise SystemExit("✗ " + explain_missing(lf))
    if not control.exists():
        raise SystemExit(f"✗ No existe el archivo de control: {control}")
    if not budget.exists():
        raise SystemExit(f"✗ No existe el archivo de budget: {budget}")
    return control, budget


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--control", help="Path al .xlsx de movimientos del lodge (Delta).")
    parser.add_argument("--budget", help="Path al .xlsx de budget del lodge.")
    args = parser.parse_args()

    DELTA_XLSX, BUDGET_DEL = _resolve_files(args)

    print(f"== Pipeline demo Delta ==")
    print(f"  Archivo control:  {DELTA_XLSX.name}")
    print(f"  Archivo budget:   {BUDGET_DEL.name}")

    # 1) Dimensión de cuentas
    accounts = load_accounts(DELTA_XLSX)
    accounts_by_code = index_by_code(accounts)
    print(f"  Plan de cuentas: {len(accounts)} cuentas")

    # 2) Movimientos (todas las hojas Mov_Analizados_*)
    movs, stats = load_movements(DELTA_XLSX)
    print(f"  Movimientos: {len(movs)} kept "
          f"(broken={stats.rows_broken}, sin_cuenta={stats.rows_no_account}, "
          f"sin_monto={stats.rows_no_amount})")

    # 3) Budget Comparativo (con denominadores BN/Pax y líneas con observación).
    # Pasamos el set de cuentas válidas para filtrar falsos positivos al detectar
    # las cuentas agrupadas en cada rubro.
    valid_codes = {a.code for a in accounts}
    comp = parse_comparativo(DELTA_XLSX, lodge_code="DEL", valid_account_codes=valid_codes)
    print(f"  Budget Comparativo: BN_real={comp.denominators.bednights}, "
          f"Pax_real={comp.denominators.pax}, meses {comp.months_elapsed}/{comp.months_total}, "
          f"líneas={len(comp.lines)}")

    # 4) Parámetros del Budget DEL (BN/FD/Pax de temporada)
    params = parse_lodge_budget(BUDGET_DEL)
    print(f"  Budget DEL params: BN={params.bn_budget}, FD={params.fd_budget}, "
          f"Pax={params.pax_budget}, TC={params.tc}")

    # 5) Reconciliación contra Resumen_Base (declarado por el cliente cuenta-por-cuenta).
    declared = load_declared(DELTA_XLSX, lodge_code="DEL")
    declared_total = declared_by_account_total(declared)
    accs_meta = {a.code: (a.name, a.rubro_secundario) for a in accounts}
    reconcile = reconcile_total(movs, declared_total, accs_meta, "DEL", min_abs_usd=1.0)
    n_match = sum(1 for r in reconcile if abs(r.gap_usd) < 1)
    print(f"  Reconciliación: {n_match}/{len(reconcile)} cuentas matchean al centavo")

    # 6) Agregaciones
    monthly = aggregate_by_account_month(movs)
    total_by_acc = aggregate_by_account_total(movs, lodge_code="DEL")

    comparisons = compare_rubro_to_budget(
        comp.lines, total_by_acc, bednights=comp.denominators.bednights
    )

    # 7) Flags
    flags = []
    flags.extend(flag_budget_deviations(comparisons))
    flags.extend(flag_month_over_month(monthly))

    # 8) Outputs
    write_account_month_csv(monthly, OUT / "movements_delta.csv")
    write_rubro_csv(comparisons, OUT / "rubro_comparativo_delta.csv")
    write_flags_csv(flags, OUT / "flags_delta.csv")
    render_markdown(
        lodge_code="DEL",
        bn_real=comp.denominators.bednights,
        bn_budget=params.bn_budget,
        comparisons=comparisons,
        flags=flags,
        out_path=OUT / "demo_delta.md",
    )
    render_html(
        lodge_code="DEL",
        lodge_name="Delta",
        bn_real=comp.denominators.bednights,
        bn_budget=params.bn_budget,
        months_elapsed=comp.months_elapsed,
        months_total=comp.months_total,
        comparisons=comparisons,
        flags=flags,
        reconcile=reconcile,
        out_path=OUT / "demo_delta.html",
    )

    n_alert = sum(1 for f in flags if f.severity == "alert")
    n_warn = sum(1 for f in flags if f.severity == "warn")
    print(f"\n  Flags totales: {len(flags)}  (alert={n_alert}, warn={n_warn})")
    print(f"  Salidas en {OUT}")


if __name__ == "__main__":
    main()
