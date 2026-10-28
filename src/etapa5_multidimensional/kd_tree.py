from dataclasses import dataclass
from heapq import heappush, heapreplace
from math import sqrt
from typing import Hashable, Sequence


@dataclass
class _Nodo:
    identificador: Hashable
    vector: tuple[float, ...]
    indice: int
    eje: int
    izquierda: "_Nodo | None" = None
    derecha: "_Nodo | None" = None


class KDTree:
    """KD-Tree para búsqueda de vecinos con distancia euclidiana."""

    def __init__(
        self,
        puntos: Sequence[tuple[Hashable, Sequence[float]]],
    ) -> None:
        self._puntos = [
            (identificador, tuple(float(x) for x in vector), i)
            for i, (identificador, vector) in enumerate(puntos)
        ]

        dimensiones = {len(vector) for _, vector, _ in self._puntos}
        if len(dimensiones) > 1:
            raise ValueError("Todos los vectores deben tener igual dimensión")

        self.dimension = next(iter(dimensiones), 0)
        self.raiz = self._construir(self._puntos, profundidad=0)

    def _construir(self, puntos, profundidad: int) -> _Nodo | None:
        if not puntos:
            return None

        eje = profundidad % self.dimension
        puntos = sorted(puntos, key=lambda punto: punto[1][eje])
        medio = len(puntos) // 2

        identificador, vector, indice = puntos[medio]
        nodo = _Nodo(identificador, vector, indice, eje)
        nodo.izquierda = self._construir(puntos[:medio], profundidad + 1)
        nodo.derecha = self._construir(puntos[medio + 1 :], profundidad + 1)
        return nodo

    def buscar(
        self,
        consulta: Sequence[float],
        k: int,
        excluir_id: Hashable | None = None,
    ) -> list[tuple[Hashable, float]]:
        """Devuelve hasta k vecinos como pares (id, distancia)."""
        if k < 1:
            raise ValueError("k debe ser mayor que cero")

        consulta = tuple(float(x) for x in consulta)
        if self.dimension and len(consulta) != self.dimension:
            raise ValueError("La consulta debe tener la misma dimensión")

        # El heap conserva los k mejores candidatos; arriba queda el más lejano.
        heap = []

        def distancia_cuadrada(vector):
            return sum((a - b) ** 2 for a, b in zip(consulta, vector))

        def visitar(nodo: _Nodo | None) -> None:
            if nodo is None:
                return

            if nodo.identificador != excluir_id:
                d2 = distancia_cuadrada(nodo.vector)
                candidato = (-d2, -nodo.indice, nodo)

                if len(heap) < k:
                    heappush(heap, candidato)
                elif candidato[:2] > heap[0][:2]:
                    heapreplace(heap, candidato)

            diferencia = consulta[nodo.eje] - nodo.vector[nodo.eje]
            primero = nodo.izquierda if diferencia < 0 else nodo.derecha
            segundo = nodo.derecha if diferencia < 0 else nodo.izquierda

            visitar(primero)

            # Explora el otro lado si puede contener un vecino más cercano.
            if len(heap) < k or diferencia**2 <= -heap[0][0]:
                visitar(segundo)

        if self.raiz is not None:
            visitar(self.raiz)

        resultados = [
            (nodo.identificador, sqrt(-distancia_negativa))
            for distancia_negativa, _, nodo in heap
        ]
        return sorted(resultados, key=lambda resultado: resultado[1])