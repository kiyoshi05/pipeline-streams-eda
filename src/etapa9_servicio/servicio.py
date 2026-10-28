from collections import Counter

from src.etapa1_preprocesamiento.preprocesamiento import campo
from src.etapa5_multidimensional.features import construir_vectores_productos
from src.etapa7_similitud.ivf import IVFFlat
from src.etapa7_similitud.minhash_lsh import (
    MinHashLSH,
    conjuntos_usuarios_por_producto,
)
from src.etapa8_grafo.grafo_dominio import Etapa8Grafo
from src.etapa8_grafo.ranking import mayores_k
from src.etapa9_servicio.topk import top_k
from src.etapa9_servicio.trie import Trie


class ServicioRecomendaciones:
    """Integra recomendaciones, similitud por compras y resultados de etapa 8."""

    def __init__(
        self,
        eventos,
        n_clusters=16,
        nprobe=4,
        pagerank=None,
        comunidades=None,
        alertas=None,
    ):
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

        self.conjuntos_compra = conjuntos_usuarios_por_producto(self.eventos)
        self.indice_lsh = MinHashLSH(
            num_hashes=100,
            bandas=20,
        ).ajustar(self.conjuntos_compra)

        self.trie = Trie()
        for evento in self.eventos:
            for nombre_campo in ("brand", "category_code"):
                valor = campo(evento, nombre_campo)
                if valor:
                    self.trie.insertar(str(valor))

        # Si no llegan resultados de la etapa 8, los calculamos desde los eventos.
        self.etapa8 = None
        if pagerank is None or comunidades is None:
            self.etapa8 = Etapa8Grafo()
            self.etapa8.procesar(self.eventos)

        self.pagerank = (
            dict(pagerank)
            if pagerank is not None
            else self.etapa8.puntajes(metodo="pagerank")
        )
        self.comunidades = (
            dict(comunidades)
            if comunidades is not None
            else self.etapa8.comunidades(metodo="louvain")
        )

        # La etapa 6 aún no está integrada en main. Este argumento permite
        # recibir sus alertas cuando estén disponibles.
        self.alertas = list(alertas) if alertas is not None else []

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

        puntuaciones = [
            (id_, 1.0 / (1.0 + distancia))
            for id_, distancia in similares
        ]
        return top_k(puntuaciones, k)

    def similares_por_compra(self, product_id, k=5):
        """Busca productos cuyos compradores también compraron este producto."""
        if product_id not in self.conjuntos_compra:
            return []

        return self.indice_lsh.similares(product_id, k)

    def productos_influyentes(self, k=10):
        """Devuelve los productos con mayor PageRank."""
        return mayores_k(self.pagerank, k)

    def comunidad_de(self, product_id):
        """Devuelve el identificador de comunidad del producto, si existe."""
        return self.comunidades.get(product_id)

    def autocompletar(self, prefijo, k=10):
        """Sugiere marcas o categorías que empiezan con el prefijo."""
        return self.trie.autocompletar(prefijo, k)

    def metricas(self):
        """Resume los eventos recibidos por el servicio."""
        productos = {
            campo(evento, "product_id")
            for evento in self.eventos
            if campo(evento, "product_id") is not None
        }
        usuarios = {
            campo(evento, "user_id")
            for evento in self.eventos
            if campo(evento, "user_id") is not None
        }
        tipos_evento = Counter(
            str(campo(evento, "event_type") or "desconocido").lower()
            for evento in self.eventos
        )

        return {
            "total_eventos": len(self.eventos),
            "productos": len(productos),
            "usuarios": len(usuarios),
            "tipos_evento": dict(tipos_evento),
        }