# Plan de implementación — Fase 2: webapp + base de datos

> Documento de contexto para Claude Code. Es **spec, no código**. Captura las
> decisiones y las opciones abiertas para que la implementación arranque clara.
> Continuación de `PLAN_demo_costos_bednight.md` (Fase 1 = demo).

---

## 1. Contexto y objetivos

Fase 1 demostró que se pueden reproducir los números del cliente (36/36 cuentas
al centavo) leyendo sus Excel. Fase 2 es **eliminar los Excel del flujo**:

- Los managers de cada lodge cargan los movimientos directamente en una webapp.
- Los datos viven en una **base de datos centralizada** (no más archivos sueltos
  por lodge).
- El dashboard pasa a ser **interactivo y vivo** (no se regenera con un script).
- El histórico queda consultable sin abrir un archivo.

**Escala objetivo: 40 lodges en producción** (los Excel de Delta, Carmelo, SJ,
El Tobar y Jacana son una muestra — el sistema final debe soportar los 40 que
administra Kautapen). Esto NO es un detalle menor: condiciona el modelo de datos
(particionado y agregados materializados), la UX (selector de lodge con búsqueda
y rollups regionales), la ingesta legacy (40 templates de Excel con variantes
distintas), los roles (manager / regional / gerencia / admin) y los costos de
infra. Ver §X (Consideraciones de escala) para el detalle.

Problemas concretos que esto resuelve:

- Hoy cada lodge tiene su propia copia del Excel — drift e inconsistencias
  entre los 40 lodges (cada uno con sus propias modificaciones al template).
- El consolidado mensual se arma a mano por gerencia. Con 40 lodges, ese
  trabajo es inviable a este punto.
- Si una fórmula se rompe (`#REF!`), nadie se entera hasta el cierre.
- No hay trazabilidad: no se sabe quién cargó qué.
- No hay forma de saber el estado actual sin pedir el último archivo de cada
  lodge.
- No hay vista regional / cross-lodge para comparar performance.

---

## 2. Decisión de scope para Fase 2

**ENTRA:**

- Schema en base de datos relacional, dimensionado para **40 lodges** y
  ~5 años de histórico (~5-10 M de movimientos).
- Backend API (Python, reutilizando la lógica del pipeline actual).
- Webapp con autenticación y permisos por lodge / región / global.
- **Formulario de carga de movimientos** con validaciones (ver §7).
- Cierre mensual (carga de BN/Pax/FD + observaciones del manager).
- Dashboard dinámico **a 3 niveles**: lodge individual, región (Argentina /
  Uruguay / etc.) y global (los 40 lodges consolidados).
- Migración one-time del histórico Excel → DB **para los 40 lodges** con
  reconciliación cuenta-por-cuenta y reporte de gaps por lodge.

**NO ENTRA (fase 3 o posterior):**

- App móvil nativa (la webapp es responsive y alcanza).
- Stock por unidades físicas (sigue dependiendo de la app de compras que no existe).
- Notificaciones push / alertas por email.
- Workflow de aprobación multi-nivel (manager → gerencia → contabilidad).
- Conexión directa con el sistema contable del cliente (si lo tienen).
- Multi-empresa (sólo Kautapen Group por ahora).

---

## 3. Stack propuesto

| Capa | Tecnología propuesta | Por qué |
|---|---|---|
| Base de datos | **PostgreSQL via Supabase** | Ya estaba en el plan original. Managed, incluye auth y storage. |
| Backend | **FastAPI (Python 3.12+)** | Reutiliza directamente los parsers y la lógica de `calc/` y `report/`. |
| Frontend | **Next.js + React + TypeScript** | UX para no técnicos, formularios complejos, deploy trivial. |
| Auth | **Supabase Auth (email + magic link)** | No requiere que el cliente recuerde contraseñas. |
| Storage de adjuntos | **Supabase Storage** | Facturas, tickets escaneados. |
| Hosting frontend | **Vercel** | Free tier alcanza. |
| Hosting backend | **Cloud Run** (Google) o **Render** | El que el cliente prefiera por costos / región. |
| CI/CD | **GitHub Actions** | Tests + deploy automático. |

