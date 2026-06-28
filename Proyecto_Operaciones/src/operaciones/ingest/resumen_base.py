"""Parser de 'Resumen_Base': real declarado por cuenta y por mes (en USD).

Es la fuente oficial del cliente para 'cuánto se gastó por cuenta en cada mes'.
Comparar esto contra nuestra suma de movimientos detecta dónde el cliente ajustó
a mano (provisiones, reversas, asientos que excluye).

La hoja crece mes a mes: cada cierre nuevo agrega una columna de mes y corre el
TOTAL. Por eso NO hardcodeamos índices: detectamos por contenido la fila de
header (donde aparecen 'SEPT', 'DIC', 'TOTAL'...) y mapeamos cada etiqueta a un
period_key canónico ('2025-09_2025-11', '2026-01', 'TOTAL'...).

Layout que esperamos (Delta):
  row con etiquetas de mes ('SEPT - NOV', 'DIC', 'ENE', ..., 'TOTAL ACUMULADO').
  row con headers de cuenta ('codigo Budget', 'Cuenta', 'Nombre', 'Codigo').
  filas siguientes: una por cuenta. Por cada bloque [vacío, ARS, USD] tomamos USD.
  La columna USD está a +1 de la columna de la etiqueta del mes.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..io_xlsx import as_code, as_float, as_str, iter_rows, open_workbook
from ..parsing import (
    extract_season_start_year, find_header_row, parse_period_label,
)

SHEET_NAME = "Resumen_Base"

# Etiquetas que deben aparecer en la fila de header de cuentas (anchors).
ACCOUNT_HEADER_ANCHORS = ("cuenta", "nombre", "codigo")


@dataclass(frozen=True)
class DeclaredSpend:
    """Lo que el cliente declara haber gastado en una cuenta en un período."""
    lodge_code: str
    account_code: str
    account_name: str
    rubro: str
    period: str         # ej. '2026-04' o '2025-09_2025-11' o 'TOTAL'
    amount_usd: float


def _discover_columns(
    rows: dict[int, tuple], season_start_year: int,
) -> tuple[dict[str, int], int]:
    """Lee la fila de header de meses y devuelve {period_key: usd_col}.

    Retorna también la fila donde empiezan los datos.

    Estrategia: scan las primeras 10 filas; para cada celda no vacía intenta
    parsear como label de mes; si funciona, registra (period, col+1) — el USD
    suele estar inmediatamente a la derecha. Toma la fila con MÁS labels válidas.
    """
    best_row: int = -1
    best_map: dict[str, int] = {}
    for row_idx in sorted(rows):
        if row_idx > 10:
            break
        row = rows[row_idx]
        mapping: dict[str, int] = {}
        for col_idx, val in enumerate(row):
            period = parse_period_label(val, season_start_year) if val else None
            if period is None:
                continue
            mapping[period] = col_idx + 1   # USD a +1 de la label
        if len(mapping) > len(best_map):
            best_map = mapping
            best_row = row_idx

    if not best_map:
        raise ValueError("No pude identificar la fila de header de meses en Resumen_Base.")

    # La fila de header de cuentas suele venir 1 después de la fila de meses.
    # Los datos empiezan 2-3 filas después (hay un row 'INSERT' y un row marcador 'DEL').
    accounts_header_row = best_row + 1
    data_start = accounts_header_row + 1
    # Buscamos la primera fila con un código numérico en col 1 (cuenta).
    for n in range(data_start, data_start + 6):
        r = rows.get(n)
        if r and len(r) > 1 and as_code(r[1]).strip() not in ("", "INSERT"):
            data_start = n
            break
    return best_map, data_start


def load_declared(
    xlsx_path: Path,
    lodge_code: str = "DEL",
    season_start_year: Optional[int] = None,
) -> list[DeclaredSpend]:
    """Carga el real declarado por el cliente, cuenta-por-cuenta-por-período.

    `season_start_year`: año de inicio de la temporada (ej. 2025 para temp 2025-2026).
    Si es None, se infiere del nombre del archivo.
    """
    if season_start_year is None:
        season_start_year = extract_season_start_year(xlsx_path.name)

    wb = open_workbook(xlsx_path)
    ws = wb[SHEET_NAME]
    rows = {n: row for n, row in iter_rows(ws, start_row=1)}

    period_cols, data_start = _discover_columns(rows, season_start_year)

    out: list[DeclaredSpend] = []
    for n in sorted(rows):
        if n < data_start:
            continue
        row = rows[n]
        if not row or len(row) < 4:
            continue
        code = as_code(row[1])
        if not code or code.upper() in ("INSERT", lodge_code.upper()):
            continue
        rubro = as_str(row[0])
        name = as_str(row[2])
        for period, col in period_cols.items():
            if len(row) <= col:
                continue
            amount = as_float(row[col])
            if amount is None or amount == 0:
                continue
            out.append(DeclaredSpend(
                lodge_code=lodge_code,
                account_code=code,
                account_name=name,
                rubro=rubro,
                period=period,
                amount_usd=amount,
            ))
    wb.close()
    return out


def declared_by_account_total(
    declared: list[DeclaredSpend], lodge_code: str = "DEL",
) -> dict[str, float]:
    """Total acumulado por cuenta (lo que el cliente declara que se gastó season-to-date)."""
    return {
        d.account_code: d.amount_usd
        for d in declared
        if d.lodge_code == lodge_code and d.period == "TOTAL"
    }


def declared_by_account_month(
    declared: list[DeclaredSpend], lodge_code: str = "DEL",
) -> dict[tuple[str, str], float]:
    """{(cuenta, mes): USD} para meses individuales (no rangos, no TOTAL)."""
    out: dict[tuple[str, str], float] = {}
    for d in declared:
        if d.lodge_code != lodge_code:
            continue
        # Sólo meses individuales: formato YYYY-MM (10 chars no son rango).
        if d.period == "TOTAL" or "_" in d.period:
            continue
        out[(d.account_code, d.period)] = d.amount_usd
    return out
