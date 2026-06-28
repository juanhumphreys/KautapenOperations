# Plan de implementación — Demo control de costos por bednight (30/6)

> Documento de contexto para Claude Code. Es **spec, no código**. Captura las
> decisiones ya tomadas para que la implementación arranque directo.
> Stack objetivo: **Supabase (Postgres)** + import único desde los Excel.

---

## 1. Contexto del negocio

Grupo de **lodges de pesca** (operación: Kautapen Group). El área de operaciones
controla gastos mes a mes contra un budget anual, en USD, normalizando por noche.
Hoy todo el control se arma a mano en Excel. El objetivo del demo es **automatizar
el control mensual budget-vs-real por bednight con detección de desvíos**, validándolo
contra el cierre de abril/mayo 2026 que ellos ya analizaron a mano.

**Métrica central:** gasto por cuenta / denominador, en USD, comparado contra budget.
Esto NO es una métrica que inventamos: los archivos de budget ya tienen columnas
"En Dólares x bednight". El valor agregado es automatizar el cálculo + el flagging.

---

## 2. Decisión de scope para el 30/6

**ENTRA:** control de costos por bednight (la data ya existe y está completa para Delta).
**NO ENTRA (fase 2):** stock por unidades físicas (kg/L). Esa data NO está en los
archivos — depende de la app de compras que todavía no existe. No se puede calcular
lo que no se puede medir.

El "módulo de stocks" prometido en la reunión se cubre parcialmente vía la hoja
`Stock - Deudas`, que es **stock valorizado por concepto** (no por unidades). Se
muestra ese ángulo y se presenta el stock-por-unidades como el próximo escalón.

---

## 3. Realidad de la data (lo más importante)

La granularidad es **CUENTA CONTABLE, no insumo físico**. Cada movimiento ya viene
tageado a un código de cuenta del plan de cuentas. No hay detalle de ítems tipo
"jabón líquido 5L x20" — la comida del mes es un monto asignado a la cuenta 5250.

**Consecuencia 1:** el problema de matching de nombres sucios (jabón = liquid soap)
NO aplica acá. La canonicalización es agrupar por número de cuenta — determinista
y trivial. Un matcher de ítems queda reservado para la fase de la app de compras,
donde los managers cargan texto libre con detalle de ítems.

**Consecuencia 2:** toda la métrica trabaja sobre cuentas valorizadas en USD.

### Archivos y hojas relevantes

Archivos de **control** (movimientos reales, uno por región):
- `DELTA_ECONOMICO_..._al_31-05-2026.xlsx` → lodge Delta (DEL).
- `URUGUAY_ECONOMICO_..._Budget_Nuevo.xlsx` → Carmelo (CAR), San Juan (SJ).

Archivos de **budget** (uno por lodge):
- `Budget_DEL_25-26.xlsx`, `Budget_El_Tobar_25-26.xlsx`, `Budget_Jacana_25-26.xlsx`.

Hojas clave dentro de los archivos de control:
- `Mov_Analizados_<mes>` → transacciones del mes (la fuente principal).
- `Plan Cuentas Link Armado` → jerarquía de cuentas (dimensión canónica).
- `Budget Comparativo` → comparación budget-vs-real con BN/Pax/FD y observaciones.
- `Stock - Deudas` → stock valorizado por concepto.
- `Resumen_Base` → acumulado por cuenta y período.

### Estructura de `Mov_Analizados_<mes>`

La tabla real **arranca cerca de la fila 10**; arriba hay celdas sueltas de resumen
(totales, TC de referencia, links). **El header está mal alineado respecto de los
datos** — no mapear columnas por la etiqueta del header. Detectar la tabla por
contenido: la fila de datos tiene código de lodge (DEL/CAR/SJ) en una columna y un
número de cuenta en la siguiente.

Columnas de datos (verificar al cargar, aprox.):
- Lodge (nombre completo, ej. "Delta") y código de lodge (ej. "DEL").
- Concepto (texto libre, a veces en inglés: "Food & Wine", "Electricity - Gas for...").
- Cuenta (código, ej. 5250) y Nombre de cuenta (ej. "Comidas y Refrigerios").
- Clave compuesta lodge+cuenta (ej. "DEL5250").
- monto $ (pesos ARS), monto USD, TC (tipo de cambio del movimiento), Fecha.

### Estructura de `Plan Cuentas Link Armado`

Header en fila ~3. Columnas: Rubro Principal / Rubro Secundario / Rubro Final /
N° Cuenta / Descripción Cuenta. Es la **dimensión de cuentas** (tabla canónica).
Ya existe — no hay que construirla.

### Estructura de `Budget Comparativo` y archivos de budget

- `Budget Comparativo` trae por lodge: Total BN, Total Pax, Meses transcurridos,
  y por cuenta el budget, real, diferencia y una **columna de Observaciones** con
  juicios escritos a mano ("Por encima del budget...", etc.).
- Los archivos `Budget_<lodge>` tienen parámetros (BN, FD, Pax, fechas) y columnas
  explícitas **"En Dólares x bednight"** para Budget 25-26 / Real 24-25 / Real 23-24.
  Hay TC fijo (ej. 1450) para el budget.

