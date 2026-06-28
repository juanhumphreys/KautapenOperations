"""Smoke tests del pipeline sobre Delta.

No es una suite completa — sólo chequea que los parsers no rompan y que los
totales coincidan en órden de magnitud con lo que el cliente reporta a mano.
Pensado para correr antes de la demo.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from operaciones.ingest.budget_comparativo import parse_comparativo
from operaciones.ingest.budget_lodge import parse_lodge_budget
from operaciones.ingest.movements import load_movements
from operaciones.ingest.plan_cuentas import load_accounts

DELTA = ROOT / "DELTA_ECONOMICO ANALISIS PRELIMINAR_TEMP 2025_2026_al_31-05-2026.xlsx"
BUDGET = ROOT / "Budget DEL 25-26.xlsx"


def test_plan_cuentas_loads():
    accs = load_accounts(DELTA)
    assert len(accs) >= 70, f"esperaba ≥70 cuentas, hay {len(accs)}"
    by_code = {a.code: a for a in accs}
    # Las cuentas que aparecen en el Budget Comparativo deben existir.
    for c in ("5250", "5251", "5213", "5208", "5227", "5226"):
        assert c in by_code, f"falta cuenta {c} en plan"
    food = by_code["5250"]
    assert food.rubro_secundario == "Food & Wine"


def test_movements_april_2026():
    movs, stats = load_movements(DELTA, sheet_names=["Mov_Analizados_Abr26"])
    assert stats.rows_broken == 0, "no esperábamos #REF! en Abr26"
    assert len(movs) > 50, f"abr26 debería traer >50 movs, hay {len(movs)}"
    # Todos los movimientos kept deben tener cuenta y month_key.
    for m in movs:
        assert m.account_code, f"mov sin cuenta: {m}"
        assert m.lodge_code == "DEL"


def test_budget_comparativo_bn():
    cd = parse_comparativo(DELTA, lodge_code="DEL")
    # Delta: BN real season-to-date == 302 (confirmado por el cliente).
    assert cd.denominators.bednights == 302
    assert cd.denominators.pax == 189
    assert cd.months_elapsed == 9
    # Esperamos al menos los rubros principales con observación.
    rubros = {l.rubro for l in cd.lines}
    for expected in ("Food & Wine", "Guides", "Propane", "Canon Lodge/Labor Permits:"):
        assert expected in rubros, f"falta rubro {expected!r}"


def test_lodge_budget_params():
    p = parse_lodge_budget(BUDGET)
    assert p.lodge_code == "DEL"
    assert p.bn_budget == 375
    assert p.fd_budget == 318.75
    assert p.pax_budget == 187.5
    assert p.tc == 1450


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"OK  {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
