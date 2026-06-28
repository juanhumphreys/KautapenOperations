"""Helpers compartidos para detectar dinámicamente la estructura de las hojas.

Cuando el cliente recarga el archivo mes a mes, suele agregar columnas (un mes
nuevo) y a veces mueve filas. En vez de hardcodear índices, buscamos por
contenido.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Año de temporada
# ---------------------------------------------------------------------------

_YEAR_PAIR_RE = re.compile(r"(20\d{2})[_\-\s]+(20\d{2})")
_YEAR_SINGLE_RE = re.compile(r"(20\d{2})")


def extract_season_start_year(filename: str, default: int = 2025) -> int:
    """Saca el año de inicio de temporada desde el nombre del archivo.

    Patrones que reconoce (ejemplos del cliente):
      'TEMP 2025_2026'   -> 2025
      'TEMP 2025-2026'   -> 2025
      'Budget DEL 25-26' -> 2025 (asume 20XX)
      'al_31-05-2026'    -> 2025 (la temporada arranca el año anterior)

    Si no encuentra patrón, devuelve `default`.
    """
    # 1) "YYYY_YYYY" o "YYYY-YYYY" o "YYYY YYYY"
    m = _YEAR_PAIR_RE.search(filename)
    if m:
        return int(m.group(1))
    # 2) "25-26" o "25_26" (asume siglo 21)
    m = re.search(r"\b(\d{2})[_\-](\d{2})\b", filename)
    if m:
        return 2000 + int(m.group(1))
    # 3) Una sola fecha "al_31-05-2026" → la temporada arrancó el año anterior
    m = _YEAR_SINGLE_RE.search(filename)
    if m:
        y = int(m.group(1))
        return y - 1   # mes 1-8 → temporada empezó el año anterior
    return default


# ---------------------------------------------------------------------------
# Detección de filas de header por contenido
# ---------------------------------------------------------------------------

def find_header_row(
    ws, must_contain: Iterable[str], max_scan_rows: int = 30,
) -> Optional[int]:
    """Devuelve el número (1-based) de la primera fila que contiene TODAS las
    etiquetas de `must_contain` (case-insensitive, substring match).
    None si no se encuentra.
    """
    needles = [s.lower() for s in must_contain]
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i > max_scan_rows:
            break
        cells = [str(c).lower() if c is not None else "" for c in row]
        joined = " | ".join(cells)
        if all(n in joined for n in needles):
            return i
    return None


def find_column_index(
    header_row: tuple, must_contain: str, fallback: Optional[int] = None,
) -> Optional[int]:
    """Devuelve el índice (0-based) de la primera celda del header que contiene
    el substring (case-insensitive). `fallback` si no se encuentra.
    """
    needle = must_contain.lower()
    for i, v in enumerate(header_row):
        if v is None:
            continue
        if needle in str(v).lower():
            return i
    return fallback


# ---------------------------------------------------------------------------
# Parseo de etiquetas de mes en español (Resumen_Base)
# ---------------------------------------------------------------------------

SPANISH_MONTH_TO_NUM = {
    "ENE": 1, "ENERO": 1,
    "FEB": 2, "FEBRERO": 2,
    "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAYO": 5,
    "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10,
    "NOV": 11, "NOVIEMBRE": 11,
    "DIC": 12, "DICIEMBRE": 12,
}


def _month_from_token(tok: str) -> Optional[int]:
    """'SEPT' → 9, 'JUNIO' → 6, 'Jun 26' → 6, etc. None si no coincide."""
    t = re.sub(r"[^A-ZÑ]", "", tok.upper())
    if not t:
        return None
    if t in SPANISH_MONTH_TO_NUM:
        return SPANISH_MONTH_TO_NUM[t]
    # Prefijo (manejar 'SEPT' vs 'SEP', 'AGOS' vs 'AGO', etc.)
    for k, v in SPANISH_MONTH_TO_NUM.items():
        if t.startswith(k) or k.startswith(t):
            return v
    return None


def parse_period_label(label: str, season_start_year: int) -> Optional[str]:
    """Convierte la etiqueta del cliente a una clave de período canónica.

    Ejemplos:
      'SEPT - NOV'         -> '2025-09_2025-11'   (rango trimestral)
      'DIC'                -> '2025-12'
      'ENE'                -> '2026-01'
      'JUN'                -> '2026-06'
      'TOTAL ACUMULADO'    -> 'TOTAL'
      ''                   -> None
    """
    if label is None:
        return None
    s = str(label).strip()
    if not s:
        return None
    up = s.upper()
    if "TOTAL" in up:
        return "TOTAL"
    # Rango con guión: 'SEPT - NOV', 'JUL - AGO'.
    if "-" in s and not re.search(r"\d{2,}", s):
        parts = [p.strip() for p in re.split(r"[-/]", s) if p.strip()]
        if len(parts) >= 2:
            m1 = _month_from_token(parts[0])
            m2 = _month_from_token(parts[-1])
            if m1 and m2:
                y1 = season_start_year if m1 >= 9 else season_start_year + 1
                y2 = season_start_year if m2 >= 9 else season_start_year + 1
                return f"{y1}-{m1:02d}_{y2}-{m2:02d}"
    # Mes individual.
    m = _month_from_token(s)
    if m is not None:
        y = season_start_year if m >= 9 else season_start_year + 1
        return f"{y}-{m:02d}"
    return None
