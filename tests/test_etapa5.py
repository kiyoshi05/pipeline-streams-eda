import random
import unittest

from src.etapa5_multidimensional.knn import knn_exacto
from src.etapa5_multidimensional.kd_tree import KDTree


class TestEtapa5(unittest.TestCase):
    def test_kd_tree_coincide_con_knn_exacto(self):
        generador = random.Random(42)
        puntos = [
            (i, tuple(generador.uniform(-10, 10) for _ in range(3)))
            for i in range(200)
        ]
        consulta = (1.5, -2.0, 4.0)

        esperado = knn_exacto(puntos, consulta, k=7, excluir_id=50)
        obtenido = KDTree(puntos).buscar(
            consulta, k=7, excluir_id=50
        )

        self.assertEqual(
            [id_ for id_, _ in esperado],
            [id_ for id_, _ in obtenido],
        )
        for (_, distancia_esperada), (_, distancia_obtenida) in zip(
            esperado, obtenido
        ):
            self.assertAlmostEqual(distancia_esperada, distancia_obtenida)

    def test_k_mayor_que_puntos_disponibles(self):
        puntos = [("A", (0, 0)), ("B", (2, 0))]
        obtenido = KDTree(puntos).buscar(
            consulta=(0, 0), k=5, excluir_id="A"
        )
        self.assertEqual(["B"], [id_ for id_, _ in obtenido])

    def test_dimensiones_inconsistentes(self):
        puntos = [("A", (0, 0)), ("B", (1, 2, 3))]
        with self.assertRaises(ValueError):
            KDTree(puntos)


if __name__ == "__main__":
    unittest.main()