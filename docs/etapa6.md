# Etapa 6: detección de fraude con estructuras probabilísticas

Esta etapa recibe el stream ya limpio y ordenado (salida de las etapas 1 y 2) y
marca cada evento con una decisión de fraude, sin frenar el flujo. La idea de
estructuras de datos del reto es clara: en un stream de pagos no se puede guardar
todo de forma exacta, así que se cambia un poco de exactitud por mucha memoria.

## Qué estructura resuelve qué pregunta

| Pregunta sobre el evento | Estructura | Por qué no la versión exacta |
|---|---|---|
| ¿Esta IP/dispositivo ya está fichado por fraude? | **Filtro de Bloom** | un `set` guarda cada clave entera; el Bloom guarda solo bits (~1,2 B/clave con p=0,01) |
| ¿Cuántos eventos llegaron de esta IP/dispositivo en la ventana? | **Count-Min Sketch** | un `dict` crece con cada clave distinta (millones de IP); el sketch usa memoria fija |

## Etapa 6.1: filtro de Bloom (lista negra)

- **Función.** Responde "¿he visto esta clave?" con un arreglo de *m* bits y *k*
  hashes. Al agregar se encienden *k* bits; al consultar, si algún bit está en 0
  la clave **seguro no está**, y si todos están en 1 **probablemente sí**.
- **Garantía.** Nunca hay falsos negativos. Esto es justo lo que se necesita: un
  fraude ya conocido jamás debe escaparse. Un falso positivo (revisar de más un
  evento legítimo) es barato.
- **Dimensionado.** Para *n* claves y falso positivo *p*: `m = -n ln p / (ln2)²`
  bits y `k = (m/n) ln2` hashes. Con `p = 0,01` salen ~9,6 bits y ~7 hashes por
  clave.
- **Hashing.** Un solo `blake2b` de 128 bits por clave, partido en dos; los *k*
  índices se obtienen por doble hashing `g_i = (h1 + i·h2) mod m`, así no se
  calculan *k* hashes independientes.
- **Complejidad.** Agregar y consultar O(k) = O(1) respecto a *n*; memoria O(m).

## Etapa 6.2: Count-Min Sketch (velocidad)

- **Función.** Cuenta frecuencias con una tabla de *d* filas × *w* columnas. Al
  sumar una clave se incrementa, por fila, la columna que le toca; al estimar se
  devuelve el **mínimo** de esos *d* contadores.
- **Garantía.** La estimación nunca queda por debajo del valor real (las
  colisiones solo suman de más). Con `w = ⌈e/ε⌉` y `d = ⌈ln(1/δ)⌉`, el
  sobreconteo es `≤ ε · total` con probabilidad `≥ 1 − δ`.
- **Uso.** Cuenta eventos por IP y por dispositivo dentro de una **ventana
  *tumbling*** (`event_time // ventana_seg`). Al cambiar de ventana el sketch se
  reinicia, así se miden ráfagas recientes y no todo el histórico.
- **Complejidad.** Sumar y estimar O(d) = O(1) respecto al número de claves;
  memoria O(d·w), fija.

## Reglas de decisión

Un evento se marca como fraude si:

1. **Lista negra** — su IP o dispositivo está en el Bloom, **o**
2. **Velocidad** — su conteo en la ventana supera `umbral_velocidad`, **o**
3. **Sospechoso previo** — su IP/dispositivo ya disparó la velocidad antes y
   quedó fichado en caliente (un `set` pequeño de reincidentes).

La regla 3 imita a un sistema real: una vez que un actor se delata por su ritmo,
sus eventos siguientes se marcan de inmediato aunque cambien de ventana. Sube el
recall de los reincidentes sin tocar la precisión.

## Datos de prueba

El generador `experimentos/datos_sinteticos.py` incorpora
`generar_eventos_fraude(n)`, que añade al contrato los campos `ip`,
`dispositivo_id`, `medio_pago` y la etiqueta de verdad `es_fraude`. Crea dos
tipos de defraudador:

- **Conocidos** (van en la lista negra): los caza el Bloom incluso con un evento
  suelto.
- **Desconocidos** (no están en ninguna lista): se delatan con una ráfaga de
  eventos en la misma ventana; los caza el Count-Min por velocidad.

La etiqueta `es_fraude` solo se usa para medir precisión y recall; el detector
nunca la mira para decidir.

## Resultados

Mediciones con `python -m experimentos.bench_etapa6`
(Python 3.13, semilla 42; promedio de varias repeticiones). Ver las figuras en
`experimentos/figuras/etapa6_*.png` y los CSV en `experimentos/resultados/`.

- **Bloom vs `set`.** El filtro usa ~1,2 bytes por clave frente a decenas de
  bytes del `set` (clave + overhead del objeto): varios órdenes de magnitud menos
  memoria. La tasa de falsos positivos medida se mantiene cerca del 1 % objetivo.
  Nunca aparecieron falsos negativos.
- **Count-Min vs `dict`.** El sketch ocupa memoria fija (no crece con las claves
  distintas), mientras el `dict` crece lineal con ellas. La estimación nunca
  subestimó y el error relativo medio quedó muy por debajo de la cota `ε`.
- **Detector de fraude.** Sobre el generador sintético: **precisión 1,0** (sin
  falsas alarmas) y **recall ≈ 0,95**. Tiempo y memoria crecen de forma
  aproximadamente lineal con *n* (pendiente ≈ 1 en log-log).

## Limitaciones

- Los eventos de **arranque de una ráfaga** (los que llegan antes de cruzar el
  umbral y antes de fichar al actor) no se detectan: son el grueso de los falsos
  negativos y el porqué del recall < 1.
- La ventana *tumbling* cuenta un **evento muy atrasado** en la ventana vigente,
  no en la suya.
- El filtro de Bloom de este diseño **no admite borrado** ni expiración; para una
  lista negra que caduca haría falta un Bloom con contadores o uno rotatorio.
- Las reglas (umbral de velocidad, pesos del score) son simples y fijas; un
  sistema real las calibraría o usaría un modelo.