> Alternativa más barata para MVP: **Streamlit** en lugar de Next.js. Menos
> vistoso pero más rápido de iterar. Decisión depende de qué tan presentable
> tiene que ser para clientes externos.

---

## 4. Modelo de datos (DB schema)

### Tablas core (la dimensión "qué cargamos")

```
regions                                 # agrupación geográfica/operativa de lodges
  id              uuid PK
  code            text unique          # 'AR-NORTE', 'UY', 'CL-SUR', ...
  name            text
  default_fx_currency text              # 'ARS', 'UYU', 'CLP'

lodges
  id              uuid PK
  code            text unique          # 'DEL', 'CAR', 'SJ', 'TOB', 'JAC', ...
  name            text                 # 'Delta', 'Carmelo', ...
  region_id       uuid FK
  manager_email   text                 # contacto principal
  active          boolean
  excel_template  text                 # 'standard_v1', 'uruguay_v2', etc.
                                        # (usado por el importador legacy para
                                        #  saber qué variante esperar)

accounts                                # plan de cuentas (canónico, una sola vez,
                                        # compartido entre todos los lodges)
  code            text PK              # '5250'
  name            text                 # 'Comidas y Refrigerios'
  rubro_principal text
  rubro_secundario text
  rubro_final     text
  is_seasonal     boolean              # patentes, seguros, licencias

rubros                                  # agrupaciones para el Budget Comparativo
  id              uuid PK
  name            text                 # 'Food & Wine'
  criterio        text                 # 'BN' | 'Acumulado' | 'FD'
  display_order   int

rubro_accounts                          # M2M rubro <-> cuentas
  rubro_id        uuid FK
  account_code    text FK
  PRIMARY KEY (rubro_id, account_code)
```

> **Nota plan de cuentas**: hoy todos los lodges del grupo comparten el mismo
> plan de cuentas (lo verificamos en los 5 Excels). Si en algún momento un
> lodge necesita una cuenta particular, se agrega al plan global con un flag
> de "aplica a estos lodges". Evitamos a toda costa tener un plan por lodge —
> sería inmanejable a 40.

### Tablas de operación (la "F" del fact table)

```
seasons
  id              uuid PK
  lodge_id        uuid FK
  year_start      int                  # 2025 (temp 2025-26)
  starts_on       date
  ends_on         date
  bn_budget       numeric
  fd_budget       numeric
  pax_budget      numeric
  fx_budget       numeric              # TC fijo para todo el budget
  closed          boolean              # true cuando ya cerraron el balance

season_months                           # cierre mensual real
  id              uuid PK
  season_id       uuid FK
  year            int
  month           int                  # 1-12
  bn_real         numeric              # huésped-noches del mes
  pax_real        numeric
  fd_real         numeric
  closed_at       timestamp
  closed_by       uuid FK -> users

movements                               # EL FACT TABLE — cada gasto/ingreso
  id              uuid PK
  lodge_id        uuid FK
  account_code    text FK
  date            date NOT NULL
  amount_local    numeric NOT NULL     # ARS, UYU, CLP — la moneda del lodge
  currency        text NOT NULL        # 'ARS' | 'UYU' | 'CLP' | ...
  fx_rate         numeric NOT NULL     # local → USD
  amount_usd      numeric NOT NULL     # generado: amount_local / fx_rate
  concept         text                 # libre
  description     text                 # detalle del comprobante
  subdiario       text                 # 'CAJA' | 'BANCOS' | 'ASIENTOS'
  comprobante     text                 # '0141 F B 000...'
  proveedor       text
  tax_id          text                 # CUIT, RUT, RUC — el ID fiscal local
  observation     text                 # libre
  attachment_url  text                 # link a storage
  source          text                 # 'web' | 'excel_import' | 'api'
  created_by      uuid FK -> users
  created_at      timestamp
  updated_at      timestamp
  void            boolean default false
  voided_reason   text

  -- Particionado: PARTITION BY RANGE (date) — un partition por año fiscal.
  -- Con 40 lodges × ~1500 movs/mes × 12 = ~720k movs/año, el particionado
  -- mantiene queries del dashboard del mes corriente rápidos sin escanear
  -- el histórico.

  -- Índices críticos:
  -- (lodge_id, date)                          → dashboards por lodge
  -- (lodge_id, account_code, date)            → drill-down por cuenta
  -- (date)                                    → rollups regional/global por mes
  -- partial index WHERE NOT void              → defaults filtran voids

budget_lines                            # budget por rubro x temporada
  season_id       uuid FK
  rubro_id        uuid FK
  budget_usd      numeric              # temporada entera
  budget_per_bn   numeric              # = budget_usd / bn_budget
  PRIMARY KEY (season_id, rubro_id)

observations                            # observaciones del manager (lo que hoy
                                        # se escribe a mano en Budget Comparativo)
  id              uuid PK
  lodge_id        uuid FK
  rubro_id        uuid FK
  period          text                 # '2026-04' | 'season-to-date'
  text            text NOT NULL
  author          uuid FK -> users
  created_at      timestamp
```

