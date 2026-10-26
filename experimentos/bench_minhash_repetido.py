import argparse
import csv
import random
import statistics
import time
import tracemalloc
from pathlib import Path

from src.etapa7_similitud.minhash_lsh import MinHashLSH


def generar_conjuntos(n, cantidad_usuarios, semilla):
    rng = random.Random(semilla)
    comunidades = 20
    base = [
        set(rng.sample(range(cantidad_usuarios), min(50, cantidad_usuarios)))
        for _ in range(comunidades)
    ]

    conjuntos = {}
    for producto in range(n):
        usuarios_base = base[producto % comunidades]
        conservar = max(1, int(len(usuarios_base) * 0.8))
        usuarios = set(rng.sample(sorted(usuarios_base), conservar))

        # Agrega algunos usuarios fuera del grupo para variar cada producto.
        extra = min(5, cantidad_usuarios - len(usuarios))
        if extra > 0:
            disponibles = list(set(range(cantidad_usuarios)) - usuarios)
            usuarios.update(rng.sample(disponibles, min(extra, len(disponibles))))

        conjuntos[producto] = usuarios

    return conjuntos


def topk_exacto(conjuntos, producto, k):
    objetivo = conjuntos[producto]
    resultados = []

    for otro, usuarios in conjuntos.items():
        if otro == producto:
            continue
        union = objetivo | usuarios
        jaccard = len(objetivo & usuarios) / len(union) if union else 0.0
        resultados.append((otro, jaccard))

    return sorted(resultados, key=lambda x: (-x[1], str(x[0])))[:k]


def recall_at_k(exacto, aproximado):
    ids_exactos = {id_ for id_, _ in exacto}
    ids_aproximados = {id_ for id_, _ in aproximado}
    return len(ids_exactos & ids_aproximados) / max(1, len(ids_exactos))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--usuarios", type=int, default=5000)
    parser.add_argument("--consultas", type=int, default=100)
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    conjuntos = generar_conjuntos(args.n, args.usuarios, args.semilla)

    tiempos_construccion = []
    memoria_pico_mb = None
    modelo = None

    for repeticion in range(args.repeticiones):
        candidato = MinHashLSH(
            num_hashes=100,
            bandas=20,
            semilla=args.semilla + repeticion,
        )

        # Mide memoria en una construcción; mide el tiempo en todas.
        if repeticion == 0:
            tracemalloc.start()

        inicio = time.perf_counter()
        candidato.ajustar(conjuntos)
        tiempos_construccion.append(time.perf_counter() - inicio)

        if repeticion == 0:
            memoria_pico_mb = tracemalloc.get_traced_memory()[1] / (1024**2)
            tracemalloc.stop()

        modelo = candidato

    rng = random.Random(args.semilla)
    cantidad_consultas = min(args.consultas, args.n)
    productos_consulta = rng.sample(list(conjuntos), cantidad_consultas)

    tiempos_lsh = []
    recalls = []

    for producto in productos_consulta:
        exacto = topk_exacto(conjuntos, producto, args.k)

        inicio = time.perf_counter()
        aproximado = modelo.similares(producto, args.k)
        tiempos_lsh.append(time.perf_counter() - inicio)

        recalls.append(recall_at_k(exacto, aproximado))

    resultado = {
        "n": args.n,
        "k": args.k,
        "consultas": cantidad_consultas,
        "repeticiones_construccion": args.repeticiones,
        "construccion_media_s": statistics.mean(tiempos_construccion),
        "construccion_desv_s": (
            statistics.stdev(tiempos_construccion)
            if len(tiempos_construccion) > 1 else 0.0
        ),
        "consulta_media_s": statistics.mean(tiempos_lsh),
        "consulta_desv_s": (
            statistics.stdev(tiempos_lsh) if len(tiempos_lsh) > 1 else 0.0
        ),
        "recall_at_k": statistics.mean(recalls),
        "memoria_pico_mb": memoria_pico_mb,
        "semilla": args.semilla,
    }

    ruta = Path(f"experimentos/resultados/minhash_{args.n}.csv")
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=resultado.keys())
        escritor.writeheader()
        escritor.writerow(resultado)

    print(resultado)
    print(f"Resultados guardados en {ruta}")


if __name__ == "__main__":
    main()