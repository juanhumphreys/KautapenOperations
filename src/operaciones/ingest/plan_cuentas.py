"""Parser de la hoja 'Plan Cuentas Link Armado'.

NO hardcodea filas: detecta la fila de header buscando las etiquetas conocidas
('Rubro Principal', 'N° Cuenta', 'Descripción Cuenta'), y mapea las columnas
por su nombre.

La estructura típica del cliente (puede variar):
  Header con: Rubro Principal | Rubro secundario | Rubro Final | N° Cuenta | Descripción Cuenta
  Datos: una fila por cuenta.
  Basura al final: 'INSERT' o filas con 0 como cuenta.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from ..io_xlsx import as_code, as_str, iter_rows, open_workbook
from ..models import Account
from ..parsing import find_header_row

SHEET_NAME = "Plan Cuentas Link Armado"

HEADER_ANCHORS = ("rubro principal", "cuenta", "descripción")


_CODE_LABELS = {"n° cuenta", "nro cuenta", "número cuenta", "numero cuenta", "código cuenta", "codigo cuenta"}
_DESC_LABELS = {"descripción cuenta", "descripcion cuenta", "descripción", "descripcion", "nombre cuenta"}


def _find_columns(header: tuple) -> dict[str, int]:
    """Mapea cada etiqueta del header a su índice (match exacto, case/strip insensitive)."""
    out: dict[str, int] = {}
    for i, v in enumerate(header):
        if v is None:
            continue
        s = str(v).strip().lower()
        if s.startswith("rubro principal"):
            out["rubro_p"] = i
        elif s.startswith("rubro secund"):
            out["rubro_s"] = i
        elif s.startswith("rubro final"):
            out["rubro_f"] = i
        elif s in _CODE_LABELS:
            out["code"] = i
        elif s in _DESC_LABELS:
            out["desc"] = i
    return out


def load_accounts(xlsx_path: Path) -> list[Account]:
    wb = open_workbook(xlsx_path)
    try:
        ws = wb[SHEET_NAME]
    except KeyError as e:
        raise ValueError(f"No existe la hoja {SHEET_NAME!r} en {xlsx_path.name}") from e

    header_n = find_header_row(ws, HEADER_ANCHORS, max_scan_rows=15)
    if header_n is None:
        raise ValueError(f"No encontré el header de {SHEET_NAME!r}")

    # Releemos para tomar la fila del header.
    rows = {n: r for n, r in iter_rows(ws, start_row=1) if n <= header_n + 200}
    header = rows[header_n]
    cmap = _find_columns(header)
    if "code" not in cmap or "desc" not in cmap:
        raise ValueError(
            f"Header de {SHEET_NAME!r} no expone columnas clave: "
            f"detectado={cmap}"
        )

    accounts: list[Account] = []
    seen: set[str] = set()
    for n in sorted(rows):
        if n <= header_n:
            continue
        row = rows[n]
        if not row or len(row) <= cmap["code"]:
            continue
        code = as_code(row[cmap["code"]])
        desc = as_str(row[cmap["desc"]]) if len(row) > cmap["desc"] else ""
        if not code or code.upper() == "INSERT":
            continue
        if code in seen:
            continue
        seen.add(code)
        accounts.append(Account(
            code=code,
            name=desc,
            rubro_principal=as_str(row[cmap["rubro_p"]]) if cmap.get("rubro_p") is not None and len(row) > cmap["rubro_p"] else "",
            rubro_secundario=as_str(row[cmap["rubro_s"]]) if cmap.get("rubro_s") is not None and len(row) > cmap["rubro_s"] else "",
            rubro_final=as_str(row[cmap["rubro_f"]]) if cmap.get("rubro_f") is not None and len(row) > cmap["rubro_f"] else "",
        ))
    wb.close()
    return accounts


def index_by_code(accounts: list[Account]) -> dict[str, Account]:
    return {a.code: a for a in accounts}