### Tablas de control

```
users
  id              uuid PK              # Supabase auth.uid()
  email           text unique
  full_name       text
  role            text                 # 'lodge_manager' | 'regional_manager'
                                        # | 'gerencia' | 'admin'

user_lodges                             # qué lodges ve cada user (override del rol)
  user_id         uuid FK
  lodge_id        uuid FK
  PRIMARY KEY (user_id, lodge_id)

user_regions                            # un regional_manager ve todos los lodges
                                        # de su(s) región(es) automáticamente
  user_id         uuid FK
  region_id       uuid FK
  PRIMARY KEY (user_id, region_id)

audit_log                               # quién hizo qué y cuándo
  id              uuid PK
  timestamp       timestamp
  user_id         uuid FK
  action          text                 # 'create' | 'update' | 'void'
  entity          text                 # 'movement' | 'observation' | ...
  entity_id       uuid
  before          jsonb
  after           jsonb
```

### Vistas materializadas para rollups

A 40 lodges, calcular el comparativo regional / global del Budget Comparativo
on-the-fly puede ser costoso. Mantenemos vistas materializadas refrescadas
al cierre de cada movimiento:

```
mv_lodge_monthly_by_account         # USD por (lodge, cuenta, año-mes)
mv_lodge_monthly_by_rubro           # USD por (lodge, rubro, año-mes)
mv_region_monthly_by_rubro          # USD por (región, rubro, año-mes)
mv_global_monthly_by_rubro          # USD por (rubro, año-mes) — para el rollup
```

Refresh: trigger después de INSERT/UPDATE/DELETE en `movements`. Si el costo
de refresh por fila se vuelve alto, pasar a refresh batch (cada 5 min).

### Row Level Security (Supabase RLS)

- `movements`, `season_months`, `observations`: el user ve filas donde
  `lodge_id` está en su `user_lodges` **o** donde `lodges.region_id` está
  en su `user_regions`.
- `gerencia` y `admin` ven todo.
- `lodge_manager` sólo INSERT/UPDATE en su(s) lodge(s); jamás puede modificar
  un mes cerrado (eso requiere admin).
- `regional_manager` puede leer todos los lodges de su región, pero sólo
  cargar movimientos en lodges donde sea designado expresamente.

---

## 5. Backend / API

### Endpoints (REST sobre FastAPI)

**Lectura (dashboard):**
- `GET /api/lodges` → lodges accesibles para el user.
- `GET /api/lodges/:id/season/current` → temporada en curso, denominadores.
- `GET /api/lodges/:id/comparativo?period=current` → datos del comparativo
  budget-vs-real por rubro (lo que el dashboard pinta).
- `GET /api/lodges/:id/flags?period=current` → desvíos detectados, con
  observación del cliente si la hay.
- `GET /api/lodges/:id/movements?from=&to=&account=` → listado paginado.
- `GET /api/lodges/:id/movements/:id` → detalle de un movimiento.

**Escritura:**
- `POST /api/lodges/:id/movements` → carga un movimiento (ver §7).
- `PATCH /api/lodges/:id/movements/:id` → corrige (audit log automático).
- `POST /api/lodges/:id/movements/:id/void` → anula con motivo (no se borra,
  queda `void=true`).
