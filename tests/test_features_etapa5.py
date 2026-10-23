import unittest

from src.etapa5_multidimensional.indice_productos import IndiceProductos


class TestIndiceProductos(unittest.TestCase):
    def test_kd_tree_y_busqueda_exacta_coinciden(self):
        eventos = [
            {"product_id": 1, "price": 10, "category_code": "ropa.camisas", "event_type": "view"},
            {"product_id": 1, "price": 10, "category_code": "ropa.camisas", "event_type": "purchase"},
            {"product_id": 2, "price": 12, "category_code": "ropa.camisas", "event_type": "cart"},
            {"product_id": 3, "price": 80, "category_code": "electronica.telefonos", "event_type": "view"},
            {"product_id": 4, "price": 75, "category_code": "electronica.telefonos", "event_type": "purchase"},
        ]
        indice = IndiceProductos(eventos)

        exactos = indice.buscar_similares(1, k=2, metodo="exacto")
        kd_tree = indice.buscar_similares(1, k=2, metodo="kd_tree")

        self.assertEqual(
            [id_ for id_, _ in exactos],
            [id_ for id_, _ in kd_tree],
        )
        self.assertNotIn(1, [id_ for id_, _ in kd_tree])

    def test_producto_inexistente(self):
        indice = IndiceProductos([
            {"product_id": 1, "price": 10, "category_code": "ropa.camisas", "event_type": "view"},
        ])
        with self.assertRaises(KeyError):
            indice.buscar_similares(999)


if __name__ == "__main__":
    unittest.main()