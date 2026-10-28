"""Benchmarks de la etapa 6: Bloom vs set, Count-Min vs dict, y el detector completo.

Uso (desde la raíz del proyecto):
    python -m experimentos.bench_etapa6 --n 100000
    python -m experimentos.bench_etapa6 --n 1000 --repeticiones 5

Por cada n mide, promediando ``--repeticiones``:
  - construir la estructura (agregar/contar n claves) en tiempo y memoria pico,
    comparando la estructura propia contra su equivalente exacto de Python;
  - consultar (``--consultas`` búsquedas) en tiempo;
  - para la estructura propia, su calidad: tasa de falsos positivos del Bloom y
    error relativo del Count-Min;
  - el detector de fraude de punta a punta: eventos/s, precisión y recall.

Escribe un CSV por experimento en ``experimentos/resultados/`` con una fila por
n (se agrega si el archivo ya existe), listo para ``graficar_etapa6``.
"""

import argparse
import csv
import random
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from src.etapa6_probabilistico import CountMinSketch, Etapa6Fraude, FiltroBloom
from experimentos.datos_sinteticos import generar_eventos_fraude

CARPETA = Path("experimentos/resultados")


def _medir(construir, repeticiones):
    """Corre ``construir`` varias veces; devuelve (tiempos, memoria_pico_mb, ultimo)."""
    tiempos, memoria_mb, ultimo = [], None, None
    for r in range(repeticiones):
        if r == 0:
            tracemalloc.start()
        inicio = time.perf_counter()
        ultimo = construir()
        tiempos.append(time.perf_counter() - inicio)
        if r == 0:
            memoria_mb = tracemalloc.get_traced_memory()[1] / (1024 ** 2)
            tracemalloc.stop()
    return tiempos, memoria_mb, ultimo


def _fila(nombre, tiempos, memoria_mb, extra):
    fila = {
        "estructura": nombre,
        "construccion_media_s": statistics.mean(tiempos),
        "construccion_desv_s": statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0,
        "memoria_pico_mb": memoria_mb,
    }
    fila.update(extra)
    return fila


def bench_bloom(n, claves, consultas_ausentes, repeticiones):
    def construir_bloom():
        b = FiltroBloom(n_esperado=n, prob_fp=0.01)
        b.actualizar(claves)
        return b
    tiempos, memoria, bloom = _medir(construir_bloom, repeticiones)
    inicio = time.perf_counter()
    fp = sum(1 for c in consultas_ausentes if c in bloom) / max(1, len(consultas_ausentes))
    t_consulta = (time.perf_counter() - inicio) / max(1, len(consultas_ausentes))

    def construir_set():
        s = set()
        s.update(claves)
        return s
    t_set, mem_set, _ = _medir(construir_set, repeticiones)

    return [
        _fila("bloom_propio", tiempos, memoria,
              {"n": n, "consulta_media_s": t_consulta, "falsos_positivos": fp,
               "fp_objetivo": 0.01}),
        _fila("set_python", t_set, mem_set,
              {"n": n, "consulta_media_s": 0.0, "falsos_positivos": 0.0, "fp_objetivo": 0.0}),
    ]


def bench_count_min(n, claves, repeticiones):
    exact = Counter(claves)
    total = sum(exact.values())

    def construir_cm():
        cm = CountMinSketch(epsilon=0.001, delta=0.01, semilla=1)
        for c in claves:
            cm.sumar(c)
        return cm
    tiempos, memoria, cm = _medir(construir_cm, repeticiones)
    errores = [cm.estimar(k) - v for k, v in exact.items()]
    error_rel = (sum(errores) / len(errores)) / max(1, total)

    def construir_dict():
        d = Counter()
        for c in claves:
            d[c] += 1
        return d
    t_dict, mem_dict, _ = _medir(construir_dict, repeticiones)

    return [
        _fila("count_min_propio", tiempos, memoria,
              {"n": n, "claves_distintas": len(exact), "error_relativo_medio": error_rel,
               "subestima": int(any(e < 0 for e in errores))}),
        _fila("dict_python", t_dict, mem_dict,
              {"n": n, "claves_distintas": len(exact), "error_relativo_medio": 0.0,
               "subestima": 0}),
    ]


def bench_detector(n, eventos, lista_negra, repeticiones):
    def correr():
        e6 = Etapa6Fraude(lista_negra=lista_negra, ventana_seg=10, umbral_velocidad=8)
        e6.procesar(eventos)
        return e6
    tiempos, memoria, e6 = _medir(correr, repeticiones)
    m = e6.metricas()
    eventos_por_s = n / statistics.mean(tiempos)
    return [_fila("detector_fraude", tiempos, memoria,
                  {"n": n, "eventos_por_s": eventos_por_s,
                   "precision": m["precision"], "recall": m["recall"],
                   "marcados": m["marcados"]})]


def _guardar(nombre, filas):
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA / f"etapa6_{nombre}.csv"
    columnas = list(filas[0].keys())
    existe = ruta.exists()
    with ruta.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        if not existe:
            escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)
    print(f"  -> {ruta}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--consultas", type=int, default=50_000)
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args(argv)

    azar = random.Random(args.semilla)
    claves = [f"ip:{azar.getrandbits(32):08x}" for _ in range(args.n)]
    ausentes = [f"no:{azar.getrandbits(32):08x}" for _ in range(args.consultas)]
    eventos, lista_negra = generar_eventos_fraude(args.n, semilla=args.semilla)

    print(f"n={args.n}  (repeticiones={args.repeticiones})")
    _guardar("bloom", bench_bloom(args.n, claves, ausentes, args.repeticiones))
    _guardar("count_min", bench_count_min(args.n, claves, args.repeticiones))
    _guardar("detector", bench_detector(args.n, eventos, lista_negra, args.repeticiones))


if __name__ == "__main__":
    main(sys.argv[1:])
