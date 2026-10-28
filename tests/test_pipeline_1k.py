"""Prueba de punta a punta con 1.000 eventos del stream sintético completo.

A diferencia de test_pipeline.py, aquí se exige que CADA etapa produzca una
salida no vacía: el stream completo trae duplicados, inválidos, compras
express y programadas, paquetes de compras conjuntas y fraude, así ninguna
etapa queda sin trabajo.
"""

import unittest
from collections import Counter

from experimentos.stream_completo import aumentar_filas, generar_stream
from src.etapa0_ingesta import leer_csv
from src.etapa2_prioridad.prioridad import NOMBRES
from src.pipeline import Pipeline


class PruebasStreamCompleto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.eventos, cls.lista_negra = generar_stream(1_000, semilla=42)

    def test_tamano_y_reproducible(self):
        self.assertEqual(len(self.eventos), 1_000)
        self.assertEqual(generar_stream(1_000, semilla=42)[0], self.eventos)
        self.assertNotEqual(generar_stream(1_000, semilla=7)[0], self.eventos)

    def test_trae_todo_lo_que_necesitan_las_etapas(self):
        tipos = Counter(e["event_type"] for e in self.eventos)
        self.assertGreater(tipos["purchase"], 0)
        self.assertGreater(sum(e["es_duplicado"] for e in self.eventos), 0)
        self.assertGreater(sum(e["es_fraude"] for e in self.eventos), 0)
        prioridades = Counter(e.get("prioridad") for e in self.eventos if e["event_type"] == "purchase")
        self.assertGreater(prioridades[1], 0)     # express
        self.assertGreater(prioridades[3], 0)     # programada
        self.assertTrue(self.lista_negra)
        self.assertTrue(all("ip" in e and "dispositivo_id" in e and "medio_pago" in e for e in self.eventos))

    def test_hay_paquetes_de_compras_conjuntas(self):
        por_sesion = {}
        for e in self.eventos:
            if e["event_type"] == "purchase" and not e["es_fraude"]:
                por_sesion.setdefault(e["user_session"], set()).add(e["product_id"])
        self.assertGreater(sum(1 for s in por_sesion.values() if len(s) >= 2), 10)

    def test_catalogo_estable(self):
        # Un producto mantiene su categoría y marca; el precio cambia poco y rara vez
        atributos = {}
        for e in self.eventos:
            if isinstance(e["product_id"], int):
                atributos.setdefault(e["product_id"], set()).add((e["category_code"], e["brand"]))
        self.assertTrue(all(len(a) == 1 for a in atributos.values()))

    def test_aumentar_filas_reales(self):
        filas, lista_negra = aumentar_filas(leer_csv("data/sample/eventos.csv"), semilla=42)
        filas = list(filas)
        self.assertGreater(len(filas), 1_000)                     # las ráfagas de fraude agregan filas
        self.assertTrue(all("ip" in f and "dispositivo_id" in f for f in filas))
        self.assertGreater(sum(f["es_fraude"] for f in filas), 0)
        self.assertTrue(lista_negra)
        # una misma sesión normal conserva su ip
        ips = {}
        for f in filas:
            if not f["es_fraude"]:
                ips.setdefault(f["user_session"], set()).add(f["ip"])
        self.assertTrue(all(len(v) == 1 for v in ips.values()))


