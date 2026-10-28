from math import dist
from typing import Hashable, Iterable, Sequence


def knn_exacto(
    puntos: Iterable[tuple[Hashable, Sequence[float]]],
    consulta: Sequence[float],
    k: int,
    excluir_id: Hashable | None = None,
) -> list[tuple[Hashable, float]]:
    """Devuelve los k puntos más cercanos usando distancia euclidiana.

    Cada punto tiene el formato (identificador, vector).
    El resultado contiene pares (identificador, distancia), ordenados
    desde el más cercano.
    """
    if k < 1:
        raise ValueError("k debe ser mayor que cero")

    consulta = tuple(float(x) for x in consulta)
    candidatos = []

    for identificador, vector in puntos:
        vector = tuple(float(x) for x in vector)

        if len(vector) != len(consulta):
            raise ValueError("Todos los vectores deben tener igual dimensión")

        if identificador == excluir_id:
            continue

        candidatos.append((identificador, dist(consulta, vector)))

    candidatos.sort(key=lambda elemento: elemento[1])
    return candidatos[:k]