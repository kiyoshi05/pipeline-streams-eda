from collections import Counter

from src.etapa5_multidimensional.features import construir_vectores_productos
from src.etapa7_similitud.ivf import IVFFlat
from src.etapa7_similitud.minhash_lsh import (
    MinHashLSH,
    conjuntos_usuarios_por_producto,
)
from src.etapa9_servicio.topk import top_k
from src.etapa9_servicio.trie import Trie


class ServicioRecomendaciones:
    """Integra recomendaciones, similitud por compras, autocompletado y métricas."""

    def __init__(self, eventos, n_clusters=16, nprobe=4):
        self.eventos = list(eventos)

        # Prepara los vectores de atributos y el índice IVF.
        self.vectores, _ = construir_vectores_productos(self.eventos)
        self.vector_por_id = dict(self.vectores)

        self.indice = None
        if self.vectores:
            self.indice = IVFFlat(
                self.vectores,
                n_clusters=n_clusters,
                nprobe=nprobe,
            )

        # Prepara los conjuntos de compradores y el índice MinHash-LSH.
        self.conjuntos_compra = conjuntos_usuarios_por_producto(self.eventos)
        self.indice_lsh = MinHashLSH(
            num_hashes=100,
            bandas=20,
        ).ajustar(self.conjuntos_compra)

        # Carga marcas y categorías para autocompletar.
        self.trie = Trie()
        for evento in self.eventos:
            for campo in ("brand", "category_code"):
                valor = evento.get(campo)
                if valor:
                    self.trie.insertar(str(valor))

    def recomendar(self, product_id, k=5):
        """Recomienda productos por similitud de atributos usando IVF."""
        if product_id not in self.vector_por_id:
            raise KeyError(f"No se encontró el producto {product_id}")

        if self.indice is None:
            return []

        similares = self.indice.buscar(
            self.vector_por_id[product_id],
            k=k,
            excluir_id=product_id,
        )

        # Una distancia menor equivale a una puntuación de similitud mayor.
        puntuaciones = [
            (id_, 1.0 / (1.0 + distancia))
            for id_, distancia in similares
        ]
        return top_k(puntuaciones, k)

    def similares_por_compra(self, product_id, k=5):
        """Busca productos comprados por conjuntos de usuarios similares."""
        if product_id not in self.conjuntos_compra:
            return []

        return self.indice_lsh.similares(product_id, k)

    def autocompletar(self, prefijo, k=10):
        """Sugiere marcas o categorías que empiezan con el prefijo."""
        return self.trie.autocompletar(prefijo, k)

    def metricas(self):
        """Resume los eventos recibidos por el servicio."""
        productos = {
            evento.get("product_id")
            for evento in self.eventos
            if evento.get("product_id") is not None
        }
        usuarios = {
            evento.get("user_id")
            for evento in self.eventos
            if evento.get("user_id") is not None
        }
        tipos_evento = Counter(
            str(evento.get("event_type") or "desconocido").lower()
            for evento in self.eventos
        )

        return {
            "total_eventos": len(self.eventos),
            "productos": len(productos),
            "usuarios": len(usuarios),
            "tipos_evento": dict(tipos_evento),
        }