- `POST /api/lodges/:id/months/:yyyy-:mm/close` → cierra el mes con
  BN/Pax/FD declarados.
- `POST /api/lodges/:id/observations` → carga observación libre por rubro.

**Admin / setup:**
- `GET/POST /api/accounts` → CRUD del plan de cuentas.
- `GET/POST /api/rubros` → CRUD de agrupaciones.
- `POST /api/budgets/:season_id` → setea budget por rubro al inicio de temporada.

**Import legacy:**
- `POST /api/import/excel` → toma un .xlsx (el del cliente actual) y backfillea
  movimientos. Marca `source='excel_import'` para distinguir.

### Reglas en backend (no en frontend)

- Validar que `account_code` exista en el plan.
- Recalcular `amount_usd = amount_ars / fx_rate` siempre (el form puede mostrar
  el valor pero el backend lo recalcula).
- Validar que la fecha del movimiento esté dentro de la temporada activa.
- Si el rubro está marcado como sensitive (canon, sueldos), requerir comprobante.
- Auditar cualquier modificación a un movimiento ya en mes cerrado (no permitir
  sin permiso de admin).

---

## 6. Frontend / Webapp

### Pantallas

1. **Login** — magic link a email del manager.
2. **Home / selector de scope** — al login, el user ve:
   - Si es `lodge_manager` de 1 lodge → entra directo al dashboard de ese lodge.
   - Si tiene acceso a varios lodges (regional, gerencia) → ve un **listado
     con búsqueda, agrupado por región**, con KPIs resumidos al lado de cada
     lodge (BN actual, sobrecostos, alertas sin observar). A 40 lodges hace
     falta búsqueda + filtro por región + indicador visual rápido.
3. **Dashboard de lodge** — versión interactiva del HTML actual:
   - Filtro por mes / temporada.
   - Filtro por rubro.
   - Drill-down: click en un rubro → ver movimientos componentes.
4. **Dashboard regional / global** (solo regional / gerencia / admin):
   - Tabla de los lodges de la región/grupo con KPIs (BN, USD/BN total,
     cantidad de desvíos sin observar).
   - Ranking de lodges por performance (mejor / peor USD/BN).
   - Drill-down: click en un lodge → su dashboard individual.
5. **Carga de movimientos** — formulario del §7.
6. **Cierre de mes**:
   - Inputs: BN, Pax, FD del mes.
   - Para cada rubro con desvío significativo, prompt para observación
     ("¿por qué Maintenance Lodge está 71% arriba?").
   - Botón "Cerrar mes" con confirmación (después no se edita sin admin).
7. **Histórico** — navegar meses anteriores, ver dashboards congelados.
8. **Admin** (solo rol admin):
   - CRUD plan de cuentas, rubros, agrupaciones.
   - **Gestión de lodges**: alta de nuevos, asignar a región, configurar
     plantilla de Excel (para el importador legacy), TC default por moneda.
   - Gestión de usuarios y permisos.
   - Visor de audit_log.
   - Tablero de estado de imports legacy (qué lodges ya migramos, cuáles
     pendientes, gaps detectados).

### Diseño visual

- Reutilizar la paleta del dashboard actual (zinc + slate + 4 severidades).
- Mobile-first para la pantalla de carga (los managers cargan desde el lodge
  con conectividad limitada).
- Componentes accesibles (campos grandes, labels claras).

---

## 7. Formulario de carga de movimientos (detalle)

Esto es la pieza central de la fase 2 — reemplaza el flujo Excel.

### Estructura del formulario

Agrupado en 4 secciones colapsables:

#### Sección 1 — Datos del movimiento (obligatorios)

| Campo | Tipo | Validación |
|---|---|---|
| **Fecha** | date picker | Obligatorio. Debe estar dentro de la temporada activa. |
| **Lodge** | dropdown | Autocompletado por el user logueado. Obligatorio. |
| **Cuenta contable** | dropdown searchable | Obligatorio. Solo cuentas del plan. Muestra código + nombre + rubro. |
| **Concepto** | text auto | Se rellena al elegir la cuenta (`rubro_secundario`). Editable. |
| **Subdiario** | dropdown | Obligatorio. Valores: `CAJA`, `BANCOS`, `ASIENTOS`, `VENTAS`, `COMPRAS`. |

