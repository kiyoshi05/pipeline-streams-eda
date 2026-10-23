import unittest

from src.etapa9_servicio.topk import top_k
from src.etapa9_servicio.trie import Trie


class TestEtapa9(unittest.TestCase):
    def test_top_k_ordena_por_puntuacion(self):
        elementos = [("A", 2), ("B", 9), ("C", 5)]
        self.assertEqual([("B", 9.0), ("C", 5.0)], top_k(elementos, 2))

    def test_trie_autocompleta_sin_distinguir_mayusculas(self):
        trie = Trie()
        for palabra in ["Samsung", "Samsonite", "Apple", "Sandalias"]:
            trie.insertar(palabra)

        self.assertEqual(
            ["Samsonite", "Samsung"],
            trie.autocompletar("sam"),
        )


if __name__ == "__main__":
    unittest.main()