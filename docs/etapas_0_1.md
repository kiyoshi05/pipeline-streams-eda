# Etapas 0 y 1: ingesta y preprocesamiento

Parte del pipeline del proyecto EDA 2026-2 (Opción B, comercio electrónico, REES46).

- **Etapa 0, ingesta y buffer:** cola FIFO sobre lista enlazada. Recibe el stream y entrega lotes en orden de llegada.
- **Etapa 1, preprocesamiento por lote:** valida y normaliza, ordena con merge sort, deduplica y usa búsqueda binaria. Entrega a la etapa 2 un lote limpio, ordenado por tiempo y sin duplicados.

## Archivos

```text
src/etapa0_ingesta/cola_fifo.py                  ColaFIFO (lista enlazada) y BufferCircular (alternativa)
src/etapa0_ingesta/ingesta.py                    Etapa0Ingesta (buffer + lotes) y leer_csv (REES46 por partes)
src/etapa1_preprocesamiento/ordenacion.py        merge_sort (el que usa la etapa), quicksort, insercion
src/etapa1_preprocesamiento/busqueda.py          lower_bound, upper_bound, contiene, rango, busqueda_lineal
src/etapa1_preprocesamiento/preprocesamiento.py  validación, claves, deduplicación, procesar_lote, Etapa1Preprocesamiento
tests/test_etapa0.py                             pruebas de la etapa 0
tests/test_etapa1.py                             pruebas de la etapa 1 y de la integración 0 -> 1
experimentos/datos_sinteticos.py                 eventos de prueba con duplicados etiquetados (no es el generador oficial)
experimentos/bench_etapas_0_1.py                 benchmarks: un CSV por experimento en experimentos/resultados/
experimentos/graficar_etapas_0_1.py              gráficos log-log en experimentos/figuras/ y tabla de pendientes
demo_etapas_0_1.py                               demo de punta a punta de las dos etapas
```

Solo usa la biblioteca estándar de Python. Los gráficos necesitan `matplotlib` y las pruebas corren con `pytest` o con `unittest`.

## Cómo correrlo

Todos los comandos se ejecutan desde la raíz del proyecto.

Pruebas (46 pruebas):

```bash
python -m pytest
```

Demo con 20.000 eventos sintéticos:

```bash
python demo_etapas_0_1.py
```

Demo con el CSV real de REES46 (cambia la ruta por la tuya):

```bash
python demo_etapas_0_1.py --csv "C:/ruta/2019-Oct.csv" --limite 200000
```

Prueba rápida de los benchmarks (menos de un minuto):

```bash
python -m experimentos.bench_etapas_0_1 --rapido
```

Benchmarks para el informe: 1K, 10K y 100K con 100 repeticiones. Calcula unos 10 minutos.

```bash
python -m experimentos.bench_etapas_0_1
```

Benchmarks hasta 10M. Es una estimación: alrededor de una hora y 2–3 GB de RAM.

```bash
python -m experimentos.bench_etapas_0_1 --tamanos 1000 10000 100000 1000000 10000000
```

Gráficos y tabla de pendientes a partir de los CSV:

```bash
python -m experimentos.graficar_etapas_0_1
```

## Integración con el resto del pipeline

1. **Clase Evento.** Las etapas aceptan `dict`, `dataclass`, `namedtuple` u objetos con atributos, así que no dependen de `src/comun/evento.py`. Cuando exista, para leer REES46 directamente como Evento usa `leer_csv(ruta, a_evento=lambda d: Evento(**d))`.
2. **Contrato de salida (acordarlo con el grupo).** Después de la etapa 1:
   - `event_time` es un entero (segundos epoch, UTC);
   - `product_id` y `user_id` son enteros;
   - `price` es float;
   - `event_type`, `brand` y `category_code` van en minúsculas;
   - los `brand` y `category_code` vacíos pasan a `"desconocido"`.
3. **Configuración.** `capacidad` y `tam_lote` deben salir de `config.yaml`. Por defecto son 10.000 y 1.000.
4. **Orquestador.**

   ```python
   etapa0 = Etapa0Ingesta(capacidad=10_000, tam_lote=1_000)
   etapa1 = Etapa1Preprocesamiento(ventana_seg=0)
   for lote in etapa0.procesar_stream(fuente):
       resultado = etapa1.procesar(lote)
       etapa2.recibir(resultado.eventos)  # el nombre depende de la interfaz de la etapa 2
   ```

5. **Medición común.** `experimentos/bench_etapas_0_1.py` mide con una función local `medir()`. Cuando exista `src/comun/medicion.py`, cámbiala por la común.

## Decisiones de diseño

**Etapa 0**

| Decisión | Motivo |
|---|---|
| Lista enlazada con punteros a cabeza y cola | Encolar y desencolar O(1) sin recorrer nada. `__slots__` en el nodo para reducir memoria. |
| Buffer circular como alternativa | Usa unas 6 veces menos memoria (no crea un objeto por elemento), pero necesita capacidad fija. |
| Buffer lleno: `recibir` devuelve False | No se pierde ningún evento. `procesar_stream` entrega un lote para liberar espacio y lo cuenta como contrapresión. |
| Entrega en cuanto hay un lote completo | Menor latencia hacia la etapa 1. El último lote puede ser menor. |

