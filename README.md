# Control de costos por bednight — Kautapen Group

Demo del 30/6 (ver `PLAN_demo_costos_bednight.md` para el contexto y decisiones).

## Setup

```bash
make setup
```

## Correr el pipeline (Delta)

```bash
# Autodetecta los .xlsx del cliente en data/raw/.
# Toma el archivo más reciente si hay varios.
make demo

# Override explícito (útil si querés correrlo sobre otro archivo):
python scripts/run_demo.py --control "DELTA_ECONOMICO...30-06-2026.xlsx" --budget "Budget DEL 25-26.xlsx"
```

Genera en `data/out/`:
- `demo_delta.html`  — dashboard interactivo para mostrar al cliente
- `demo_delta.md`    — reporte markdown
- `*.csv`            — datos para auditoría

Cuando llegue el archivo del 30/6:
1. Copiarlo a `data/raw/`.
2. Correr `make demo` — agarra el archivo nuevo automáticamente.
3. Abrir `data/out/demo_delta.html`.

## Comandos útiles

```bash
make db-up       # levanta Postgres local
make migrate     # aplica migraciones
make seed        # carga dimensiones/budget
make import      # importa movimientos
make reconcile   # valida conciliación
make api         # backend FastAPI en :8000
make web         # frontend Next.js en :3000
make test        # tests Python
```

## Layout

```
src/operaciones/
  ingest/   parsers de las hojas de Excel (movimientos, plan de cuentas, budget)
  calc/     agregación por (lodge, cuenta, mes) y flags de desvío
  report/   render de la salida (CSV + Markdown)
scripts/
  run_demo.py   entrypoint
data/
  raw/   acá copiamos/symlinkeamos los .xlsx originales (no se commitean)
  out/   salida del pipeline
```
