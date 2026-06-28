# Reporte de progreso · Control de costos por bednight

**Cliente:** Kautapen Group · 40 lodges
**Fecha:** 2026-06-28
**Demo objetivo:** 30/06/2026

---

## 1. Resumen ejecutivo

Llevamos completadas dos fases del proyecto. La primera valida que el motor
de cálculo reproduce los números del cliente al centavo a partir de sus Excel.
La segunda mueve esa data a una base de datos centralizada con las tablas y
flujos necesarios para escalar a 40 lodges.

**Estado actual:**
- ✅ **Fase 1 (Demo Excel)** — completa, validada contra los datos de Delta.
- ✅ **Fase 2A (Base de datos + migración)** — completa, validada con
  reconciliación al centavo.
- 🔄 **Fase 2B-2I** — pendiente, planificada en `PLAN_fase2_webapp.md`.

**Validación clave repetida en ambas fases:**

> En el lodge Delta, **las 36/36 cuentas de gasto coinciden al centavo** entre
> nuestro cálculo (suma de movimientos crudos) y lo que el cliente declara en
> su Excel. La única discrepancia detectada está en el rubro "Food & Wine"
> a nivel agregado ($28,079 declarado vs $29,462 calculado), no a nivel
> cuenta — es un ajuste manual del cliente que él debe explicar.

---

## 2. Fase 1: Demo sobre Excel (cerrada)

**Objetivo:** demostrar que un motor automatizado puede reproducir el análisis
budget-vs-real que el cliente hace a mano, y además detectar desvíos que ellos
no comentaron.

### Lo que entregamos

| Componente | Descripción |
|---|---|
| Parser de movimientos | Lee `Mov_Analizados_<mes>` de los Excel, normaliza a USD, descarta filas con fórmulas rotas. **No hardcodea** — autodetecta filas de header y columnas por contenido. |
| Parser de Plan de Cuentas | Lee `Plan Cuentas Link Armado`, mapea código → rubro principal/secundario/final. |
| Parser de Budget Comparativo | Extrae budget, real, USD/BN y observaciones del manager por rubro agrupado. |
| Parser de Budget anual | Extrae BN, FD, Pax y TC del archivo `Budget DEL 25-26`. |
| Parser de Resumen_Base | Lee el real declarado por el cliente cuenta-por-cuenta-por-mes. **Soporta JUN** cuando llegue el archivo del 30/6. |
| Motor de cálculo | Suma USD por (lodge, cuenta, mes), agrupa por rubro, divide por bednights. |
| Motor de flags | Detecta sobrecostos, ahorros, posibles timing (cuotas anuales pendientes), saltos mes a mes. |
| Reconciliación | Compara nuestra suma vs lo declarado por el cliente. |
| Dashboard HTML | Página estática con dashboard + detalle por rubro, paleta unificada, sin servidor. |

### Validación cuantitativa

Sobre el archivo de Delta al cierre de Mayo 2026:

- **1,408 movimientos** parseados (broken: 0, sin cuenta: 2,069 sumarios)
- **79 cuentas** en el plan
- **29 rubros** agrupados en el Budget Comparativo
- **BN real 302** vs BN budget 375 (avance 75% de temporada)
- **Reconciliación: 36/36 cuentas al centavo** ✅

### Hallazgos del demo (para presentar al cliente)

**Desvíos confirmados (el sistema reproduce las observaciones del manager):**
- Propane +166% (+$1,146 USD) → cliente: "aumento real de Gas"
- Maintenance Boats +119% (+$4,616) → cliente: "arreglo Astillero Laffranchi"
- Fixed Asset Mejoras +120% (+$11,099) → cliente: "Generador queda 2027"
- Canon Lodge +49% → cliente: "Guardería Lancha doble"
- Food & Wine -25% (-$9,421 ahorro) → cliente: "Mejora en sistema de compras"

**Desvíos sin observación del cliente (candidatos a "se les pasó"):**
- Maintenance Lodge +71% (+$3,026 USD)
- Maintenance Equipment +59% (+$285)
- Misc & Shipping +90% (+$2,024 — el cliente puso "OK con budget" sin detalle)

**Falsos positivos identificados y filtrados como "timing":**
- Insurance -100%, Vehicles Taxes -97% → son cuotas anuales que aún no se pagaron,
  no son ahorros reales.

### Cómo correrlo

```bash
python scripts/run_demo.py
open data/out/demo_delta.html
```

---

## 3. Fase 2A: Base de datos + migración del histórico (cerrada)

**Objetivo:** sacar los datos del Excel y meterlos en una base relacional que
soporte 40 lodges en producción.

### Lo que entregamos

| Componente | Descripción |
|---|---|
| PostgreSQL 16 en Docker | Base de datos local para desarrollo. Puerto 5433 para no colisionar con el Postgres del host. |
| Schema relacional | 15 tablas siguiendo el diseño documentado en `PLAN_fase2_webapp.md §4`. Incluye índices compuestos para queries de dashboard. |
| Modelos SQLAlchemy 2.0 | ORM con tipos completos para todas las entidades del dominio. |
| Migraciones Alembic | Setup completo + migración inicial reproducible. |
| Script de seed | Carga plan de cuentas, rubros, región, lodge Delta y temporada 2025-26 desde los Excel. |
| Script de import | Toma movimientos del Excel y los carga en la tabla `movements`. Reusa los parsers de Fase 1. |
| Script de reconciliación | Verifica que la suma USD por cuenta en DB coincide con lo declarado en Resumen_Base. |

### Tablas creadas (15)

