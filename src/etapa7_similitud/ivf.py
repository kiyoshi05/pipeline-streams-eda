import random
from math import sqrt


def _distancia2(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


class IVFFlat:
    """Índice aproximado IVF-Flat con agrupamiento k-means sencillo."""

    def __init__(
        self,
        puntos,
        n_clusters=16,
        nprobe=4,
        max_iter=20,
        semilla=42,
    ):
        self.ids = [id_ for id_, _ in puntos]
        self.vectores = [tuple(map(float, v)) for _, v in puntos]

        if not self.vectores:
            raise ValueError("Se necesita al menos un vector")

        dimensiones = {len(v) for v in self.vectores}
        if len(dimensiones) != 1:
            raise ValueError("Todos los vectores deben tener igual dimensión")

        self.n_clusters = min(n_clusters, len(self.vectores))
        if self.n_clusters < 1 or nprobe < 1:
            raise ValueError("n_clusters y nprobe deben ser mayores que cero")

        self.nprobe = min(nprobe, self.n_clusters)
        rng = random.Random(semilla)
        self.centroides = [
            self.vectores[i]
            for i in rng.sample(range(len(self.vectores)), self.n_clusters)
        ]

        for _ in range(max_iter):
            etiquetas = [
                min(
                    range(self.n_clusters),
                    key=lambda c: _distancia2(vector, self.centroides[c]),
                )
                for vector in self.vectores
            ]

            grupos = [[] for _ in range(self.n_clusters)]
            for vector, etiqueta in zip(self.vectores, etiquetas):
                grupos[etiqueta].append(vector)

            nuevos = []
            for grupo, centro_anterior in zip(grupos, self.centroides):
                if grupo:
                    nuevos.append(tuple(
                        sum(v[d] for v in grupo) / len(grupo)
                        for d in range(len(centro_anterior))
                    ))
                else:
                    nuevos.append(centro_anterior)

            if nuevos == self.centroides:
                break
            self.centroides = nuevos

        self.buckets = [[] for _ in range(self.n_clusters)]
        for i, vector in enumerate(self.vectores):
            cluster = min(
                range(self.n_clusters),
                key=lambda c: _distancia2(vector, self.centroides[c]),
            )
            self.buckets[cluster].append(i)

    def buscar(self, consulta, k=10, excluir_id=None):
        consulta = tuple(map(float, consulta))
        if len(consulta) != len(self.vectores[0]):
            raise ValueError("La consulta debe tener la misma dimensión")
        if k < 1:
            raise ValueError("k debe ser mayor que cero")

        clusters = sorted(
            range(self.n_clusters),
            key=lambda c: _distancia2(consulta, self.centroides[c]),
        )[:self.nprobe]

        candidatos = []
        for cluster in clusters:
            for i in self.buckets[cluster]:
                if self.ids[i] != excluir_id:
                    d2 = _distancia2(consulta, self.vectores[i])
                    candidatos.append((self.ids[i], d2, i))

        candidatos.sort(key=lambda x: (x[1], x[2]))
        return [
            (id_, sqrt(d2))
            for id_, d2, _ in candidatos[:k]
        ]