class PruebasPipeline1K(unittest.TestCase):
    """Cada una de las 10 etapas produce salida con 1.000 eventos."""

    @classmethod
    def setUpClass(cls):
        eventos, lista_negra = generar_stream(1_000, semilla=42)
        cls.p = Pipeline(lista_negra=lista_negra, capacidad_cache=10).procesar(eventos).cerrar()
        cls.resumen = cls.p.resumen()

    def test_etapa1_descarta_y_deduplica(self):
        self.assertGreater(self.resumen[1]["descartados"], 0)
        self.assertGreater(self.resumen[1]["duplicados"], 0)
        m = self.p.e1.metricas()
        self.assertEqual(m["precision_dedup"], 1.0)

    def test_etapa6_detecta_fraude(self):
        self.assertGreater(self.resumen[6]["marcados"], 0)
        self.assertEqual(self.resumen[6]["precision"], 1.0)
        self.assertGreater(self.resumen[6]["recall"], 0.6)

    def test_etapa2_usa_los_cinco_niveles(self):
        self.assertEqual(set(self.resumen[2]), set(NOMBRES.values()))
        self.assertTrue(all(cantidad > 0 for cantidad in self.resumen[2].values()))

    def test_etapa3_catalogo_cache_y_matrices(self):
        self.assertGreater(self.resumen[3]["productos"], 0)
        self.assertGreater(self.resumen[3]["compras_celdas"], 0)
        tasa = self.p.simular_consultas(n=500)
        self.assertGreater(tasa, 0.2)          # la caché del ~15 % del catálogo acierta en los populares
        self.assertLess(tasa, 1.0)             # pero no le cabe todo
        ficha = self.p.consultar_producto(self.p.influyentes(1)[0][0])
        self.assertGreater(ficha["compras"], 0)

    def test_etapa4_rangos(self):
        rango = self.p.productos_por_precio(100, 600)
        self.assertTrue(rango)
        self.assertTrue(all(100 <= precio <= 600 for precio, _ in rango))
        tiempos = sorted(e["event_time"] for e in self.p.eventos)
        self.assertEqual(len(self.p.eventos_entre(tiempos[0], tiempos[-1])), len(self.p.eventos))

    def test_lote_de_prioridades_sale_por_urgencia(self):
        llegada, salida = self.p.lote_de_prioridades(por_nivel=2, semilla=42)
        self.assertEqual(len(llegada), 10)                      # 2 de cada uno de los 5 niveles
        self.assertEqual(sorted(map(id, llegada)), sorted(map(id, salida)))
        self.assertEqual([e["event_time"] for e in llegada], sorted(e["event_time"] for e in llegada))
        claves = [(e["prioridad"], e["event_time"]) for e in salida]
        self.assertEqual(claves, sorted(claves))                # urgencia y, a igual urgencia, el más antiguo
        self.assertNotEqual([id(e) for e in llegada], [id(e) for e in salida])

    def test_panel_de_ventas(self):
        v = self.p.ventas(k=5)
        compras = [e for e in self.p.eventos if e["event_type"] == "purchase"]
        self.assertEqual(v["ventas"] + v["retenidas_por_fraude"], len(compras))
        self.assertGreater(v["retenidas_por_fraude"], 0)        # el fraude no cuenta como venta
        self.assertAlmostEqual(v["ingresos"], sum(v["por_categoria"].values()), places=1)
        self.assertEqual(sum(v["por_tipo_orden"].values()), v["ventas"])
        self.assertNotIn("fraude_o_pago", v["por_tipo_orden"])
        ingresos_top = [total for *_, total in v["mas_vendidos"]]
        self.assertEqual(ingresos_top, sorted(ingresos_top, reverse=True))
        self.assertTrue(0 < v["conversion"] < 1)

    def test_etapa8_grafo_con_compras_conjuntas(self):
        self.assertGreater(self.resumen[8]["aristas"], 20)
        top = self.p.influyentes(3)
        self.assertTrue(self.p.e8.relacionados(top[0][0], 3))

    def test_etapa7_usa_la_matriz_de_la_etapa_3(self):
        self.assertEqual(self.p.servicio.conjuntos_compra, self.p.e3.compradores_por_producto())

    def test_similitud_frente_al_exacto(self):
        c = self.p.comparar_similitud(k=5, muestras=20)
        self.assertEqual(c["kd_tree"]["recall"], 1.0)           # el KD-Tree es exacto
        self.assertGreaterEqual(c["ivf"]["recall"], 0.8)
        self.assertGreater(c["minhash_lsh"]["consultas"], 0)    # hay productos con compradores en común
        self.assertGreater(c["minhash_lsh"]["recall"], 0.0)

    def test_etapa9_salidas(self):
        s = self.p.servicio
        producto = self.p.influyentes(1)[0][0]
        self.assertTrue(s.recomendar(producto, 3))
        # Con 1K eventos cada producto tiene pocos compradores y el LSH no siempre
        # encuentra vecinos (ver comparar_similitud); al menos algún producto debe tenerlos.
        self.assertTrue(any(s.similares_por_compra(p, 3) for p in s.conjuntos_compra))
        self.assertEqual(len(s.alertas), self.resumen[6]["marcados"])

    def test_recorrido_de_las_10_etapas(self):
        pasos = self.p.recorrido(self.p.evento_para_demo())
        self.assertEqual(sorted(e for e, _, _ in pasos), list(range(10)))
        self.assertTrue(all(texto for _, _, texto in pasos))


if __name__ == "__main__":
    unittest.main()
