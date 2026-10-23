from collections import Counter

from src.etapa5_multidimensional.features import construir_vectores_productos
from src.etapa7_similitud.ivf import IVFFlat
from src.etapa9_servicio.topk import top_k
from src.etapa9_servicio.trie import Trie


class ServicioRecomendaciones:
    def __init__(self, eventos, n_clusters=16, nprobe=4):
        self.eventos = list(eventos)
        self.vectores, _ = construir_vectores_productos(self.eventos)
        self.vector_por_id = dict(self.vectores)

        self.indice = None
        if self.vectores:
            self.indice = IVFFlat(
                self.vectores,
                n_clusters=n_clusters,
                nprobe=nprobe,
            )

        self.trie = Trie()
        for evento in self.eventos:
            for campo in ("brand", "category_code"):
                valor = evento.get(campo)
                if valor:
                    self.trie.insertar(str(valor))

    def recomendar(self, product_id, k=5):
        if product_id not in self.vector_por_id:
            raise KeyError(f"No se encontró el producto {product_id}")
        if self.indice is None:
            return []

        similares = self.indice.buscar(
            self.vector_por_id[product_id],
            k=k,
            excluir_id=product_id,
        )

        # Convierte distancia (menor es mejor) en puntuación (mayor es mejor).
        puntuaciones = [
            (id_, 1 / (1 + distancia))
            for id_, distancia in similares
        ]
        return top_k(puntuaciones, k)

    def autocompletar(self, prefijo, k=10):
        return self.trie.autocompletar(prefijo, k)

    def metricas(self):
        productos = {
            e.get("product_id")
            for e in self.eventos
            if e.get("product_id") is not None
        }
        usuarios = {
            e.get("user_id")
            for e in self.eventos
            if e.get("user_id") is not None
        }

        return {
            "total_eventos": len(self.eventos),
            "productos": len(productos),
            "usuarios": len(usuarios),
            "tipos_evento": dict(Counter(
                str(e.get("event_type", "desconocido")).lower()
                for e in self.eventos
            )),
        }