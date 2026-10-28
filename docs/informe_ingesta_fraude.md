# Informe — Ingesta y fraude (etapas 0, 1 y 6)

**Autor:** Axel · **Rol:** Ingesta y fraude

Este documento resume el aporte del integrante encargado de la entrada del
pipeline (etapas 0 y 1) y de la detección de fraude (etapa 6). En las tres el
criterio de diseño es el mismo: elegir la estructura de datos según la pregunta
que se hace y medirla contra la alternativa obvia de la librería estándar.

---

## Etapa 0 — Ingesta y buffer

**Función.** Recibe el stream de eventos y los entrega a la etapa 1 en lotes, en
el mismo orden de llegada, como una cola FIFO.

**Estructura.** Cola sobre **lista enlazada** con punteros a cabeza y cola:
encolar y desencolar en **O(1)** sin reubicar elementos. Los nodos usan
`__slots__` para bajar la memoria por nodo. Como alternativa de memoria fija se
implementó un **buffer circular**, que usa ~6× menos memoria a cambio de una
capacidad tope.

**Control de flujo.** Si el buffer se llena, `recibir` devuelve `False` y no se
pierde ningún evento; `procesar_stream` entrega un lote para liberar espacio
(contrapresión) y lo cuenta.

**Complejidad.** encolar/desencolar O(1); un lote sale apenas se completa, lo que
reduce la latencia.

**Resultados.** La elección de la estructura importa muchísimo: con 100 000
eventos, `list.pop(0)` tarda **16,8 s** (es O(n) por saque) frente a **0,057 s**
de la lista enlazada. A 1M, `collections.deque` (implementada en C) es ~5× más
rápida que la lista enlazada propia; la memoria pico a 1M es 48,0 MB (lista
enlazada) vs 8,0 MB (buffer circular).

---

## Etapa 1 — Preprocesamiento por lote

**Función.** Convierte cada lote crudo en uno limpio, ordenado por tiempo y sin
duplicados, listo para la etapa 2.

**Pasos y estructuras.**

- **Validación/normalización** (O(n)): tipos al contrato (tiempo a epoch UTC
  entero, ids a entero, precio a float, textos a minúsculas; marcas y categorías
  vacías pasan a `"desconocido"`). Los eventos inválidos se descartan con su
  motivo.
- **Ordenación**: **merge sort iterativo**, estable y **O(n log n)** en el peor
  caso, por la clave compuesta `(event_time, user_session, product_id,
  event_type, user_id, price)`. Un solo ordenamiento deja el lote en orden
  temporal y, de paso, junta las copias exactas.
- **Deduplicación**: exacta comparando vecinos en el lote ordenado (**O(n)**); y
  por ventana de tiempo para copias con timestamp desplazado, usando **búsqueda
  binaria** para ubicar el inicio de la ventana.
- **Consultas**: `lower_bound`/`upper_bound`/rango sobre el lote limpio en
  **O(log n)**.

**Decisión de diseño.** Se eligió merge sort (y no quicksort) por ser **estable**
—conserva el orden de llegada en empates, necesario para quedarse con la primera
copia— y por garantizar O(n log n) incluso en el peor caso.

**Resultados.** `procesar_lote` completo es O(n log n). Con entrada casi ordenada
(como llega el stream), la inserción es competitiva, pero con entrada aleatoria
merge sort mantiene su garantía mientras la inserción se dispara. De punta a
punta (1M en lotes de 1 000): precisión de deduplicación 100 %, **recall 99,7 %**
y ~59 000 eventos/s en esta etapa.

**Límite conocido.** Solo se detectan duplicados dentro del mismo lote.

---

## Etapa 6 — Detección de fraude (probabilístico)

**Función.** Sobre el stream ya limpio y priorizado, marca cada evento con una
decisión de fraude sin frenar el flujo. Es la etapa donde más se nota el canje
exactitud ↔ memoria: en un stream de pagos no se puede guardar todo de forma
exacta.

**Estructuras (a mano).**

- **Filtro de Bloom** para la *lista negra* de IP/dispositivos conocidos:
  responde "¿está fichado?" con *m* bits y *k* hashes (doble hashing sobre un
  `blake2b` de 128 bits). **Nunca da falsos negativos**, así que un fraude
  conocido jamás se escapa; a cambio admite falsos positivos acotados. O(k) por
  consulta.
- **Count-Min Sketch** para la *velocidad*: cuenta eventos por IP/dispositivo en
  una ventana de tiempo con memoria fija (*d*×*w* contadores). Devuelve el mínimo
  de *d* filas, así **nunca subestima** una ráfaga. O(d) por operación.

**Reglas.** Un evento es fraude si (1) está en la lista negra, (2) supera el
umbral de velocidad en su ventana, o (3) su identificador ya se delató antes y
quedó fichado en caliente (reincidente). Esto captura tanto al defraudador ya
conocido como al nuevo que se delata por su ritmo.

**Datos y evaluación.** Se amplió el generador sintético con
`generar_eventos_fraude`, que añade `ip`, `dispositivo_id`, `medio_pago` y la
etiqueta de verdad `es_fraude` (que el detector nunca mira para decidir; solo
sirve para medir precisión/recall).

**Resultados.**

| Comparación | Propio | Estándar | Lectura |
|---|---|---|---|
| Bloom vs `set` (1M claves) | **1,14 MB** | 48 MB | ~42× menos memoria; FP ≈ 1 % (objetivo), 0 falsos negativos |
| Count-Min vs `dict` (1M) | **0,13 MB (fija)** | 44 MB | memoria constante; nunca subestima; error relativo 0,0003 ≪ ε |
| Detector de fraude | **precisión 1,0 · recall ≈ 0,95** | — | ~14 000–19 000 eventos/s, escala lineal |

Integrado en el pipeline real (ingesta → limpieza → prioridad → fraude), el
detector mantiene **precisión 1,0 y recall 0,952**, pese al reordenamiento por
prioridad.

**Límites.** Los eventos del arranque de una ráfaga (antes de cruzar el umbral y
de fichar al actor) son el grueso de los falsos negativos; la ventana *tumbling*
cuenta un evento muy atrasado en la ventana vigente; y el Bloom de este diseño no
admite borrado/expiración.

---

## Conclusión del aporte

Las tres etapas muestran el mismo principio con datos distintos: la cola de la
etapa 0 convierte un O(n) en O(1), el merge sort estable de la etapa 1 garantiza
el peor caso, y las estructuras probabilísticas de la etapa 6 cambian un poco de
exactitud por memoria constante o casi constante. En todos los casos la versión
propia se midió contra la de la librería estándar: su ventaja no siempre es la
velocidad (las de C suelen ganar), sino **la complejidad garantizada y, sobre
todo, la memoria**, que es lo que decide si el pipeline escala a millones de
eventos.
