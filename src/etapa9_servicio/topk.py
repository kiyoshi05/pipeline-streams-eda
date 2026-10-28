from src.etapa2_prioridad.heap import MinHeap


def top_k(elementos, k):
    """Recibe pares (id, puntuación) y devuelve los k de mayor puntuación."""
    if k < 1:
        raise ValueError("k debe ser mayor que cero")

    heap = MinHeap()

    for orden, (identificador, puntuacion) in enumerate(elementos):
        entrada = (float(puntuacion), -orden, identificador)

        if len(heap) < k:
            heap.push(entrada)
        elif entrada[:2] > heap.peek()[:2]:
            heap.pop()
            heap.push(entrada)

    mejores = []
    while heap:
        mejores.append(heap.pop())

    mejores.sort(key=lambda elemento: (-elemento[0], -elemento[1]))
    return [
        (identificador, puntuacion)
        for puntuacion, _, identificador in mejores
    ]