```
regions, lodges, accounts, rubros, rubro_accounts,
seasons, season_months, movements, budget_lines, observations,
users, user_lodges, user_regions, audit_log,
alembic_version
```

### Validación cuantitativa

```
== Estado DB tras seed + import (Delta) ==
  Cuentas: 79
  Rubros:  29
  Lodges:  1
  Seasons: 1
  Movimientos: 1,235

== Reconciliación DB vs Resumen_Base ==
  Cuentas con match al centavo: 36/36 ✅
```

### Hallazgo importante para los 40 lodges

Durante el import, **173 movimientos se filtraron** porque tienen códigos de
cuenta (1101xx = caja/bancos, 8101) que **no figuran en el Plan de Cuentas
oficial** del cliente. Son asientos contables de contrapartida que el cliente
no tracea en su control de costos.

**Implicancia operativa**: al hacer la migración masiva de los 40 lodges en
Fase 2F, vamos a tener que generar un reporte por lodge con las cuentas
"huérfanas" para que gerencia decida si las agrega al plan canónico o las
ignora.

### Cómo correrlo

```bash
docker compose up -d                          # levantar Postgres
.venv/bin/alembic upgrade head                # aplicar schema
.venv/bin/python scripts/seed_db.py           # cargar dimensión
.venv/bin/python scripts/import_movements.py  # importar movimientos
.venv/bin/python scripts/reconcile_db.py      # verificar 36/36
```

---

## 4. Lo que sigue

Según el roadmap del `PLAN_fase2_webapp.md`:

| Fase | Duración estimada | Entregable |
|---|---|---|
| **2B** | 2 semanas | FastAPI con endpoints read-only que sirvan el dashboard desde DB. Auth + roles (lodge_manager / regional_manager / gerencia / admin). |
| **2C** | 3 semanas | **Frontend Next.js + formulario de carga de movimientos** (la pieza central — el manager carga directo, no más Excel). Validaciones, autocompletes, audit log. |
| **2D** | 2 semanas | Cierre de mes (BN/Pax/FD + observaciones) y admin de cuentas/rubros/lodges/usuarios. |
| **2E** | 2 semanas | Dashboard regional y global con rollups (los 40 lodges consolidados, ranking, drill-down por región). |
| **2F** | 3 semanas | **Importador legacy escalado a 40 lodges**: inventario de variantes del template, parsers por template, reconciliación automática, dashboard de progreso. |
| **2G** | 2 semanas | Onboarding piloto: 3-5 lodges con managers receptivos, modo dual con el Excel. |
| **2H** | 4 semanas | Rollout escalonado del resto de los lodges (4-5 por semana). |
| **2I** | 1 semana | Deprecation del Excel + documentación final. |

**Total estimado restante: ~21 semanas** (~5 meses).

---

## 5. Pendientes a confirmar con el cliente

Lo siguiente NO bloquea el arranque de 2B-2C, pero sí condiciona la
arquitectura final. Cuando lleguen las respuestas, hacemos ajustes.

1. Mapa oficial de los 40 lodges (código, región, moneda, manager).
2. Cantidad y rol de managers que van a cargar (1 por lodge vs varios).
3. Si hay regionales que supervisan varios lodges.
4. Conectividad en los lodges remotos (¿necesitamos modo offline?).
5. Si tienen sistema contable upstream que podríamos integrar.
6. Lista completa de monedas usadas (hoy soportamos cualquiera).
7. Si hace falta workflow de aprobación pre-publicación.
8. Quién paga la infra y cómo facturamos.
9. Si los 40 Excel usan un único template o hay variantes regionales.
10. Plan de rollout (qué lodges pilotean).

Ver detalle en `PLAN_fase2_webapp.md §11`.

---

## 6. Riesgos y mitigación

| Riesgo | Severidad | Mitigación |
|---|---|---|
| Resistencia al cambio (40 managers + Excel) | Alta | Modo dual de 1-2 meses + capacitación por región + lodges piloto. |
| Variantes no documentadas del template Excel | Alta | Inventario obligatorio en Fase 2F. Aceptar 3 variantes parseables; el resto se re-templatea a mano antes de importar. |
| Plan de cuentas heterogéneo entre lodges | Media | Reporte por lodge de cuentas "huérfanas" durante migración. Gerencia decide qué agrega al plan canónico. |
| Performance del dashboard regional con 40 lodges | Media | Vistas materializadas + índices compuestos. Si lentea, paginación + caching. |
| Onboarding lento bloquea deprecation del Excel | Media | Cohortes de 4-5 lodges por semana en 2H. Manager regional como punto único de capacitación. |
| Conectividad pobre en lodges remotos | Media | PWA offline-first + sync diferido. Indicador visual claro de estado. |
| Costos de cloud escalan más rápido de lo previsto | Baja | Estimación inicial USD 45-230/mes para los 40 lodges. Monitoreo desde día 1. |

---

## 7. Documentos del proyecto

| Archivo | Propósito |
|---|---|
| `PLAN_demo_costos_bednight.md` | Spec original de Fase 1. |
| `PLAN_fase2_webapp.md` | Spec completa de Fase 2 (DB + webapp + 40 lodges). |
| `REPORTE_PROGRESO.md` | Este documento. |
| `README.md` | Cómo correr el demo de Fase 1. |
| `src/operaciones/` | Core de cálculo (parsers, calc, report) — reutilizable. |
| `src/db/` | Modelos SQLAlchemy. |
| `scripts/` | Entrypoints: seed, import, reconcile, demo. |
| `tests/test_smoke.py` | 4 smoke tests verificando los parsers. |
| `data/out/demo_delta.html` | Dashboard generado para el demo del 30/6. |
