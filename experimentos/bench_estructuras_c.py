import argparse
import csv
import random
import time
import tracemalloc
from pathlib import Path

from src.etapa5_multidimensional.kd_tree import KDTree
from src.etapa9_servicio.trie import Trie


def medir_construccion(funcion, medir_memoria):
    if medir_memoria:
        tracemalloc.start()

    inicio = time.perf_counter()
    objeto = funcion()
    segundos = time.perf_counter() - inicio

    pico_mb = None
    if medir_memoria:
        pico_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()

    return objeto, segundos, pico_mb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[1000, 10000, 100000])
    parser.add_argument("--consultas", type=int, default=50)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--salida", default="experimentos/resultados/estructuras_c.csv")
    parser.add_argument("--sin-memoria", action="store_true")
    args = parser.parse_args()

    resultados = []
    for n in args.sizes:
        rng = random.Random(args.semilla)

        puntos = [
            (i, tuple(rng.random() for _ in range(5)))
            for i in range(n)
        ]
        palabras = [f"producto_{i:08d}" for i in range(n)]

        arbol, kd_build, kd_mem = medir_construccion(
            lambda: KDTree(puntos), not args.sin_memoria
        )

        trie, trie_build, trie_mem = medir_construccion(
            lambda: construir_trie(palabras), not args.sin_memoria
        )

        indices = rng.sample(range(n), min(args.consultas, n))

        inicio = time.perf_counter()
        for i in indices:
            arbol.buscar(puntos[i][1], k=10, excluir_id=i)
        kd_query = (time.perf_counter() - inicio) / len(indices)

        prefijos = [palabras[i][:10] for i in indices]
        inicio = time.perf_counter()
        for prefijo in prefijos:
            trie.autocompletar(prefijo, k=10)
        trie_query = (time.perf_counter() - inicio) / len(prefijos)

        resultados.append({
            "n": n,
            "kd_build_s": kd_build,
            "kd_query_avg_s": kd_query,
            "kd_peak_mb": kd_mem,
            "trie_build_s": trie_build,
            "trie_query_avg_s": trie_query,
            "trie_peak_mb": trie_mem,
        })
        print(f"n={n}: KD build={kd_build:.3f}s, "
              f"Trie insert={trie_build:.3f}s")

        del arbol, trie, puntos, palabras

    ruta = Path(args.salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=resultados[0].keys())
        escritor.writeheader()
        escritor.writerows(resultados)

    print(f"Resultados guardados en {ruta}")


def construir_trie(palabras):
    trie = Trie()
    for palabra in palabras:
        trie.insertar(palabra)
    return trie


if __name__ == "__main__":
    main()