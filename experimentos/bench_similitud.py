import argparse
import random
import time
import tracemalloc

from src.etapa7_similitud.minhash_lsh import MinHashLSH


def topk_exacto(conjuntos, producto, k):
    objetivo = conjuntos[producto]
    resultados = []

    for otro, usuarios in conjuntos.items():
        if otro == producto or not usuarios:
            continue

        union = objetivo | usuarios
        jaccard = len(objetivo & usuarios) / len(union)
        resultados.append((otro, jaccard))

    return sorted(resultados, key=lambda x: (-x[1], str(x[0])))[:k]


def recall_at_k(exacto, aproximado, k):
    relevantes = {id_ for id_, _ in exacto[:k]}
    encontrados = {id_ for id_, _ in aproximado[:k]}

    if not relevantes:
        return 1.0

    return len(relevantes & encontrados) / len(relevantes)


def generar_conjuntos(n_productos, n_usuarios, semilla):
    rng = random.Random(semilla)
    return {
        producto: set(
            rng.sample(
                range(n_usuarios),
                k=min(rng.randint(5, 30), n_usuarios),
            )
        )
        for producto in range(n_productos)
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--productos", type=int, default=1000)
    parser.add_argument("--usuarios", type=int, default=5000)
    parser.add_argument("--consultas", type=int, default=25)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    conjuntos = generar_conjuntos(
        args.productos, args.usuarios, args.semilla
    )

    tracemalloc.start()
    inicio = time.perf_counter()
    modelo = MinHashLSH(num_hashes=100, bandas=20, semilla=args.semilla)
    modelo.ajustar(conjuntos)
    tiempo_construccion = time.perf_counter() - inicio
    memoria_pico_mb = tracemalloc.get_traced_memory()[1] / (1024**2)
    tracemalloc.stop()

    consultas = list(conjuntos)[:min(args.consultas, len(conjuntos))]
    tiempos_exactos = []
    tiempos_lsh = []
    recalls = []

    for producto in consultas:
        inicio = time.perf_counter()
        exacto = topk_exacto(conjuntos, producto, args.k)
        tiempos_exactos.append(time.perf_counter() - inicio)

        inicio = time.perf_counter()
        aproximado = modelo.similares(producto, args.k)
        tiempos_lsh.append(time.perf_counter() - inicio)

        recalls.append(recall_at_k(exacto, aproximado, args.k))

    print(f"Productos: {args.productos}")
    print(f"Consultas: {len(consultas)} | K: {args.k}")
    print(f"Construcción LSH: {tiempo_construccion:.4f} s")
    print(f"Consulta exacta promedio: {sum(tiempos_exactos) / len(consultas):.6f} s")
    print(f"Consulta LSH promedio: {sum(tiempos_lsh) / len(consultas):.6f} s")
    print(f"Recall@{args.k} promedio: {sum(recalls) / len(recalls):.3f}")
    print(f"Pico de memoria al construir LSH: {memoria_pico_mb:.2f} MB")


if __name__ == "__main__":
    main()