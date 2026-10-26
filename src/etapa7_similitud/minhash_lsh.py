from collections import defaultdict
from functools import lru_cache
from hashlib import blake2b
import random

from src.etapa1_preprocesamiento.preprocesamiento import campo


_PRIMO = 2**61 - 1


def conjuntos_usuarios_por_producto(eventos):
    """Devuelve {product_id: conjunto de user_id} para compras."""
    conjuntos = defaultdict(set)

    for evento in eventos:
        tipo = str(campo(evento, "event_type", "")).lower()
        if tipo != "purchase":
            continue

        product_id = campo(evento, "product_id")
        user_id = campo(evento, "user_id")

        if product_id is not None and user_id is not None:
            conjuntos[product_id].add(user_id)

    return dict(conjuntos)


@lru_cache(maxsize=None)
def _token_a_entero(token):
    texto = str(token).encode("utf-8")
    return int.from_bytes(
        blake2b(texto, digest_size=8).digest(),
        "big",
    )


class MinHashLSH:
    def __init__(self, num_hashes=100, bandas=20, semilla=42):
        if num_hashes < 1 or bandas < 1 or num_hashes % bandas != 0:
            raise ValueError("num_hashes debe ser divisible entre bandas")

        self.num_hashes = num_hashes
        self.bandas = bandas
        self.filas_por_banda = num_hashes // bandas
        self._rng = random.Random(semilla)
        self._coeficientes = [
            (self._rng.randrange(1, _PRIMO), self._rng.randrange(_PRIMO))
            for _ in range(num_hashes)
        ]
        self.conjuntos = {}
        self.firmas = {}
        self._buckets = defaultdict(set)

    def _firma(self, elementos):
        tokens = [_token_a_entero(x) % _PRIMO for x in elementos]

        return tuple(
            min((a * token + b) % _PRIMO for token in tokens)
            for a, b in self._coeficientes
        )

    def ajustar(self, conjuntos):
        """Construye firmas MinHash y buckets LSH."""
        self.conjuntos = {
            producto: set(usuarios)
            for producto, usuarios in conjuntos.items()
            if usuarios
        }
        self.firmas.clear()
        self._buckets.clear()

        for producto, usuarios in self.conjuntos.items():
            firma = self._firma(usuarios)
            self.firmas[producto] = firma

            for banda in range(self.bandas):
                inicio = banda * self.filas_por_banda
                fin = inicio + self.filas_por_banda
                clave = (banda, firma[inicio:fin])
                self._buckets[clave].add(producto)

        return self

    def similares(self, producto, k=10):
        """Devuelve candidatos LSH ordenados por Jaccard exacto."""
        if producto not in self.conjuntos:
            raise KeyError(f"No se encontró el producto {producto}")

        candidatos = set()
        firma = self.firmas[producto]

        for banda in range(self.bandas):
            inicio = banda * self.filas_por_banda
            fin = inicio + self.filas_por_banda
            clave = (banda, firma[inicio:fin])
            candidatos.update(self._buckets[clave])

        candidatos.discard(producto)
        usuarios_objetivo = self.conjuntos[producto]

        resultados = []
        for otro in candidatos:
            usuarios_otro = self.conjuntos[otro]
            union = usuarios_objetivo | usuarios_otro
            jaccard = len(usuarios_objetivo & usuarios_otro) / len(union)
            resultados.append((otro, jaccard))

        return sorted(
            resultados,
            key=lambda x: (-x[1], str(x[0])),
        )[:k]