#### Sección 2 — Montos (obligatorios)

| Campo | Tipo | Validación |
|---|---|---|
| **Monto ARS** | number | Obligatorio. ≠ 0. Acepta negativos (devoluciones). |
| **Tipo de cambio** | number | Obligatorio. > 0. Default: TC oficial del día (autocompletado). |
| **Monto USD** | number readonly | Auto-calculado `ARS / TC`. Editable solo si admin lo permite. |

> Nota: el cliente carga ARS (es su moneda natural), pero el sistema **siempre
> guarda y muestra USD** en el dashboard. El TC se guarda para auditoría.

#### Sección 3 — Documentación (obligatoria para gastos)

| Campo | Tipo | Validación |
|---|---|---|
| **Tipo de comprobante** | dropdown | Obligatorio si `subdiario in (CAJA, BANCOS, COMPRAS)`. Valores: factura A/B/C, ticket, recibo, asiento manual. |
| **Número de comprobante** | text | Obligatorio si hay tipo de comprobante. Formato libre. |
| **Proveedor / Sujeto** | text con autocomplete | Obligatorio para gastos. Autocompleta desde proveedores ya cargados. |
| **CUIT / RUT** | text | Obligatorio si proveedor es persona jurídica. Formato XX-XXXXXXXX-X. |
| **Adjunto** | file upload | Opcional. Acepta PDF, JPG, PNG. Max 5 MB. Va a Supabase Storage. |

#### Sección 4 — Detalle (opcional pero recomendado)

| Campo | Tipo | Validación |
|---|---|---|
| **Observación** | textarea | Opcional. Lo que hoy escriben en la col "Comentario renglón asiento" del Excel. |
| **Referencia a asiento contable** | text | Opcional. Para conciliar con su sistema contable. |
| **Centro de costo** | dropdown | Opcional. Para asignar a sub-proyectos dentro del lodge. |

### Validaciones cruzadas (al hacer submit)

- Si la fecha cae en un mes ya cerrado → bloquear con mensaje claro
  ("El mes 2026-04 ya está cerrado. Pedile a admin que reabra").
- Si la cuenta es del rubro "Salaries" → exigir período de devengamiento
  (campo extra).
