# pipeline-streams-eda

Pipeline de *streams* para comercio electrónico (dataset **REES46**), construido
como proyecto de **Estructuras de Datos y Algoritmos** (UTEC, 2026-2, Opción B).
Un flujo de 10 etapas procesa eventos de compra en orden de llegada y termina
recomendando productos, detectando fraude y respondiendo consultas, usando en
cada etapa la estructura de datos adecuada implementada **a mano** y comparada
contra su equivalente de la librería estándar.

## Roles del equipo

| Integrante | Rol | Etapas | Cuenta |
|---|---|---|---|
| **Axel** | Ingesta y fraude | 0 (ingesta), 1 (preprocesamiento), 6 (fraude) | `Axel12fuentes` |
| **Carlos Fukumoto** | Almacenamiento y grafo | 2 (prioridad), 3 (lookup), 4 (índice), 8 (grafo) | `kiyoshi05` |
| **Sebastián Gallegos** | Similitud y servicio | 5 (multidimensional), 7 (similitud), 9 (servicio) | `sebastiangallegosmostajo` |

## El pipeline

```
stream -> 0 ingesta -> 1 limpieza -> 2 prioridad -> 3 lookup -> 4 índice
       -> 5 multidim. -> 6 fraude -> 7 similitud -> 8 grafo -> 9 servicio
```

| Etapa | Qué hace | Estructura principal | Se compara contra |
|---|---|---|---|
| 0 Ingesta | buffer FIFO del stream, entrega por lotes | cola con lista enlazada / buffer circular | `deque`, `list.pop(0)` |
| 1 Preprocesamiento | validar, ordenar y deduplicar el lote | merge sort + búsqueda binaria | `sorted`, `set` |
| 2 Prioridad | entregar por urgencia | min-heap | `heapq` |
| 3 Lookup | ficha de producto y caché | tabla hash, LRU, matriz dispersa | `dict`, `OrderedDict` |
| 4 Índice | buscar por tiempo y por precio | B+Tree | listas ordenadas |
| 5 Multidimensional | vecinos por atributos | k-d tree + k-NN | fuerza bruta |
| 6 Probabilístico | **detección de fraude** | filtro de Bloom + Count-Min Sketch | `set`, `dict` |
| 7 Similitud | productos con compradores similares | MinHash LSH + IVF | Jaccard exacto |
| 8 Grafo | co-compra, influencia, comunidades | grafo + PageRank + Louvain | sistema lineal, `networkx` |
| 9 Servicio | recomendación y autocompletado | trie + top-k | — |

## Cómo correr

Requiere Python 3.11+ (probado en 3.13).

```bash
pip install -r requirements.txt
```

**Pruebas** (toda la suite):

```bash
python -m pytest -q
```

**App de demostración** (Streamlit):

```bash
streamlit run app.py
```

**Benchmarks** (ejemplo: etapa 6, de 1K a 1M) y sus figuras:

```bash
python -m experimentos.bench_etapa6 --n 100000
python -m experimentos.graficar_etapa6
```

## Datos

No se sube el dataset completo. El generador sintético con semilla vive en
`experimentos/datos_sinteticos.py` (reproduce el contrato de REES46, con
duplicados e inválidos etiquetados, y patrones de fraude con la etiqueta
`es_fraude`). En `data/sample/eventos.csv` hay una **muestra de 1 000 eventos**
para que la app y las pruebas corran sin descargar nada.

## Estructura del repositorio

```
src/            una carpeta por etapa (etapa0_ingesta ... etapa9_servicio)
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
