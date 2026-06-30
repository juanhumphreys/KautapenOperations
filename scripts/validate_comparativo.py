"""Dump rapido del Budget Comparativo con valores cacheados (data_only=True).
Sirve para cotejar contra lo que el parser/dashboard muestra.

Uso:
    python scripts/validate_comparativo.py [path_al_xlsx]

Si no pasas path, usa el de Delta por default.
"""
import sys
from pathlib import Path

import openpyxl

DEFAULT_XLSX = "frontend/data/raw/DELTA_ECONOMICO ANALISIS PRELIMINAR_TEMP 2025_2026_al_31-05-2026.xlsx"

# (row, label) — editar segun lo que quieras comparar
ROWS_TO_CHECK = [
    (14, "Shop"),
    (15, "Extras"),
    (24, "Canon Lodge/Labor Permits:"),
    (28, "Manager"),
    (29, "Guides"),
    (33, "Food & Wine"),
    (35, "Electricity"),
    (37, "Propane"),
    (44, "Maintenance Boats/Vehicles"),
    (47, "Insurance for lodge and boats"),
]


def fmt(v):
    if v is None:
        return "None"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def main(xlsx_path: str = DEFAULT_XLSX) -> None:
    wb = openpyxl.load_workbook(Path(xlsx_path), read_only=False, data_only=True)
    ws = wb["Budget Comparativo"]

    def get(row, col):
        return ws.cell(row=row, column=col).value

    print("=" * 80)
    print(f"FILE: {Path(xlsx_path).name}")
    print("DENOMINADORES (Budget Comparativo, R8-R10)")
    print("=" * 80)
    print(f"  BN real      (F8)  = {fmt(get(8, 6))}")
    print(f"  BN budget    (D8)  = {fmt(get(8, 4))}")
    print(f"  Pax real     (F9)  = {fmt(get(9, 6))}")
    print(f"  Pax budget   (D9)  = {fmt(get(9, 4))}")
    print(f"  Meses transc (F10) = {fmt(get(10, 6))}")
    print(f"  Meses total  (D10) = {fmt(get(10, 4))}")

    print()
    print("=" * 80)
    print(f"RUBROS — {len(ROWS_TO_CHECK)} cuentas")
    print("=" * 80)
    header = (
        f"{'Row':>4} {'Rubro':<55} {'Crit':<10} "
        f"{'BudgetUSD':>11} {'RealUSD':>11} {'Desvío':>11} "
        f"{'Bud/BN':>8} {'Real/BN':>8} {'ColN':>7}"
    )
    print(header)
    print("-" * len(header))
    for row, _ in ROWS_TO_CHECK:
        crit = get(row, 1)
        rubro = get(row, 2)
        budget_usd = get(row, 4)
        real_usd = get(row, 6)
        delta = get(row, 7)
        bud_bn = get(row, 12)
        real_bn = get(row, 13)
        col_n = get(row, 14)
        print(
            f"R{row:<3} {(rubro or '')[:54]:<55} {(crit or '-')[:9]:<10} "
            f"{fmt(budget_usd):>11} {fmt(real_usd):>11} {fmt(delta):>11} "
            f"{fmt(bud_bn):>8} {fmt(real_bn):>8} {fmt(col_n):>7}"
        )

    print()
    print("=" * 80)
    print("OBSERVACIONES (col H)")
    print("=" * 80)
    for row, _ in ROWS_TO_CHECK:
        obs = get(row, 8)
        if obs:
            print(f"  R{row} {(get(row, 2) or '')[:40]}: {obs[:100]}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    main(path)
