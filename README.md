# pipeline-streams-eda

Pipeline de *streams* para comercio electrónico (dataset **REES46**), construido
como proyecto de **Estructuras de Datos y Algoritmos** (UTEC, 2026-2, Opción B).
Un flujo de 10 etapas procesa eventos de compra en orden de llegada y termina
recomendando productos, detectando fraude y respondiendo consultas, usando en
cada etapa la estructura de datos adecuada implementada **a mano** y comparada
contra su equivalente de la librería estándar o un método exacto.

## Entregables

| Entregable | Dónde |
|---|---|
| Informe final (15 páginas: portada, contenido y referencias) | [`Proyecto_Final_Grupo_1.pdf`](Proyecto_Final_Grupo_1.pdf) |
| Código fuente, una carpeta por etapa | [`src/`](src/) |
| Diagrama del pipeline | [`docs/diagrama_pipeline.html`](docs/diagrama_pipeline.html) |
| Notebooks | [`notebooks/pipeline_completo.ipynb`](notebooks/pipeline_completo.ipynb) (las 10 etapas, con datos sintéticos o reales) y [`notebooks/ingesta_y_fraude.ipynb`](notebooks/ingesta_y_fraude.ipynb) |
| Benchmarks: scripts, resultados y figuras | [`experimentos/`](experimentos/) |

## Roles del equipo y contribución individual

Cada integrante es responsable principal de sus etapas y aporta en la misma
medida al código, a las mediciones, a la integración y a los entregables. El
reparto coincide con los autores de los commits y de los pull requests del
historial.

| Integrante | Rol | Etapas (responsable principal) | Aporte concreto | Cuenta |
|---|---|---|---|---|
| **Axcel Fuentes** | Ingesta y fraude | 0 (ingesta), 1 (preprocesamiento), 6 (fraude) | Cola FIFO y buffer circular; validación, merge sort, deduplicación y búsqueda binaria; filtro de Bloom, Count-Min Sketch y detector de fraude. Generador sintético con fraude y muestra de 1K eventos. Benchmarks de las etapas 0, 1 y 6. Notebooks, diagrama del pipeline y sección del informe de sus etapas. | `Axel12fuentes` |
| **Carlos Fukumoto** | Almacenamiento y grafo | 2 (prioridad), 3 (lookup), 4 (índice), 8 (grafo) | MinHeap y cola con prioridades; tabla hash con hashing de Fibonacci, caché LRU y matriz dispersa; B+Tree por tiempo y por precio; grafo de co-compra, PageRank, Louvain y Label Propagation. Orquestador del pipeline (`src/pipeline.py`, `run_pipeline.py`) y pruebas de punta a punta. Benchmarks de las etapas 2, 3, 4 y 8. Sección del informe de sus etapas. | `kiyoshi05` |
| **Sebastián Gallegos** | Similitud y servicio | 5 (multidimensional), 7 (similitud), 9 (servicio) | KD-Tree y KNN exacto; IVF y MinHash + LSH; Top-K con heap, Trie y servicio de recomendaciones. Panel de Streamlit (`app.py`) con recomendaciones e influencia. Benchmarks de KD-Tree, Trie y MinHash. Sección del informe de sus etapas. | `sebastiangallegosmostajo` |

Trabajo compartido por los tres: integración de las etapas por *pull request*
revisado, informe final y presentación.

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
python run_pipeline.py --csv data/raw/2019-Oct.csv --limite 100000 --cache 2000
```

**Notebook** con el pipeline completo (en la primera celda se elige
`FUENTE = "sintetico"` o `"real"`):

```bash
jupyter notebook notebooks/pipeline_completo.ipynb
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
Se regenera con `experimentos.stream_completo.escribir_muestra`.

**Datos reales.** El archivo de octubre de 2019 de REES46 (unos 5 GB) se descarga
de Kaggle y se guarda en `data/raw/`, que git ignora. El pipeline se probó con
100.000 eventos reales: 138 s en total, con 258 MB de memoria pico.

## Estructura del repositorio

```
src/            una carpeta por etapa (etapa0_ingesta ... etapa9_servicio) y pipeline.py
run_pipeline.py el pipeline de punta a punta desde la terminal
tests/          pruebas unitarias y de integración (unittest + pytest)
experimentos/   benchmarks, generador de datos, figuras y resultados (CSV)
notebooks/      pipeline completo e ingesta y fraude
docs/           documentación por etapa y diagrama del pipeline
data/sample/    muestra de 1K eventos (data/raw/ para REES46, ignorada por git)
app.py          panel con Streamlit
Proyecto_Final_Grupo_1.pdf   informe final
```

## Forma de trabajo

Una rama por tarea e integración a `main` por *pull request* revisado por otro
integrante. Commits pequeños y frecuentes con la cuenta de cada autor. Todas las
mediciones son reproducibles con la semilla de `config.yaml`.
