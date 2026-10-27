"""Integración de las etapas del integrante B con las etapas 0 y 1:

stream sintético -> 0 (cola) -> 1 (limpieza) -> 2 (prioridad) -> 3 (lookup)
-> 4 (índice) -> 8 (grafo de co-compra)

Las etapas 5, 6, 7 y 9 están en otras ramas; cuando se unan, irán entre la 4
y la 8 sin cambiar estas pruebas, porque cada etapa deja pasar los eventos.
"""

import unittest
from itertools import combinations

from experimentos.datos_sinteticos import iterar_eventos
from src.etapa0_ingesta import Etapa0Ingesta
from src.etapa1_preprocesamiento import Etapa1Preprocesamiento
from src.etapa2_prioridad.prioridad import Etapa2Prioridad
from src.etapa3_lookup import Etapa3Lookup
from src.etapa4_indice import Etapa4Indice
from src.etapa8_grafo import Etapa8Grafo, modularidad


class PruebasIntegracion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e0 = Etapa0Ingesta(capacidad=5_000, tam_lote=1_000)
        cls.e1 = Etapa1Preprocesamiento()
        cls.e2 = Etapa2Prioridad()
        cls.e3 = Etapa3Lookup(capacidad_cache=500)
        cls.e4 = Etapa4Indice(orden=32)
        cls.e8 = Etapa8Grafo()
        cls.salida = []
        cls.prioridades_por_lote = []
        for lote in cls.e0.procesar_stream(iterar_eventos(20_000, semilla=42)):
            limpio = cls.e1.procesar(lote).eventos
            cls.e2.recibir(limpio)
            urgentes = cls.e2.extraer()
            cls.prioridades_por_lote.append([e["prioridad"] for e in urgentes])
            eventos = cls.e8.procesar(cls.e4.procesar(cls.e3.procesar(urgentes)))
            cls.salida.extend(eventos)

    def test_ningun_evento_se_pierde(self):
        self.assertGreater(len(self.salida), 18_000)
        self.assertEqual(self.e3.metricas()["recibidos"], len(self.salida))
        self.assertEqual(self.e4.metricas()["recibidos"], len(self.salida))
        self.assertEqual(self.e8.metricas()["recibidos"], len(self.salida))

    def test_cada_lote_sale_por_urgencia(self):
        for prioridades in self.prioridades_por_lote:
            self.assertEqual(prioridades, sorted(prioridades))

    def test_etapa3_tiene_todos_los_productos(self):
        productos = {e["product_id"] for e in self.salida}
        self.assertEqual(len(self.e3.catalogo), len(productos))
        un_producto = next(iter(productos))
        ficha = self.e3.consultar(un_producto)
        contados = sum(ficha[c] for c in ("vistas", "carritos", "quitados", "compras"))
        self.assertEqual(contados, sum(1 for e in self.salida if e["product_id"] == un_producto))
        self.assertGreater(self.e3.interacciones.nnz, 0)
        self.assertLess(self.e3.interacciones.densidad, 0.01)   # usuario x producto es muy dispersa

    def test_etapa4_indexa_tiempo_y_precio(self):
        tiempos = [e["event_time"] for e in self.salida]
        self.assertEqual(len(self.e4.eventos_entre(min(tiempos), max(tiempos))), len(self.salida))
        medio = sorted(tiempos)[len(tiempos) // 2]
        self.assertEqual(len(self.e4.eventos_entre(medio, max(tiempos))), sum(1 for t in tiempos if t >= medio))
        productos = {e["product_id"] for e in self.salida}
        precios = self.e4.productos_por_precio()
        self.assertEqual(len(precios), len(productos))   # un precio vigente por producto
        self.assertEqual([p for p, _ in precios], sorted(p for p, _ in precios))
        # El precio vigente es el del evento más reciente de cada producto
        # (a igual tiempo, el último que llegó a la etapa)
        ultimo = {}
        for e in self.salida:
            previo = ultimo.get(e["product_id"])
            if previo is None or e["event_time"] >= previo[0]:
                ultimo[e["product_id"]] = (e["event_time"], e["price"])
        for p in productos:
            self.assertEqual(self.e4.precio(p), ultimo[p][1])

    def test_etapa8_grafo_coincide_con_las_compras(self):
        por_sesion = {}
        for e in self.salida:
            if e["event_type"] == "purchase":
                por_sesion.setdefault(e["user_session"], set()).add(e["product_id"])
        esperado = {}
        for productos in por_sesion.values():
            for u, v in combinations(sorted(productos), 2):
                esperado[(u, v)] = esperado.get((u, v), 0) + 1
        obtenido = {tuple(sorted((u, v))): w for u, v, w in self.e8.grafo.aristas()}
        self.assertGreater(len(esperado), 0)
        self.assertEqual(obtenido, esperado)

    def test_etapa8_salidas_para_el_servicio(self):
        top = self.e8.influyentes(5)
        self.assertEqual(len(top), 5)
        self.assertEqual([s for _, s in top], sorted((s for _, s in top), reverse=True))
        self.assertTrue(self.e8.relacionados(top[0][0], 3))
        particion = self.e8.comunidades()
        self.assertEqual(set(particion), set(self.e8.grafo.nodos()))
        self.assertGreaterEqual(modularidad(self.e8.grafo, particion), 0.0)


if __name__ == "__main__":
    unittest.main()
