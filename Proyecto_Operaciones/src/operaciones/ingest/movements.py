"""Parser de Mov_Analizados_<mes>.

NO hardcodea filas ni columnas. Estrategia:
- Busca la fila de header escaneando las primeras filas y eligiendo aquella
  que contiene MÁS etiquetas conocidas ('Lodge', 'Cuenta', 'monto USD', etc.).
- Mapea las columnas por su etiqueta (la primera celda que contiene 'monto USD'
  es la columna de USD, sin importar su índice).
- Si el cliente reorganiza la planilla, el parser sigue funcionando.

Filas con #REF!/#N/A se descartan loggeando el motivo.
El month_key se deriva de la fecha de cada movimiento, no del nombre de la hoja.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from ..io_xlsx import as_code, as_float, as_str, is_broken, iter_rows, open_workbook
from ..models import Movement

# Etiquetas que esperamos en el header (sub-strings, case-insensitive).
# Variantes observadas: las hojas mensuales recientes usan 'Cuenta'/'Nombre'/'monto USD'.
# Las hojas viejas (Sept-Nov) usan 'Codigo Cuenta'/'Cuenta Contable'/'Saldo - u$s'.
HEADER_LABELS = {
    "lodge_code": ("lodge",),
    "concept":    ("concepto",),
    "acc_code":   ("cuenta", "codigo cuenta", "código cuenta", "cod cuenta"),
    "acc_name":   ("nombre", "cuenta contable", "descripción cuenta"),
    "amt_ars":    ("monto $", "saldo - $", "saldo $", "saldo ars"),
    "amt_usd":    ("monto usd", "saldo - u$s", "saldo u$s", "monto u$s"),
    "fx":         ("tc", "tipo cambio", "tipo de cambio"),
    "date":       ("fecha",),
}
MIN_LABEL_MATCHES = 4   # >= 4 etiquetas distintas en la misma fila = header.


@dataclass
class ParseStats:
    rows_total: int = 0
    rows_kept: int = 0
    rows_broken: int = 0
    rows_no_account: int = 0
    rows_no_amount: int = 0
    sheets_skipped: list[str] = None    # hojas que no pudimos parsear

    def __post_init__(self):
        if self.sheets_skipped is None:
            self.sheets_skipped = []


@dataclass
class ColumnMap:
    """Índices (0-based) detectados del header de Mov_Analizados."""
    lodge_name: Optional[int] = None    # cuál de las cols 'lodge' es el NOMBRE
    lodge_code: Optional[int] = None    # cuál es el CÓDIGO ('DEL'/'CAR'/'SJ')
    concept: Optional[int] = None
    acc_code: Optional[int] = None
    acc_name: Optional[int] = None
    amt_ars: Optional[int] = None
    amt_usd: Optional[int] = None
    fx: Optional[int] = None
    date: Optional[int] = None


def _month_key(d: date | None) -> str:
    if d is None:
        return ""
    return f"{d.year:04d}-{d.month:02d}"


def _coerce_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


def _score_header_row(row: tuple) -> int:
    cells = [str(c).lower() if c is not None else "" for c in row]
    found = set()
    for key, needles in HEADER_LABELS.items():
        for needle in needles:
            if any(needle in c for c in cells):
                found.add(key)
                break
    return len(found)


def _find_header(ws, max_scan: int = 30) -> tuple[int, tuple]:
    """Devuelve (n_fila, row_values) de la mejor fila-candidata."""
    best_n, best_row, best_score = -1, None, 0
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i > max_scan:
            break
        s = _score_header_row(row)
        if s > best_score:
            best_n, best_row, best_score = i, row, s
    if best_score < MIN_LABEL_MATCHES:
        raise ValueError(f"No encontré una fila-header válida en la hoja "
                         f"(mejor score={best_score}). Layout cambió?")
    return best_n, best_row


def _build_column_map(header: tuple) -> ColumnMap:
    """Mapea las columnas detectadas a sus índices.

    Prioriza match EXACTO sobre substring para evitar colisiones (ej. 'Cuenta
    Anterior' no debe matchear 'Cuenta').
    """
    cells = [(i, str(v).strip().lower() if v is not None else "") for i, v in enumerate(header)]

    def find_exact(*targets: str) -> Optional[int]:
        for t in targets:
            t = t.lower()
            for i, c in cells:
                if c == t:
                    return i
        return None

    def find_substring(*needles: str) -> Optional[int]:
        for n in needles:
            n = n.lower()
            for i, c in cells:
                if n in c:
                    return i
        return None

    def find(*exact: str, contains: tuple[str, ...] = ()) -> Optional[int]:
        """Match exacto primero, después substring."""
        idx = find_exact(*exact)
        if idx is not None:
            return idx
        if contains:
            return find_substring(*contains)
        return None

    cm = ColumnMap()
    cm.lodge_code = find("lodge", contains=("lodge",))
    # Nombre del lodge: típicamente la col inmediatamente anterior al código.
    if cm.lodge_code is not None and cm.lodge_code > 0:
        cm.lodge_name = cm.lodge_code - 1
    cm.concept = find("concepto", contains=("concepto",))
    cm.acc_code = find("cuenta", "n° cuenta", "nro cuenta", "codigo cuenta",
                       "código cuenta", "cod cuenta")
    cm.acc_name = find("nombre", "cuenta contable", "descripción cuenta",
                       "descripcion cuenta")
    cm.amt_ars = find_substring("monto $", "monto ars", "saldo - $", "saldo $")
    cm.amt_usd = find_substring("monto usd", "monto u$s", "saldo - u$s", "saldo u$s")
    cm.fx = find("tc", "t.c.", "tipo de cambio", "tipo cambio")
    cm.date = find("fecha")
    return cm


def _iter_sheet_movements(
    ws, sheet_name: str, stats: ParseStats,
) -> Iterator[Movement]:
    header_row_n, header = _find_header(ws)
    cmap = _build_column_map(header)

    # Validación mínima: necesitamos al menos cuenta, lodge code y USD.
    if cmap.acc_code is None or cmap.lodge_code is None or cmap.amt_usd is None:
        raise ValueError(
            f"Header de {sheet_name!r} no expone columnas clave: "
            f"acc_code={cmap.acc_code} lodge_code={cmap.lodge_code} amt_usd={cmap.amt_usd}"
        )

    for n, row in iter_rows(ws, start_row=header_row_n + 1):
        if not row:
            continue
        stats.rows_total += 1

        def cell(idx: Optional[int]):
            if idx is None or len(row) <= idx:
                return None
            return row[idx]

        if any(is_broken(cell(c)) for c in (cmap.lodge_code, cmap.acc_code, cmap.amt_usd)):
            stats.rows_broken += 1
            continue

        lodge_code = as_str(cell(cmap.lodge_code))
        account_code = as_code(cell(cmap.acc_code))
        if not lodge_code or not account_code:
            stats.rows_no_account += 1
            continue

        amount_usd = as_float(cell(cmap.amt_usd))
        amount_ars = as_float(cell(cmap.amt_ars))
        if amount_usd is None and amount_ars is None:
            stats.rows_no_amount += 1
            continue

        d = _coerce_date(cell(cmap.date))
        stats.rows_kept += 1
        yield Movement(
            lodge_code=lodge_code,
            lodge_name=as_str(cell(cmap.lodge_name)),
            account_code=account_code,
            account_name=as_str(cell(cmap.acc_name)),
            concept=as_str(cell(cmap.concept)),
            amount_usd=amount_usd or 0.0,
            amount_ars=amount_ars or 0.0,
            fx_rate=as_float(cell(cmap.fx)),
            date=d,
            month_key=_month_key(d),
            source_sheet=sheet_name,
        )


def load_movements(
    xlsx_path: Path, sheet_names: Iterable[str] | None = None,
) -> tuple[list[Movement], ParseStats]:
    """Carga movimientos de una o varias hojas Mov_Analizados_*.

    Si sheet_names es None, levanta TODAS las hojas que empiecen con 'Mov_Analizados_'.
    Para cada hoja, detecta dinámicamente la fila de header y las columnas.
    """
    wb = open_workbook(xlsx_path)
    if sheet_names is None:
        sheet_names = [s for s in wb.sheetnames if s.startswith("Mov_Analizados_")]
    stats = ParseStats()
    out: list[Movement] = []
    for name in sheet_names:
        ws = wb[name]
        try:
            out.extend(_iter_sheet_movements(ws, name, stats))
        except ValueError as e:
            # Hoja con layout incompatible (suele ser un trimestre viejo o resumen).
            stats.sheets_skipped.append(f"{name}: {e}")
    wb.close()
    return out, stats
