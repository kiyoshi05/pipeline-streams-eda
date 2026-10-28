# pipeline-streams-eda

Pipeline de *streams* para comercio electrónico (dataset **REES46**), construido
como proyecto de **Estructuras de Datos y Algoritmos** (UTEC, 2026-2, Opción B).
Un flujo de 10 etapas procesa eventos de compra en orden de llegada y termina
recomendando productos, detectando fraude y respondiendo consultas, usando en
cada etapa la estructura de datos adecuada implementada **a mano** y comparada
contra su equivalente de la librería estándar o un método exacto.

## Roles del equipo

| Integrante | Rol | Etapas | Cuenta |
|---|---|---|---|
| **Axel** | Ingesta y fraude | 0 (ingesta), 1 (preprocesamiento), 6 (fraude) | `Axel12fuentes` |
| **Carlos Fukumoto** | Almacenamiento y grafo | 2 (prioridad), 3 (lookup), 4 (índice), 8 (grafo) | `kiyoshi05` |
| **Sebastián Gallegos** | Similitud y servicio | 5 (multidimensional), 7 (similitud), 9 (servicio) | `sebastiangallegosmostajo` |

## El pipeline

El orquestador (`src/pipeline.py`) pasa cada lote del stream por las etapas de
flujo y, al cerrar el stream, arma las que trabajan sobre el catálogo completo:

```
por lote:   stream -> 0 ingesta -> 1 limpieza -> 6 fraude -> 2 prioridad
                   -> 3 lookup -> 4 índice -> 8 grafo
al cerrar:  5 multidimensional -> 7 similitud -> 9 servicio
```

La etapa 6 va antes que la 2 por dos razones: su ventana de velocidad necesita
los eventos en orden de tiempo (como salen de la 1) y la prioridad usa su
decisión (`fraude_predicho`). La etiqueta `es_fraude` del generador nunca se usa
para decidir: solo para medir precisión y recall.

| Etapa | Qué hace | Estructura principal | Se compara contra |
|---|---|---|---|
| 0 Ingesta | buffer FIFO del stream, entrega por lotes | cola con lista enlazada / buffer circular | `deque`, `list.pop(0)` |
| 1 Preprocesamiento | validar, ordenar y deduplicar el lote | merge sort + búsqueda binaria | `sorted`, `set` |
| 2 Prioridad | entregar por urgencia: fraude, express, estándar, programada, navegación | min-heap | `heapq`, lista ordenada |
| 3 Lookup | ficha de producto, caché y matrices usuario x producto | tabla hash, LRU, matriz dispersa | `dict`, `OrderedDict` |
| 4 Índice | consultas puntuales y por rango, por tiempo y por precio | B+Tree | lista ordenada + `bisect` |
| 5 Multidimensional | vecinos por atributos | k-d tree + k-NN | fuerza bruta |
| 6 Probabilístico | **detección de fraude** | filtro de Bloom + Count-Min Sketch | `set`, `dict` |
| 7 Similitud | productos parecidos y con compradores en común | IVF + MinHash LSH | KNN exacto, Jaccard exacto |
| 8 Grafo | co-compra, influencia, comunidades | grafo + PageRank + Louvain | ranking por grado, Label Propagation |
| 9 Servicio | recomendación y autocompletado | trie + top-k | — |

## Cómo correr

Requiere Python 3.11+ (probado en 3.13).

```bash
pip install -r requirements.txt
```

**Pipeline de punta a punta** (las 10 etapas, con alertas, ranking, recorrido de
un evento, consultas de productos y similitud frente al método exacto):

```bash
python run_pipeline.py
python run_pipeline.py --n 100000
python run_pipeline.py --csv data/sample/eventos.csv
```

**Pruebas** (toda la suite):

```bash
python -m pytest -q
```

**App de demostración** (Streamlit):

```bash
streamlit run app.py
```

**Benchmarks** y sus figuras (cada integrante tiene los suyos en `experimentos/`):

```bash
python -m experimentos.bench_etapas_0_1          # etapas 0 y 1
python -m experimentos.bench_etapa6 --n 100000   # etapa 6
python -m experimentos.graficar_etapa6
python -m experimentos.bench_estructuras_base    # etapas 2, 3 y 4
python -m experimentos.bench_comunidades         # etapa 8
python -m experimentos.graficar_etapas_2_3_4_8
```

## Datos

No se sube el dataset completo. Los generadores sintéticos con semilla están en
`experimentos/`:

- `stream_completo.py`: el stream que ejercita las 10 etapas (duplicados,
  inválidos, compras express y programadas, paquetes de compras conjuntas y
  fraude con la etiqueta `es_fraude`). `aumentar_filas` agrega esos campos a
  filas reales de REES46, que no los traen.
- `datos_sinteticos.py`: los generadores de las etapas 0, 1 y 6.

`data/sample/eventos.csv` es una **muestra sintética de 1 000 eventos** con las
columnas de REES46, para que la app y las pruebas corran sin descargar nada.
Se regenera con `experimentos.stream_completo.escribir_muestra`. La muestra real
de REES46 (archivo de octubre de 2019) está pendiente.

## Estructura del repositorio

```
src/            una carpeta por etapa (etapa0_ingesta ... etapa9_servicio) y pipeline.py
run_pipeline.py el pipeline de punta a punta desde la terminal
tests/          pruebas unitarias y de integración (unittest + pytest)
experimentos/   benchmarks, generador de datos, figuras y resultados (CSV)
docs/           documentación por etapa
data/sample/    muestra de 1K eventos
app.py          demo con Streamlit
```

## Forma de trabajo

Una rama por tarea e integración a `main` por *pull request* revisado por otro
integrante. Commits pequeños y frecuentes con la cuenta de cada autor. Todas las
mediciones son reproducibles con la semilla de `config.yaml`.
