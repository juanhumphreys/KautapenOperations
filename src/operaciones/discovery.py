"""Autodetecta los archivos Excel del cliente.

Patrones esperados (definidos por el cliente — son los archivos que mandan
mes a mes):
  - Control Delta:    'DELTA_ECONOMICO*.xlsx'
  - Control Uruguay:  'URUGUAY*.xlsx' (Carmelo + San Juan)
  - Budget Delta:     'Budget DEL*.xlsx'
  - Budget El Tobar:  'Budget El Tobar*.xlsx'
  - Budget Jacana:    'Budget Jacana*.xlsx'

Búsqueda: primero en `data/raw/`, después en la raíz del proyecto para mantener
compatibilidad con corridas viejas. Si hay varios matches (ej. el cliente dejó el
de abril y el de junio), toma el más reciente por mtime.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class LodgeFiles:
    """Archivos detectados para un lodge."""
    code: str
    name: str
    control_xlsx: Optional[Path]   # archivo de movimientos (None si no se encontró)
    budget_xlsx: Optional[Path]    # archivo de budget anual


LODGE_PATTERNS = [
    # (code, name, control_pattern, budget_pattern)
    ("DEL", "Delta", "DELTA_ECONOMICO*.xlsx", "Budget DEL*.xlsx"),
    ("URU", "Uruguay (Carmelo + San Juan)", "URUGUAY*.xlsx", None),
    ("TOB", "El Tobar", None, "Budget El Tobar*.xlsx"),
    ("JAC", "Jacana", None, "Budget Jacana*.xlsx"),
]


def _find(root: Path, pattern: Optional[str]) -> Optional[Path]:
    if pattern is None:
        return None
    # Buscar primero en data/raw/, después en la raíz.
    for base in (root / "data" / "raw", root):
        matches = list(base.glob(pattern))
        if not matches:
            continue
        if len(matches) == 1:
            return matches[0]
        # Varios: el más nuevo gana.
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None


def discover_lodges(root: Path) -> list[LodgeFiles]:
    """Detecta archivos para todos los lodges conocidos."""
    out = []
    for code, name, ctrl_pat, budg_pat in LODGE_PATTERNS:
        out.append(LodgeFiles(
            code=code,
            name=name,
            control_xlsx=_find(root, ctrl_pat),
            budget_xlsx=_find(root, budg_pat),
        ))
    return out


def discover_delta(root: Path) -> LodgeFiles:
    """Shortcut para el demo: solo Delta."""
    for lf in discover_lodges(root):
        if lf.code == "DEL":
            return lf
    raise RuntimeError("No se pudo detectar Delta")


def explain_missing(lf: LodgeFiles) -> str:
    """Mensaje de error claro cuando faltan archivos."""
    missing = []
    if lf.control_xlsx is None:
        missing.append(f"archivo de control (patrón DELTA_ECONOMICO*.xlsx)")
    if lf.budget_xlsx is None:
        missing.append(f"archivo de budget (patrón Budget DEL*.xlsx)")
    if not missing:
        return ""
    return (
        f"No se encontró {' ni '.join(missing)} para {lf.name}. "
        f"Copialos a data/raw/."
    )
