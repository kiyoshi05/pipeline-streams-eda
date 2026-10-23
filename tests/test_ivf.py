import random
import unittest

from src.etapa7_similitud.ivf import IVFFlat
from src.etapa5_multidimensional.knn import knn_exacto


class TestIVF(unittest.TestCase):
    def test_consultar_todos_los_clusters_coincide_con_knn_exacto(self):
        rng = random.Random(42)
        puntos = [
            (i, (rng.random(), rng.random(), rng.random()))
            for i in range(100)
        ]
        consulta = (0.4, 0.5, 0.6)

        exacto = knn_exacto(puntos, consulta, k=5, excluir_id=10)
        indice = IVFFlat(
            puntos, n_clusters=10, nprobe=10, semilla=42
        )
        obtenido = indice.buscar(consulta, k=5, excluir_id=10)

        self.assertEqual(
            [id_ for id_, _ in exacto],
            [id_ for id_, _ in obtenido],
        )


if __name__ == "__main__":
    unittest.main()