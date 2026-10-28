"""Pipeline de las 10 etapas de punta a punta (src/pipeline.py).

Un stream sintético con fraude atraviesa las 10 etapas y termina en salidas
observables: alertas, ranking de influencia, recomendaciones y autocompletado.
"""

import io
import unittest
from contextlib import redirect_stdout

from experimentos.datos_sinteticos import generar_eventos_fraude, iterar_eventos
from src.pipeline import ETAPAS, ORDEN_CIERRE, ORDEN_FLUJO, Pipeline


class PruebasPipelineCompleto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.stream, cls.lista_negra = generar_eventos_fraude(10_000, semilla=42)
        cls.fraude_real = sum(e["es_fraude"] for e in cls.stream)
        cls.p = Pipeline(lista_negra=cls.lista_negra, tam_lote=1_000).procesar(cls.stream).cerrar()

    def test_recorre_las_10_etapas_en_orden(self):
        self.assertEqual(ORDEN_FLUJO, (0, 1, 6, 2, 3, 4, 8))
        self.assertEqual(sorted(ORDEN_FLUJO + ORDEN_CIERRE), list(range(10)))
        # Cada etapa trabajó y midió su tiempo; la 7 la construye el servicio de la 9
        self.assertEqual(set(self.p.tiempos), set(ETAPAS) - {7})
        self.assertEqual(set(self.p.resumen()), set(ETAPAS))

    def test_ningun_evento_valido_se_pierde(self):
        m1 = self.p.e1.metricas()
        self.assertEqual(m1["recibidos"], len(self.stream))
        self.assertEqual(len(self.p.eventos), m1["entregados"])
        for etapa in (self.p.e3, self.p.e4, self.p.e8):
            self.assertEqual(etapa.metricas()["recibidos"], len(self.p.eventos))
        self.assertEqual(self.p.e6.metricas()["recibidos"], len(self.p.eventos))
        self.assertEqual(self.p.servicio.metricas()["total_eventos"], len(self.p.eventos))

    def test_fraude_detectado_y_priorizado(self):
        m6 = self.p.e6.metricas()
        self.assertGreater(m6["marcados"], 0)
        self.assertEqual(m6["precision"], 1.0)
        self.assertGreater(m6["recall"], 0.8)
        # Todo evento marcado sale con prioridad 0 y llega como alerta al servicio
        self.assertTrue(all(e["prioridad"] == 0 for e in self.p.alertas))
        self.assertTrue(all(e["prioridad"] != 0 for e in self.p.eventos if not e["fraude_predicho"]))
        self.assertEqual(len(self.p.servicio.alertas), m6["marcados"])

    def test_la_prioridad_no_usa_la_etiqueta(self):
        # Un fraude real que la etapa 6 no detectó no recibe prioridad 0
        no_detectados = [e for e in self.p.eventos if e["es_fraude"] and not e["fraude_predicho"]]
        self.assertTrue(all(e["prioridad"] != 0 for e in no_detectados))

    def test_salidas_del_servicio(self):
        s = self.p.servicio
        top = self.p.influyentes(5)
        self.assertEqual(len(top), 5)
        self.assertEqual([v for _, v in top], sorted((v for _, v in top), reverse=True))
        producto = top[0][0]
        self.assertTrue(s.recomendar(producto, 3))              # etapas 5 y 7: vectores + IVF
        self.assertIsNotNone(s.comunidad_de(producto))          # etapa 8: comunidades
        marca = self.p.e3.consultar(producto)["brand"]
        self.assertIn(marca, s.autocompletar(marca[:2], 50))      # etapa 9: Trie
        self.assertTrue(self.p.indice_productos.buscar_similares(producto, 3))  # etapa 5: KD-Tree

    def test_recorrido_de_un_evento(self):
        evento = self.p.evento_para_demo()
        self.assertTrue(evento["fraude_predicho"])               # hay fraude: muestra una alerta
        pasos = self.p.recorrido(evento)
        self.assertEqual([e for e, _, _ in pasos], list(ORDEN_FLUJO + ORDEN_CIERRE))
        self.assertTrue(all(texto for _, _, texto in pasos))
        textos = dict((e, t) for e, _, t in pasos)
        self.assertIn("marcado como fraude", textos[6])
        self.assertIn("prioridad 0", textos[2])

    def test_el_servicio_se_rearma_con_mas_lotes(self):
        p = Pipeline(lista_negra=self.lista_negra, tam_lote=500)
        p.procesar(self.stream[:2_000])
        primero = p.servicio
        p.procesar(self.stream[2_000:4_000])
        self.assertIsNot(p.servicio, primero)
        self.assertEqual(p.servicio.metricas()["total_eventos"], len(p.eventos))


class PruebasPipelineSinFraude(unittest.TestCase):
    """Un stream sin campos de fraude (como un CSV de REES46) también atraviesa todo."""

    def test_stream_sin_campos_de_fraude(self):
        p = Pipeline().procesar(iterar_eventos(3_000, semilla=7))
        self.assertEqual(p.e6.metricas()["marcados"], 0)
        self.assertEqual(p.alertas, [])
        self.assertGreater(len(p.eventos), 2_500)
        evento = p.evento_para_demo()
        self.assertEqual(len(p.recorrido(evento)), 10)

    def test_sin_eventos_no_cierra(self):
        with self.assertRaises(ValueError):
            Pipeline().cerrar()


class PruebasRunPipeline(unittest.TestCase):

    def test_script_de_punta_a_punta(self):
        import run_pipeline
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(run_pipeline.main(["--n", "3000"]), 0)
        texto = salida.getvalue()
        for parte in ("1. Etapas", "2. Alertas de fraude", "3. Productos más influyentes", "4. Recorrido"):
            self.assertIn(parte, texto)
        for nombre in ETAPAS.values():
            self.assertIn(nombre, texto)


if __name__ == "__main__":
    unittest.main()
