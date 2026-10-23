import argparse
import random
import time
import tracemalloc
from statistics import mean

from src.etapa5_multidimensional.knn import knn_exacto
from src.etapa7_similitud.ivf import IVFFlat


def recall_at_k(exacto, aproximado):
    ids_exactos = {id_ for id_, _ in exacto}
    ids_aproximados = {id_ for id_, _ in aproximado}
    return len(ids_exactos & ids_aproximados) / max(1, len(ids_exactos))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--consultas", type=int, default=25)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--clusters", type=int, default=32)
    parser.add_argument("--nprobe", type=int, default=4)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.semilla)
    puntos = [
        (i, tuple(rng.random() for _ in range(5)))
        for i in range(args.n)
    ]

    tracemalloc.start()
    inicio = time.perf_counter()
    indice = IVFFlat(
        puntos,
        n_clusters=args.clusters,
        nprobe=args.nprobe,
        semilla=args.semilla,
    )
    tiempo_construccion = time.perf_counter() - inicio
    memoria_pico_mb = tracemalloc.get_traced_memory()[1] / (1024**2)
    tracemalloc.stop()

    tiempos_exactos = []
    tiempos_ivf = []
    recalls = []

    for id_consulta, vector in puntos[:min(args.consultas, args.n)]:
        inicio = time.perf_counter()
        exacto = knn_exacto(puntos, vector, args.k, excluir_id=id_consulta)
        tiempos_exactos.append(time.perf_counter() - inicio)

        inicio = time.perf_counter()
        aproximado = indice.buscar(vector, args.k, excluir_id=id_consulta)
        tiempos_ivf.append(time.perf_counter() - inicio)

        recalls.append(recall_at_k(exacto, aproximado))

    print(f"Vectores: {args.n}")
    print(f"Clusters: {indice.n_clusters} | nprobe: {indice.nprobe}")
    print(f"Construcción IVF: {tiempo_construccion:.4f} s")
    print(f"Consulta exacta promedio: {mean(tiempos_exactos):.6f} s")
    print(f"Consulta IVF promedio: {mean(tiempos_ivf):.6f} s")
    print(f"Recall@{args.k} promedio: {mean(recalls):.3f}")
    print(f"Pico de memoria de construcción: {memoria_pico_mb:.2f} MB")


if __name__ == "__main__":
    main()