**Etapa 1**

| Decisión | Motivo |
|---|---|
| Una sola clave `(event_time, user_session, product_id, event_type, user_id, price)` | Un único ordenamiento deja el lote en orden temporal para la etapa 2 y pone las copias exactas una al lado de otra. |
| Merge sort iterativo | O(n log n) en el peor caso y estable, así la copia que se conserva es la que llegó primero. Sin recursión y con la clave calculada una vez por elemento. |
| Deduplicación exacta por vecinos (por defecto) | O(n) sobre el lote ordenado. |
| Deduplicación con ventana (`ventana_seg > 0`) | Para copias con el timestamp desplazado. La búsqueda binaria ubica en O(log n) el inicio de la ventana. |
| Búsqueda binaria también en `eventos_en_rango` y `contiene_evento` | Consultas por rango de tiempo y de pertenencia sobre el lote limpio en O(log n). |
| Métricas de calidad contra `es_duplicado` | Precisión y recall. Valen `None` si los eventos no traen la etiqueta, como REES46 sin el generador. |

**Límite conocido:** solo se detectan duplicados dentro del mismo lote. Si la copia cae en el lote siguiente, se escapa. Con lotes de 1.000 el recall medido fue 99,7%.

## Complejidad

| Operación | Tiempo | Espacio |
|---|---|---|
| encolar, desencolar, frente | O(1) | O(1) por elemento |
| desencolar_lote(k) | O(k) | O(k) |
| validar y normalizar un lote | O(n) | O(n) |
| merge sort | O(n log n) | O(n) |
| deduplicación exacta | O(n) | O(n) |
| deduplicación con ventana | O(n log n + n·w) | O(n) |
| lower_bound, upper_bound, contiene | O(log n) | O(1) |
| procesar_lote completo | O(n log n) | O(n) |

## Resultados preliminares

Son de una corrida de comprobación en la laptop de desarrollo (Intel Core Ultra 7 165U, 16 GB, Python 3.13) con solo 5 repeticiones, de 1K a 100K. Sirven para saber qué esperar; no los uses en el informe. Corre el benchmark completo.

- **Cola.** Lista enlazada y buffer circular crecen de forma lineal (pendiente cercana a 1,1). `list.pop(0)` es cuadrática (pendiente 2,2): a 100K tardó 2,2 s contra 0,04 s de la lista enlazada. `deque` es unas 5 veces más rápida porque está escrita en C.
- **Memoria de la cola a 100K.** Lista enlazada 4,8 MB, buffer circular 0,8 MB.
- **Ordenación.**
  - En orden aleatorio, la inserción es cuadrática (pendiente 2,5) y tardó 6,4 s con solo 10K.
  - El stream llega casi ordenado por tiempo, y ahí la inserción casi no necesita mover elementos: fue unas 2 veces más rápida que merge sort.
  - Timsort (`sorted`) fue unas 12 veces más rápido que el merge sort propio. Es esperable: está en C y aprovecha los tramos ya ordenados.
  - Esto vale para defender en el informe: merge sort garantiza O(n log n) aunque el stream llegue desordenado.
- **Deduplicación a 100K.** `set` y "sorted + vecinos" tardan casi lo mismo (0,04 s), pero el `set` usa 7,0 MB frente a 1,6 MB y no deja el lote ordenado.
- **Búsqueda a 100K.** 100 consultas binarias tardaron 0,2 ms y la búsqueda lineal 1,1 s.
- **Etapa 1 completa.** Entre 70.000 y 220.000 eventos por segundo según la corrida. Precisión de la deduplicación 100%, recall 99,7%.

Las pendientes salieron algo por encima de la teoría: alrededor de 1,2–1,3 en operaciones lineales. Hay dos causas probables. Con más datos, los objetos ya no caben en la caché del procesador. Además, este procesador tiene núcleos de rendimiento y de eficiencia, y Windows mueve el proceso entre ellos, lo que da mucha variación entre corridas.

Para las mediciones oficiales:
- laptop enchufada y en modo de energía "Mejor rendimiento";
- terminal en primer plano y otros programas cerrados;
- reportar el promedio y también el mínimo (`min_s`).

El benchmark avisa si la laptop está en batería y lo registra en la columna `plataforma` de cada CSV (`energia: bateria` o `energia: corriente`). También pide a Windows que no lo ponga en modo de eficiencia aunque la terminal quede en segundo plano.

Una corrida de prueba (en batería o con pocas repeticiones) va a otra carpeta con `--salida`, para no mezclarla con los resultados oficiales de `experimentos/resultados/`, y no se sube al repo.

## Pendientes

- Probar con la clase real de `src/comun/evento.py`.
- Definir con quien haga el generador si los duplicados son copias exactas o con el tiempo desplazado (`ventana_seg`), y si cada copia lleva el id del evento original.
- Confirmar con el profesor que se aceptan menos repeticiones en 1M y 10M.
- Correr los benchmarks oficiales y generar las figuras para el informe.
