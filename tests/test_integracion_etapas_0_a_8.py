"""Integración de las etapas del integrante B con las etapas 0, 1 y 6:

stream sintético -> 0 (cola) -> 1 (limpieza) -> 2 (prioridad) -> 3 (lookup)
-> 4 (índice) -> 6 (fraude) -> 8 (grafo de co-compra)

La etapa 6 va como anotación después de la prioridad: marca cada evento con su
decisión de fraude y lo deja pasar, así las etapas siguientes reciben todo. Las
etapas 5, 7 y 9 están en otras ramas y encajarán igual sin cambiar estas pruebas.
"""

import unittest
from itertools import combinations

from experimentos.datos_sinteticos import generar_eventos_fraude, iterar_eventos
from src.etapa0_ingesta import Etapa0Ingesta
from src.etapa1_preprocesamiento import Etapa1Preprocesamiento
from src.etapa2_prioridad.prioridad import Etapa2Prioridad
from src.etapa3_lookup import Etapa3Lookup
from src.etapa4_indice import Etapa4Indice
from src.etapa6_probabilistico import Etapa6Fraude
from src.etapa8_grafo import Etapa8Grafo, modularidad


class PruebasIntegracion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e0 = Etapa0Ingesta(capacidad=5_000, tam_lote=1_000)
        cls.e1 = Etapa1Preprocesamiento()
        cls.e2 = Etapa2Prioridad()
        cls.e3 = Etapa3Lookup(capacidad_cache=500)
        cls.e4 = Etapa4Indice(orden=32)
        cls.e6 = Etapa6Fraude()
        cls.e8 = Etapa8Grafo()
        cls.salida = []
        cls.prioridades_por_lote = []
        for lote in cls.e0.procesar_stream(iterar_eventos(20_000, semilla=42)):
            limpio = cls.e1.procesar(lote).eventos
            cls.e2.recibir(limpio)
            urgentes = cls.e2.extraer()
            cls.prioridades_por_lote.append([e["prioridad"] for e in urgentes])
            anotados = cls.e6.procesar(cls.e4.procesar(cls.e3.procesar(urgentes)))
            eventos = cls.e8.procesar(anotados)
            cls.salida.extend(eventos)

    def test_ningun_evento_se_pierde(self):
        self.assertGreater(len(self.salida), 18_000)
        self.assertEqual(self.e3.metricas()["recibidos"], len(self.salida))
        self.assertEqual(self.e4.metricas()["recibidos"], len(self.salida))
        self.assertEqual(self.e6.metricas()["recibidos"], len(self.salida))
        self.assertEqual(self.e8.metricas()["recibidos"], len(self.salida))

    def test_etapa6_anota_y_deja_pasar(self):
        # Sobre este stream (sin campos de fraude) la etapa no marca nada,
        # pero anota cada evento y no pierde ninguno.
        self.assertTrue(all("fraude_predicho" in e for e in self.salida))
        self.assertEqual(self.e6.metricas()["marcados"], 0)
        self.assertFalse(self.e6.metricas()["con_etiqueta"])

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


class PruebasIntegracionFraude(unittest.TestCase):
    """La etapa 6 detectando fraude de punta a punta sobre el pipeline real:
    stream con fraude -> 0 (cola) -> 1 (limpieza) -> 2 (prioridad) -> 6 (fraude).
    """

    @classmethod
    def setUpClass(cls):
        eventos, lista_negra = generar_eventos_fraude(20_000, semilla=42)
        cls.fraude_real = sum(e["es_fraude"] for e in eventos)
        e0 = Etapa0Ingesta(capacidad=5_000, tam_lote=1_000)
        e1 = Etapa1Preprocesamiento()
        e2 = Etapa2Prioridad()
        cls.e6 = Etapa6Fraude(lista_negra=lista_negra, ventana_seg=10, umbral_velocidad=8)
        cls.procesados = 0
        for lote in e0.procesar_stream(eventos):
            limpio = e1.procesar(lote).eventos
            e2.recibir(limpio)
            anotados = cls.e6.procesar(e2.extraer())
            cls.procesados += len(anotados)

    def test_no_pierde_eventos(self):
        self.assertEqual(self.e6.metricas()["recibidos"], self.procesados)
        self.assertGreater(self.procesados, 18_000)

    def test_detecta_el_fraude(self):
        m = self.e6.metricas()
        self.assertTrue(m["con_etiqueta"])
        self.assertGreater(self.fraude_real, 0)
        self.assertEqual(m["fp"], 0)            # ninguna falsa alarma sobre este generador
        self.assertEqual(m["precision"], 1.0)
        self.assertGreater(m["recall"], 0.8)    # casi todo el fraude, pese al reordenamiento por prioridad


if __name__ == "__main__":
    unittest.main()