- Si el monto en USD es > 5,000 → mostrar warning ("¿Estás seguro? Es un
  movimiento grande") + requerir adjunto.
- Si el proveedor es nuevo (no estaba en autocomplete) → confirmar antes de
  crearlo en la tabla de proveedores.

### UX del formulario

- Tabs / wizard si el formulario crece demasiado.
- Botón "Guardar borrador" → guarda en localStorage por si pierden internet.
- Botón "Cargar y crear otro" para flujos en batch.
- Listado de los últimos 10 movimientos cargados por el user al costado (para
  copiar uno y modificar).
- Feedback claro al guardar: "✓ Cargado. Movimiento DEL-5250-20260427-001.
  Total USD: $1,234".

---

## 8. Migración del histórico (40 lodges)

Con 40 lodges, esto NO es un script de 5 minutos. Es un mini-proyecto.

### 8.1 Estrategia

1. **Inventario de los 40 Excel** — pedir al cliente los archivos actualizados.
   Para cada uno detectar:
   - Variante del template (`standard_v1`, `uruguay_v2`, ...).
   - Moneda local del lodge.
   - Año de inicio de la temporada (las temporadas no arrancan todas en
     septiembre — algunos lodges del hemisferio norte arrancan en abril).
   - Hojas con layout no-estándar (ej. la `Mov_Analizados_Sept25-Nov 25` de
     Delta que ya manejamos como variante).

2. **Importador genérico** — extender los parsers de Fase 1 para:
   - Operar lodge por lodge en paralelo (workers async).
   - Soportar `excel_template` por lodge (config en DB).
   - Loggear gaps por lodge (igual que ya hacemos para Food & Wine en Delta).
   - Si un Excel tiene gaps no resolvibles, marcarlo como "pendiente de
     revisión manual" sin bloquear el resto.

3. **Pipeline de import**, por lodge:
   - Schema setup → semilla del plan de cuentas, rubros, lodge.
   - Backfill de movimientos → INSERT con `source='excel_import'` + audit_log.
   - Reconciliación cuenta-por-cuenta (igual que en Fase 1).
   - Reporte: % de cuentas que matchean al centavo, gaps detectados.

4. **Dashboard de progreso** — los 40 lodges en una tabla con estado:
   `pendiente | en proceso | importado | con gaps | fallido`.

5. **Setup de usuarios** — onboarding por región (manager regional carga sus
   lodge_managers).

6. **Modo dual (1-2 meses)** — el cliente carga en webapp Y mantiene el Excel
   como red de seguridad. Comparación automática diaria para detectar drift.

7. **Deprecation del Excel** — por lodge cuando el manager confirma confianza;
   no todos a la vez. Lodges piloto primero, después el resto.

### 8.2 Riesgos específicos de 40 lodges

- **Variantes no documentadas del template**: si 5-10 lodges tienen layouts
  raros, hay que decidir si los normalizamos a `standard_v1` antes de importar
  o agregamos parsers específicos. **Recomendación**: aceptar hasta 3 variantes
  bien soportadas; cualquier extra exige re-template manual antes de importar.
- **Calidad de los datos heterogénea**: algunos lodges van a tener menos
  trazabilidad que otros. Marcar movimientos con `data_quality_score` para
  saber qué confianza darle a los rollups regionales.
- **Tiempo**: importar 40 lodges con reconciliación es ~2 sprints, no 2 días.

---

## 9. Despliegue y operación

| Componente | Dónde corre | Notas |
|---|---|---|
| DB | Supabase (us-east) | Backups diarios automáticos. |
| Backend FastAPI | Cloud Run o Render | Auto-scale. CORS configurado. |
| Frontend Next.js | Vercel | Preview deploys por PR. |
| Storage | Supabase Storage | Bucket `attachments` privado, signed URLs. |
| Secretos | Variables de entorno + Supabase Vault | Sin nada en el repo. |
| Monitoreo | Logs de Supabase + Sentry para frontend/backend | Errores notificados a Slack. |

### Seguridad

- HTTPS-only.
- RLS habilitado en todas las tablas con datos sensibles.
- Audit_log inmutable (deny update/delete por RLS).
- Backup encriptado.
- Política de retención de adjuntos (purgar > 7 años).

---

## 10. Roadmap por fases (revisado para 40 lodges)

| Fase | Duración | Entregable |
|---|---|---|
| **2A** | 2 sem | Schema DB completo + particionado + índices + vistas materializadas. Migración de 1 lodge piloto (Delta) con reconciliación. Backend read-only sirviendo dashboard desde DB. |
| **2B** | 2 sem | Auth + roles (lodge / regional / gerencia / admin) + selector con búsqueda + dashboard de lodge interactivo. |
| **2C** | 3 sem | Formulario de carga de movimientos con validaciones + autocompletes + audit log + multi-moneda. |
| **2D** | 2 sem | Cierre de mes + observaciones + admin de cuentas/rubros/lodges/usuarios. |
| **2E** | 2 sem | Dashboard regional y global (rollups con vistas materializadas) + ranking de lodges. |
| **2F** | 3 sem | **Importador legacy escalado a 40 lodges**: inventario, parsers por template, dashboard de progreso, reconciliación automática por lodge. |
| **2G** | 2 sem | Onboarding por región: 3-5 lodges piloto en modo dual, capacitación de managers regionales. |
| **2H** | 4 sem | Rollout del resto de los 40 lodges (4-5 por semana) con acompañamiento. |
| **2I** | 1 sem | Deprecation del Excel + documentación final. |

Total: **~21 semanas** (~5 meses) para reemplazar el Excel en los 40 lodges.

> El roadmap original (12 semanas) era para ~5 lodges. La escala a 40 agrega
> ~2 meses, principalmente en migración legacy y rollout escalonado. El
> producto core (2A-2E) sigue siendo ~11 semanas; lo que se estira es la
> operación de transición.

---

## 11. Pendientes a confirmar con el cliente

Antes de empezar 2A:

1. **Mapa de los 40 lodges**: lista oficial con código, nombre, región/país,
   moneda local, temporada (mes de inicio), manager principal y email.
2. **¿Cuántos managers van a cargar?** ¿Es uno por lodge o varios? Determina
   la complejidad de auth y los costos de Supabase.
3. **¿Hay managers regionales que supervisan varios lodges?** Define el rol
   `regional_manager` y cómo se asignan a regiones.
4. **¿Tienen internet estable en los 40 lodges?** Algunos sí (Carmelo, urbano),
   otros no (Delta, remoto). El formulario probablemente tenga que ser
   **offline-first (PWA con sync diferido)** para los lodges remotos.
5. **¿Hay un sistema contable upstream?** Si los movimientos ya están en otro
   sistema (Tango, Bejerman, etc.) en algunos lodges, ¿queremos integración
   para esos y carga manual para el resto?
6. **¿Quién es el dueño del plan de cuentas?** Hoy parece compartido en los
   5 Excel que vimos. Confirmar que sigue siendo así en los 40. Si gerencia
   agrega cuentas, ¿quién aprueba?
7. **¿Necesitan exportar a Excel?** Algunos auditores externos lo van a pedir.
   ¿Damos export por lodge / por región / global?
8. **Monedas**: confirmar lista completa. Hoy sabemos ARS y UYU; probablemente
   también CLP, BRL, USD directo para algunos lodges.
9. **¿Aprobación de movimientos?** Hoy el manager carga y listo. ¿Queremos
   workflow de revisión por el manager regional antes de que entre al
   dashboard? Con 40 lodges puede ser necesario para mantener calidad.
10. **Costos de infra** — ¿el cliente paga directamente Supabase + Vercel +
    Cloud Run, o se le factura como servicio mensual? Con 40 lodges la
    factura mensual de Supabase sube (probablemente ~USD 100-300/mes).
11. **Variantes de los Excel** — ¿los 40 lodges usan el mismo template o
    hay variantes regionales? Necesitamos los 40 archivos antes de empezar
    2F para inventariar.
12. **Plan de rollout**: ¿qué lodges van primero como piloto? Sugerencia:
    3 lodges con managers receptivos al cambio + un mix de regiones.

---

## 12. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Resistencia al cambio (40 managers acostumbrados a Excel) | Modo dual de 1-2 meses + capacitación regional + UX que sienta "como Excel" en la carga + lodges piloto con managers receptivos. |
| Variantes no documentadas del template Excel | Inventario obligatorio en 2F. Aceptar hasta 3 variantes parseables; el resto se re-templatea a mano antes de importar. |
| Cambios al plan de cuentas durante la transición | Migración del Excel debe ser reproducible (idempotente) para correr varias veces. Plan de cuentas versionado. |
| Pérdida de datos durante migración a 40 lodges | Backup pre-migración + reconciliación cuenta-por-cuenta por lodge + reporte de gaps publicado a gerencia antes de "ir vivo" en cada lodge. |
| Conectividad pobre en lodges remotos | PWA offline-first + sync. Aceptable que un movimiento tarde minutos en aparecer en el dashboard. Indicador visual claro de estado de sync. |
| Performance del dashboard regional/global con 40 lodges | Vistas materializadas + particionado por año + índices específicos. Si igual lentea, paginación y carga incremental. |
| Manager regional sobrecargado supervisando 10 lodges | UX del dashboard regional debe priorizar por alertas, no listar parejo. Ranking + filtros + drill-down. |
| Costos de cloud crecen más rápido de lo previsto | Empezar con tiers gratuitos para los lodges piloto. Monitorear desde el primer día. Revisar facturación al final de 2H. |
| 40 lodges generan demasiados flags por mes | Curaduría agresiva en defaults: thresholds por rubro (no globales), filtros por región, batch resolution de observaciones. |
| Onboarding lento bloquea la deprecation del Excel | Cohortes de 4-5 lodges por semana en 2H. Manager regional como punto único de capacitación. Documentación + screencast por flujo. |

---

## X. Consideraciones de escala (40 lodges)

Esta sección reúne todo lo que cambia por pasar de 5 a 40 lodges.

### X.1 Volumen de datos esperado

| Métrica | Por lodge / mes | Total con 40 lodges |
|---|---|---|
| Movimientos | ~1,000-2,000 | 40k-80k / mes |
| Movimientos / año | ~15k-25k | 600k-1M / año |
| Movimientos en 5 años | — | 3M-5M en la tabla `movements` |
| Adjuntos (PDF/JPG) | ~200-500 | 8k-20k / mes |
| Storage adjuntos / año | ~500 MB / lodge | ~20 GB / año total |

PostgreSQL maneja esto sin problema, pero requiere índices buenos y
particionado.

### X.2 Performance

- **Particionado de `movements` por año fiscal** (RANGE PARTITION). Las queries
  del dashboard del mes corriente sólo tocan la partición del año actual.
- **Índices compuestos** específicos por patrón de uso:
  - `(lodge_id, date)` — dashboards por lodge.
  - `(lodge_id, account_code, date)` — drill-down por cuenta.
  - `(date)` global — rollups regionales / globales por mes.
  - Partial index `WHERE NOT void` — el dashboard nunca cuenta voids.
- **Vistas materializadas** para los rollups (ver §4).
- **Caching en backend**: el comparativo del mes vigente para un lodge puede
  cachearse 1-5 min sin afectar la frescura percibida.
- **Paginación obligatoria** en listados de movimientos (default 50, max 200).

### X.3 UX a escala

- **Selector de lodge**: con 40 lodges, listar parejo es inútil. Necesita:
  - Búsqueda por nombre/código.
  - Agrupación por región.
  - Pin de favoritos del usuario.
  - Indicador visual rápido de estado (verde = todo OK, amarillo = desvíos sin
    observar, rojo = alertas críticas).
- **Dashboard regional**: tabla scrollable con el ranking de los lodges de la
  región por desvío más grande.
- **Dashboard global**: el view de gerencia general, top-line solamente
  (lista colapsada de regiones con KPIs agregados).

### X.4 Roles y permisos

| Rol | Acceso |
|---|---|
| `lodge_manager` | Su(s) lodge(s). Carga y edita. No puede ver otros lodges. |
| `regional_manager` | Lectura de todos los lodges de su región. Escritura solo en lodges asignados explícitamente. Aprobación de observaciones de sus managers. |
| `gerencia` | Lectura de todo. No escritura. |
| `admin` | Todo (incluyendo modificar meses cerrados con audit). |

### X.5 Costos estimados de infra (los 40 lodges en prod)

| Componente | Costo mensual estimado |
|---|---|
| Supabase Pro (DB + Auth + Storage) | USD 25-100 (escala con volumen) |
| Vercel (frontend) | USD 0-20 (Hobby plan alcanza) |
| Cloud Run backend | USD 20-80 (depende de tráfico) |
| Sentry / monitoreo | USD 0-30 |
| **Total** | **USD 45-230 / mes** |

Comparado con el costo de un Excel administrado a mano (horas de gerencia
consolidando 40 archivos = literalmente decenas de horas/mes), la infra
es marginal.

### X.6 Onboarding escalonado

Los 40 lodges NO arrancan al mismo tiempo en producción.

1. **Piloto (2G)**: 3-5 lodges con managers receptivos. Diversidad regional.
   Modo dual durante todo el piloto.
2. **Cohorte 1 (2H semana 1-2)**: 8-10 lodges, principalmente de la misma
   región que el piloto (los managers regionales ya saben).
3. **Cohorte 2 (2H semana 3-4)**: 12-15 lodges, otras regiones.
4. **Cohorte 3 (2I)**: los últimos 10-15 + cleanup.

Cada cohorte tiene su propio modo dual y reconciliación de cierre antes de
deprecar el Excel.

---

## 13. Fuera de scope explícito

Para evitar scope creep:

- **No** vamos a reemplazar el sistema contable del cliente.
- **No** vamos a hacer presupuestación interactiva (eso es Excel para
  modelar; nosotros somos control de ejecución).
- **No** vamos a hacer pronósticos / forecasting (Fase 3+).
- **No** vamos a integrar con su POS o sistema de reservas (Fase 3+).
- **No** vamos a hacer reportes fiscales / AFIP / DGI.
