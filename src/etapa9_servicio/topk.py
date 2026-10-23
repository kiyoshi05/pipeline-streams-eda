from heapq import heappush, heapreplace


def top_k(elementos, k):
    """Recibe pares (id, puntuación) y devuelve los k de mayor puntuación."""
    if k < 1:
        raise ValueError("k debe ser mayor que cero")

    heap = []

    for orden, (identificador, puntuacion) in enumerate(elementos):
        entrada = (float(puntuacion), -orden, identificador)

        if len(heap) < k:
            heappush(heap, entrada)
        elif entrada[:2] > heap[0][:2]:
            heapreplace(heap, entrada)

    mejores = sorted(heap, key=lambda x: (-x[0], -x[1]))
    return [(identificador, puntuacion) for puntuacion, _, identificador in mejores]