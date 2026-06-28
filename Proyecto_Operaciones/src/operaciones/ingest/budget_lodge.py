"""Parser del archivo Budget_<lodge>.xlsx (parámetros de temporada).

Sólo extraemos los parámetros principales (BN/FD/Pax/fechas/TC). El detalle
por cuenta NO lo usamos en el demo: el archivo de control 'Budget Comparativo'
ya trae budget + real prorrateados, que es lo que necesitamos para comparar.

Layout 'Budget Del 25-26' (verificado):
- row 3:  TC en col H (=1450)
- row 11: header de columnas ('Budget 25-26', 'Real 24-25', 'Real 23-24', ...)
- row 13: BN
- row 14: FD
- row 15: Pax
- row 16: Fecha Inicio
- row 17: Fecha Cierre
- row 18: Días

Columnas (0-based) para parámetros:
  col 2  etiqueta ('BN', 'FD', 'Pax', ...)
  col 3  Budget 25-26
  col 4  Real 24-25
  col 5  Real 23-24
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..io_xlsx import as_float, as_str, iter_rows, open_workbook
from ..models import Denominators


@dataclass
class LodgeBudgetParams:
    lodge_code: str
    sheet: str
    tc: Optional[float]
    bn_budget: Optional[float]
    bn_real_prev: Optional[float]
    fd_budget: Optional[float]
    fd_real_prev: Optional[float]
    pax_budget: Optional[float]
    pax_real_prev: Optional[float]


# Mapeo conocido archivo → (sheet_principal, lodge_code).
LODGE_BUDGET_SHEETS = {
    "Budget DEL 25-26.xlsx": ("Budget Del 25-26", "DEL"),
    "Budget El Tobar 25-26.xlsx": ("Budget 2026", "TOB"),
    "Budget Jacana 25-26.xlsx": ("Budget 2025-26", "JAC"),
}


def parse_lodge_budget(xlsx_path: Path) -> LodgeBudgetParams:
    sheet, lodge_code = LODGE_BUDGET_SHEETS.get(xlsx_path.name, (None, "??"))
    wb = open_workbook(xlsx_path)
    if sheet is None or sheet not in wb.sheetnames:
        # Fallback: agarrar la primera hoja que empiece con 'Budget'
        cand = [s for s in wb.sheetnames if s.lower().startswith("budget")]
        sheet = cand[0] if cand else wb.sheetnames[0]

    ws = wb[sheet]
    rows = {n: row for n, row in iter_rows(ws, start_row=1) if n <= 30}

    def _row_by_label(label: str) -> tuple | None:
        target = label.strip().lower()
        for r in rows.values():
            if len(r) > 2 and as_str(r[2]).strip().lower() == target:
                return r
        return None

    tc = None
    # TC suele estar en row 3 col H (índice 7) con etiqueta "TC" en col G (índice 6).
    for r in rows.values():
        if len(r) > 7 and as_str(r[6]).strip().upper() == "TC":
            tc = as_float(r[7])
            break

    def _triple(label: str) -> tuple[float | None, float | None, float | None]:
        r = _row_by_label(label)
        if r is None:
            return (None, None, None)
        a = as_float(r[3]) if len(r) > 3 else None
        b = as_float(r[4]) if len(r) > 4 else None
        c = as_float(r[5]) if len(r) > 5 else None
        return (a, b, c)

    bn_b, bn_p, _ = _triple("BN")
    fd_b, fd_p, _ = _triple("FD")
    pax_b, pax_p, _ = _triple("Pax")
    wb.close()
    return LodgeBudgetParams(
        lodge_code=lodge_code,
        sheet=sheet,
        tc=tc,
        bn_budget=bn_b,
        bn_real_prev=bn_p,
        fd_budget=fd_b,
        fd_real_prev=fd_p,
        pax_budget=pax_b,
        pax_real_prev=pax_p,
    )


def as_denominators(params: LodgeBudgetParams, period: str = "season-budget") -> Denominators:
    return Denominators(
        lodge_code=params.lodge_code,
        period=period,
        bednights=params.bn_budget,
        pax=params.pax_budget,
        fishing_days=params.fd_budget,
        source="budget",
    )
