"""Parser de la hoja 'Budget Comparativo' (archivo de control del lodge).

NO hardcodea filas ni columnas: detecta dinámicamente:
  - La fila del header de la sección DEL/CAR/SJ (la que contiene 'Criterio'
    y 'Ítem', o algún tag de columna como 'Comparable' / 'Real' / 'Observación').
  - Las filas 'Total BN', 'Total pax', 'Meses Transcurridos' por su etiqueta
    en col B (col 1).
  - Las columnas 'Budget Comparable', 'Real', 'Observación', 'Budget x BN',
    'Real x BN' por su nombre.

Si el cliente reorganiza la planilla, el parser sigue funcionando mientras
mantenga las etiquetas reconocibles.

Las columnas de cuentas agrupadas (P-T en la versión actual) NO tienen header
estable — son las últimas columnas no vacías de la fila. Las detectamos como
"las columnas a la derecha de Observación que contienen códigos numéricos".
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..io_xlsx import as_code, as_float, as_str, iter_rows, open_workbook
from ..models import BudgetLine, Denominators
from ..parsing import find_header_row

SHEET_NAME = "Budget Comparativo"

# Etiquetas que esperamos en la fila del header.
HEADER_ANCHORS = ("criterio", "ítem", "comparable", "observación")
HEADER_ANCHORS_FALLBACK = ("criterio", "comparable")   # variant si no hay tilde


# ---------------------------------------------------------------------------
# Estructura de salida
# ---------------------------------------------------------------------------

@dataclass
class ComparativoData:
    lodge_code: str
    denominators: Denominators
    months_elapsed: Optional[float]
    months_total: Optional[float]
    lines: list[BudgetLine]


# ---------------------------------------------------------------------------
# Detección de columnas
# ---------------------------------------------------------------------------

def _detect_header_row(ws) -> int:
    n = find_header_row(ws, HEADER_ANCHORS, max_scan_rows=15)
    if n is not None:
        return n
    n = find_header_row(ws, HEADER_ANCHORS_FALLBACK, max_scan_rows=15)
    if n is not None:
        return n
    raise ValueError(f"No encontré el header de {SHEET_NAME!r}")


@dataclass
class ColumnMap:
    criterio: Optional[int] = None
    rubro: Optional[int] = None
    budget_total: Optional[int] = None     # 'Budget TOTAL' (temporada entera)
    budget_comparable: Optional[int] = None  # 'Budget Comparable' (prorrateado)
    real: Optional[int] = None
    obs: Optional[int] = None
    budget_bn: Optional[int] = None        # 'Budget x BN' / 'USD/BN'
    real_bn: Optional[int] = None
    accounts_start: Optional[int] = None   # primera col de cuentas agrupadas


def _build_cmap(header: tuple) -> ColumnMap:
    cells = [(i, str(v).strip().lower() if v is not None else "") for i, v in enumerate(header)]

    def find(*needles: str) -> Optional[int]:
        for n in needles:
            n = n.lower()
            for i, c in cells:
                if n in c:
                    return i
        return None

    cm = ColumnMap()
    cm.criterio = find("criterio")
    cm.rubro = find("ítem", "item")
    cm.obs = find("observación", "observacion")
    # Real puede aparecer dos veces ('REAL' a nivel comparable y 'REAL TOTAL').
    # Tomamos la PRIMERA ocurrencia (la que está al lado del Comparable).
    cm.budget_comparable = find("comparable")
    if cm.budget_comparable is not None:
        # Real suele venir 1 columna después de Comparable.
        for i, c in cells:
            if i <= cm.budget_comparable:
                continue
            if "real" in c:
                cm.real = i
                break
    # Budget TOTAL: la celda del header suele tener el valor numérico (375) en
    # vez del label. Asumimos que va antes que 'Comparable'.
    if cm.budget_comparable is not None and cm.budget_comparable > 0:
        cm.budget_total = cm.budget_comparable - 1

    # USD/BN: el cliente NO etiqueta estas columnas con 'BN' ni 'USD/BN' —
    # el header dice 'BUDGET TOTAL'/'REAL'/'%' (engañoso). Las detectamos por
    # POSICIÓN: tras 'observación' aparece un bloque vacío y luego BUDGET/REAL/%.
    # Buscamos las dos primeras columnas que en el header tienen un texto con
    # 'budget' o 'real' (que NO sean las ya asignadas).
    used = {cm.budget_total, cm.budget_comparable, cm.real}
    bn_candidates = [
        i for i, c in cells
        if i not in used and (("budget" in c) or ("real" in c)) and "%" not in c
    ]
    if len(bn_candidates) >= 2:
        cm.budget_bn = bn_candidates[0]
        cm.real_bn = bn_candidates[1]
    return cm


def _row_by_label(rows: dict[int, tuple], label: str, col: int = 1) -> Optional[tuple[int, tuple]]:
    """Encuentra la fila cuya celda en `col` matchea (substring case-insensitive)."""
    target = label.strip().lower()
    for n, r in rows.items():
        if r and len(r) > col and r[col] is not None:
            if target in str(r[col]).strip().lower():
                return n, r
    return None


def _account_codes_in_row(
    row: tuple, start_col: int, valid_codes: Optional[set[str]] = None,
) -> tuple[str, ...]:
    """Saca los códigos de cuenta agrupados en una fila.

    Si `valid_codes` está dado, filtramos contra el plan: sólo cuentan los
    códigos REALES (esto evita falsos positivos por montos numéricos que
    parecen códigos).
    """
    if start_col is None or len(row) <= start_col:
        return ()
    codes = []
    for v in row[start_col:]:
        c = as_code(v)
        if not c:
            continue
        # Mínimo formato de código (al menos 4 dígitos).
        digits = c.replace(".", "")
        if not (digits.isdigit() and len(digits) >= 4):
            continue
        if valid_codes is not None and c not in valid_codes:
            continue
        codes.append(c)
    return tuple(codes)


def parse_comparativo(
    xlsx_path: Path,
    lodge_code: str = "DEL",
    valid_account_codes: Optional[set[str]] = None,
) -> ComparativoData:
    """Si pasás `valid_account_codes` (del plan de cuentas), filtramos los
    códigos detectados contra ese set para evitar falsos positivos."""
    wb = open_workbook(xlsx_path)
    ws = wb[SHEET_NAME]

    rows: dict[int, tuple] = {n: r for n, r in iter_rows(ws, start_row=1)}
    header_n = _detect_header_row(ws)
    header = rows[header_n]
    cmap = _build_cmap(header)

    if cmap.real is None or cmap.budget_total is None:
        raise ValueError(
            f"No pude detectar las columnas clave de {SHEET_NAME!r}: cmap={cmap}"
        )

    # --- Denominadores: filas etiquetadas en col 1 (B) ---
    bn_real = bn_budget = pax_real = months_elapsed = months_total = None
    total_bn = _row_by_label(rows, "total bn")
    total_pax = _row_by_label(rows, "total pax")
    meses = _row_by_label(rows, "meses transcurridos")
    if total_bn:
        _, r = total_bn
        bn_budget = as_float(r[cmap.budget_total]) if len(r) > cmap.budget_total else None
        bn_real = as_float(r[cmap.real]) if len(r) > cmap.real else None
    if total_pax:
        _, r = total_pax
        pax_real = as_float(r[cmap.real]) if len(r) > cmap.real else None
    if meses:
        _, r = meses
        months_total = as_float(r[cmap.budget_total]) if len(r) > cmap.budget_total else None
        months_elapsed = as_float(r[cmap.real]) if len(r) > cmap.real else None

    denoms = Denominators(
        lodge_code=lodge_code,
        period="season-to-date",
        bednights=bn_real,
        pax=pax_real,
        fishing_days=None,
        source="comparativo",
    )

    # --- Líneas de detalle: filas con códigos de cuenta agrupados ---
    # La primera col de cuentas suele estar después de 'real_bn' o 'obs'.
    candidates_start = max(
        cmap.real_bn or 0, cmap.obs or 0, cmap.real or 0
    ) + 1

    lines: list[BudgetLine] = []
    for n in sorted(rows):
        if n <= header_n:
            continue
        row = rows[n]
        if not row:
            continue
        codes = _account_codes_in_row(row, candidates_start, valid_account_codes)
        if not codes:
            continue   # subtotal / separador
        rubro = as_str(row[cmap.rubro]) if cmap.rubro is not None and len(row) > cmap.rubro else ""
        criterio = as_str(row[cmap.criterio]) if cmap.criterio is not None and len(row) > cmap.criterio else ""
        lines.append(BudgetLine(
            lodge_code=lodge_code,
            rubro=rubro,
            criterio=criterio or None,
            account_codes=codes,
            budget_usd=as_float(row[cmap.budget_total]) if len(row) > cmap.budget_total else None,
            real_usd=as_float(row[cmap.real]) if len(row) > cmap.real else None,
            budget_per_bn=as_float(row[cmap.budget_bn]) if cmap.budget_bn is not None and len(row) > cmap.budget_bn else None,
            real_per_bn=as_float(row[cmap.real_bn]) if cmap.real_bn is not None and len(row) > cmap.real_bn else None,
            observacion=as_str(row[cmap.obs]) if cmap.obs is not None and len(row) > cmap.obs else None,
            source_row=n,
        ))
    wb.close()
    return ComparativoData(
        lodge_code=lodge_code,
        denominators=denoms,
        months_elapsed=months_elapsed,
        months_total=months_total,
        lines=lines,
    )