---

## 4. Decisiones de modelado (fijar desde el arranque)

1. **Moneda: USD siempre.** La inflación en ARS hace inútil comparar meses en pesos.
   Usar el `monto USD` de cada movimiento (ya trae el TC aplicado por fecha).
2. **Denominador según tipo de cuenta** (esto es un diferenciador, no dividir todo
   por BN como hacen a mano):
   - **BN (bednights = huésped-noche, CONFIRMADO):** comida, limpieza, lodging,
     insumos que escalan con la cantidad de huéspedes-noche.
   - **FD (Fishing Days, CONFIRMADO):** guías, nafta de lanchas, alquiler de armas,
     todo lo que escala con días de pesca, no con noches de cama.
   - El mapeo cuenta→denominador hay que definirlo (ver Pendientes). Default: BN.
3. **BN = huésped-noche.** Confirmado: en Delta budget figura BN 375 / Pax 187 (≈2
   noches por huésped).
4. **Clave de agregación:** (lodge, cuenta, mes). Sumar `monto USD` por esa clave.

---

## 5. Pipeline a implementar

1. **Parser de `Mov_Analizados_<mes>`** — saltear el layout de reporte, detectar la
   tabla por contenido (no por header), normalizar a filas: lodge, cuenta, nombre,
   concepto, monto_usd, tc, fecha, mes. Descartar/loggear filas con `#REF!`/`#N/A`.
2. **Dimensión de cuentas** desde `Plan Cuentas Link Armado` (rubro→cuenta).
3. **Dimensión de denominadores** por (lodge, mes): BN, Pax, FD desde `Budget Comparativo`.
4. **Cálculo:** gasto USD por (lodge, cuenta, mes) ÷ denominador adecuado al tipo de
   cuenta → costo por bednight (o por fishing day) por cuenta.
5. **Comparación vs. budget:** usar las columnas "En Dólares x bednight" de los
   archivos de budget → varianza por cuenta (real vs budget).
6. **Flagging** (reglas simples, sin ML):
   - desvío vs budget > umbral (ver Pendientes),
   - salto mes-a-mes (abril→mayo) por encima de umbral,
   - monto atípico dentro del mes (outlier respecto del histórico de la cuenta).
7. **Validación:** cruzar los flags generados contra la columna de Observaciones de
   abril/mayo. ¿Reproducimos sus juicios? ¿Aparece algo que se les pasó?

> **Curado manual:** el motor genera todos los flags que quiera; en la demo se
> muestran solo los 3-4 reales + el que se les pasó. No mostrar output crudo en vivo.
> El riesgo principal son falsos positivos por artefactos de planilla (una cuenta que
> figura en cero un mes por estar cargada distinto), no por la lógica.

---

## 6. Cobertura de data (limitación a tener en cuenta)

Los archivos NO se solapan parejo:

| Lodge        | Movimientos (real) | Budget |
|--------------|--------------------|--------|
| Delta (DEL)  | Sí (abr/may)       | Sí     |
| Carmelo      | Sí                 | No     |
| San Juan     | Sí                 | No     |
| El Tobar     | No                 | Sí     |
| Jacana       | No                 | Sí     |

**El único lodge end-to-end completo es Delta.** El demo se arma sobre Delta y se
presenta como "corre igual para los demás cuando carguemos sus archivos". Para
mostrar más de un lodge hace falta pedir budget de Carmelo/SJ o movimientos de
El Tobar/Jacana.

---

## 7. Gotchas de parsing

- Layout de "reporte": headers dispersos en filas superiores, tabla real desde ~fila 10.
- **Header mal alineado con los datos** → detectar columnas por contenido, no por etiqueta.
- `#REF!` y `#N/A` por fórmulas rotas → filtrar y loggear, no romper.
- Hojas NO estandarizadas entre lodges (uno tiene "Real 2024", otro "Real al 31-7-24",
  Jacana no tiene hoja de real). No asumir nombres de hoja fijos; resolver por patrón.
- Doble moneda por fila (ARS y USD con TC propio) → usar siempre USD.

---

## 8. Explícitamente FUERA del 30/6

Para no sobre-prometer (esto es prototipo de validación, no herramienta final):
- UI de carga multiusuario (los managers cargando desde los lodges).
- App de stock por unidades físicas.
- Paso LLM del matcher de ítems.
- Todo el bloque de infra/deploy (Cloud Run, containers, Secret Manager, KMS, etc.):
  eso recién cuando pase de demo a herramienta viva.
- Import: de una sola vez desde los Excel a Supabase. Nada de flujo de entrada.

---

## 9. Pendientes a confirmar con el cliente (bloquean afinado, no el arranque)

1. **Umbral de "alerta"**: ¿qué % de desvío vs budget consideran flag? (¿10%? ¿15%?).
2. **Mapeo cuenta→denominador (BN vs FD)**: ¿lo define el dev a criterio o lo
   confirman ellos cuenta por cuenta? Default propuesto: BN, salvo guías/nafta
   lanchas/armas → FD.
3. (Menor) Confirmar que las Observaciones de abril/mayo son la "verdad" contra la
   que validamos.
