import unittest

from src.etapa7_similitud.minhash_lsh import (
    MinHashLSH,
    conjuntos_usuarios_por_producto,
)


class TestMinHashLSH(unittest.TestCase):
    def test_construye_conjuntos_solo_con_compras(self):
        eventos = [
            {"product_id": 1, "user_id": 10, "event_type": "purchase"},
            {"product_id": 1, "user_id": 11, "event_type": "purchase"},
            {"product_id": 1, "user_id": 12, "event_type": "view"},
        ]
        self.assertEqual({1: {10, 11}}, conjuntos_usuarios_por_producto(eventos))

    def test_productos_con_usuarios_iguales_son_similares(self):
        conjuntos = {
            1: {10, 11, 12},
            2: {10, 11, 12},
            3: {50, 51, 52},
        }
        modelo = MinHashLSH(num_hashes=100, bandas=20).ajustar(conjuntos)

        resultados = modelo.similares(1, k=2)
        self.assertEqual(2, resultados[0][0])
        self.assertAlmostEqual(1.0, resultados[0][1])


if __name__ == "__main__":
    unittest.main()