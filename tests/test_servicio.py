import unittest
from types import SimpleNamespace

from src.etapa2_prioridad.prioridad import Etapa2Prioridad
from src.etapa9_servicio.servicio import ServicioRecomendaciones


class TestServicioRecomendaciones(unittest.TestCase):
    def setUp(self):
        self.eventos = [
            {
                "product_id": 1,
                "user_id": 10,
                "price": 10,
                "brand": "Acme",
                "category_code": "ropa.camisas",
                "event_type": "view",
            },
            {
                "product_id": 2,
                "user_id": 11,
                "price": 12,
                "brand": "Acme",
                "category_code": "ropa.camisas",
                "event_type": "purchase",
            },
            {
                "product_id": 3,
                "user_id": 12,
                "price": 80,
                "brand": "Nova",
                "category_code": "electronica.telefonos",
                "event_type": "view",
            },
        ]
        self.servicio = ServicioRecomendaciones(
            self.eventos,
            n_clusters=3,
            nprobe=3,
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

    def test_similares_por_compra(self):
        eventos = [
            {
                "product_id": 1,
                "user_id": 10,
                "price": 20,
                "brand": "A",
                "category_code": "ropa",
                "event_type": "purchase",
            },
            {
                "product_id": 1,
                "user_id": 11,
                "price": 20,
                "brand": "A",
                "category_code": "ropa",
                "event_type": "purchase",
            },
            {
                "product_id": 2,
                "user_id": 10,
                "price": 22,
                "brand": "A",
                "category_code": "ropa",
                "event_type": "purchase",
            },
            {
                "product_id": 2,
                "user_id": 11,
                "price": 22,
                "brand": "A",
                "category_code": "ropa",
                "event_type": "purchase",
            },
            {
                "product_id": 3,
                "user_id": 30,
                "price": 90,
                "brand": "B",
                "category_code": "electronica",
                "event_type": "purchase",
            },
        ]

        servicio = ServicioRecomendaciones(eventos)
        resultado = servicio.similares_por_compra(1, k=2)

        self.assertEqual(2, resultado[0][0])
        self.assertAlmostEqual(1.0, resultado[0][1])

    def test_acepta_eventos_de_etapa2_con_prioridad(self):
        eventos = [
            SimpleNamespace(
                product_id=1,
                user_id=10,
                price=20,
                brand="Acme",
                category_code="ropa",
                event_type="purchase",
                event_time=2,
            ),
            SimpleNamespace(
                product_id=1,
                user_id=11,
                price=20,
                brand="Acme",
                category_code="ropa",
                event_type="purchase",
                event_time=1,
            ),
            SimpleNamespace(
                product_id=2,
                user_id=10,
                price=22,
                brand="Acme",
                category_code="ropa",
                event_type="purchase",
                event_time=3,
            ),
            SimpleNamespace(
                product_id=2,
                user_id=11,
                price=22,
                brand="Acme",
                category_code="ropa",
                event_type="purchase",
                event_time=4,
            ),
        ]

        cola = Etapa2Prioridad()
        cola.recibir(eventos)
        eventos_etapa2 = cola.extraer()

        self.assertTrue(
            all(hasattr(evento, "prioridad") for evento in eventos_etapa2)
        )

        servicio = ServicioRecomendaciones(
            eventos_etapa2,
            n_clusters=2,
            nprobe=2,
        )

        self.assertEqual(2, servicio.metricas()["productos"])
        similares = servicio.similares_por_compra(1, k=1)
        self.assertEqual(2, similares[0][0])
        self.assertEqual(["Acme"], servicio.autocompletar("ac"))


if __name__ == "__main__":
    unittest.main()