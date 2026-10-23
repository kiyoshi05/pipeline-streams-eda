import unittest

from src.etapa9_servicio.servicio import ServicioRecomendaciones


class TestServicioRecomendaciones(unittest.TestCase):
    def setUp(self):
        self.eventos = [
            {"product_id": 1, "user_id": 10, "price": 10, "brand": "Acme",
             "category_code": "ropa.camisas", "event_type": "view"},
            {"product_id": 2, "user_id": 11, "price": 12, "brand": "Acme",
             "category_code": "ropa.camisas", "event_type": "purchase"},
            {"product_id": 3, "user_id": 12, "price": 80, "brand": "Nova",
             "category_code": "electronica.telefonos", "event_type": "view"},
        ]
        self.servicio = ServicioRecomendaciones(
            self.eventos, n_clusters=3, nprobe=3
        )

    def test_recomienda_sin_incluir_el_producto_consultado(self):
        recomendaciones = self.servicio.recomendar(1, k=2)
        self.assertLessEqual(len(recomendaciones), 2)
        self.assertNotIn(1, [id_ for id_, _ in recomendaciones])

    def test_autocompleta_marca_y_categoria(self):
        self.assertEqual(["Acme"], self.servicio.autocompletar("ac"))

    def test_metricas(self):
        metricas = self.servicio.metricas()
        self.assertEqual(3, metricas["total_eventos"])
        self.assertEqual(3, metricas["productos"])


if __name__ == "__main__":
    unittest.main()