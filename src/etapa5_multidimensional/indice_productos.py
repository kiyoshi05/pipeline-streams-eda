from src.etapa5_multidimensional.features import construir_vectores_productos
from src.etapa5_multidimensional.kd_tree import KDTree
from src.etapa5_multidimensional.knn import knn_exacto


class IndiceProductos:
    def __init__(self, eventos):
        self.vectores, self.categorias = construir_vectores_productos(eventos)
        self.vector_por_id = dict(self.vectores)
        self.kd_tree = KDTree(self.vectores)

    def buscar_similares(self, product_id, k=10, metodo="kd_tree"):
        if product_id not in self.vector_por_id:
            raise KeyError(f"No se encontró el producto {product_id}")

        consulta = self.vector_por_id[product_id]

        if metodo == "kd_tree":
            return self.kd_tree.buscar(consulta, k, excluir_id=product_id)

        if metodo == "exacto":
            return knn_exacto(self.vectores, consulta, k, excluir_id=product_id)

        raise ValueError("metodo debe ser 'kd_tree' o 'exacto'")