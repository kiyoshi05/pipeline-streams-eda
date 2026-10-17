import heapq
import random
import unittest

from src.etapa2_prioridad.heap import MinHeap
from experimentos.datos_sinteticos import iterar_eventos
from src.etapa0_ingesta import Etapa0Ingesta
from src.etapa1_preprocesamiento import Etapa1Preprocesamiento
from src.etapa2_prioridad.prioridad import (
    BAJA, ESTANDAR, EXPRESS, FRAUDE_O_PAGO, Etapa2Prioridad, asignar_prioridad,
)


def es_heap(datos):
    """True si cada padre es menor o igual que sus hijos."""
    n = len(datos)
    for i in range(n):
        for hijo in (2 * i + 1, 2 * i + 2):
            if hijo < n and datos[hijo] < datos[i]:
                return False
    return True


def vaciar(heap):
    """Saca todos los elementos con pop, en el orden en que salen."""
    return [heap.pop() for _ in range(len(heap))]


class PruebasMinHeap(unittest.TestCase):

    def test_vacio(self):
        h = MinHeap()
        self.assertEqual(len(h), 0)
        with self.assertRaises(IndexError):
            h.peek()
        with self.assertRaises(IndexError):
            h.pop()

    def test_un_elemento(self):
        h = MinHeap()
        h.push(7)
        self.assertEqual(h.peek(), 7)
        self.assertEqual(h.pop(), 7)
        self.assertEqual(len(h), 0)

    def test_push_como_en_papel(self):
        # Ejercicio 1: insertar 7, 3, 9, 1, 5 deja la lista [1, 3, 9, 7, 5]
        h = MinHeap()
        for x in (7, 3, 9, 1, 5):
            h.push(x)
        self.assertEqual(h._datos, [1, 3, 9, 7, 5])

    def test_pop_como_en_papel(self):
        # Ejercicio 2: dos pop sobre [1, 3, 9, 7, 5]
        h = MinHeap()
        for x in (7, 3, 9, 1, 5):
            h.push(x)
        self.assertEqual(h.pop(), 1)
        self.assertEqual(h._datos, [3, 5, 9, 7])
        self.assertEqual(h.pop(), 3)
        self.assertEqual(h._datos, [5, 7, 9])

    def test_peek_no_saca(self):
        h = MinHeap([4, 2, 6])
        self.assertEqual(h.peek(), 2)
        self.assertEqual(h.peek(), 2)
        self.assertEqual(len(h), 3)

    def test_orden_de_salida(self):
        h = MinHeap([5, 3, 8, 1, 9, 2])
        self.assertEqual(vaciar(h), [1, 2, 3, 5, 8, 9])

    def test_repetidos(self):
        h = MinHeap([3, 1, 3, 1, 2])
        self.assertEqual(vaciar(h), [1, 1, 2, 3, 3])

    def test_heapify_cumple_la_regla(self):
        azar = random.Random(42)
        for n in (0, 1, 2, 3, 10, 100, 1000):
            with self.subTest(n=n):
                h = MinHeap([azar.randint(0, 100) for _ in range(n)])
                self.assertTrue(es_heap(h._datos))

    def test_heapify_igual_que_push(self):
        azar = random.Random(7)
        datos = [azar.randint(0, 1000) for _ in range(500)]
        con_heapify = MinHeap(datos)
        con_push = MinHeap()
        for x in datos:
            con_push.push(x)
        self.assertEqual(vaciar(con_heapify), vaciar(con_push))

    def test_no_modifica_la_entrada(self):
        datos = [5, 3, 8, 1]
        MinHeap(datos).pop()
        self.assertEqual(datos, [5, 3, 8, 1])

    def test_contra_sorted_al_azar(self):
        azar = random.Random(123)
        for _ in range(200):
            datos = [azar.randint(-50, 50) for _ in range(azar.randint(0, 80))]
            with self.subTest(datos=datos):
                self.assertEqual(vaciar(MinHeap(datos)), sorted(datos))

    def test_push_y_pop_mezclados_contra_heapq(self):
        # heapq de Python es la referencia: las dos deben sacar lo mismo
        azar = random.Random(99)
        h = MinHeap()
        ref = []
        for _ in range(2000):
            if ref and azar.random() < 0.4:
                self.assertEqual(h.pop(), heapq.heappop(ref))
            else:
                x = azar.randint(0, 500)
                h.push(x)
                heapq.heappush(ref, x)
            self.assertEqual(len(h), len(ref))
            self.assertTrue(es_heap(h._datos))

    def test_tuplas_desempatan_por_tiempo_y_contador(self):
        # Clave de la etapa 2: (prioridad, event_time, contador, evento)
        h = MinHeap()
        h.push((3, 1001, 0, "view"))
        h.push((1, 1002, 1, "purchase express"))
        h.push((0, 1003, 2, "alerta fraude"))
        h.push((3, 1000, 3, "view anterior"))
        h.push((3, 1000, 4, "view anterior, llegó después"))
        self.assertEqual([t[3] for t in vaciar(h)], [
            "alerta fraude",
            "purchase express",
            "view anterior",
            "view anterior, llegó después",
            "view",
        ])

    def test_contador_evita_comparar_diccionarios(self):
        # Sin contador, dos tuplas iguales en (prioridad, tiempo) comparan los dict y fallan
        h = MinHeap()
        h.push((2, 1000, 0, {"product_id": 1}))
        h.push((2, 1000, 1, {"product_id": 2}))
        self.assertEqual(h.pop()[3], {"product_id": 1})
        self.assertEqual(h.pop()[3], {"product_id": 2})


def ev(t, tipo="view", **extra):
    """Evento mínimo para las pruebas."""
    evento = {"event_time": t, "event_type": tipo, "product_id": t}
    evento.update(extra)
    return evento


class PruebasAsignarPrioridad(unittest.TestCase):

    def test_por_tipo_de_evento(self):
        self.assertEqual(asignar_prioridad(ev(1, "purchase")), ESTANDAR)
        for tipo in ("view", "cart", "remove_from_cart"):
            with self.subTest(tipo=tipo):
                self.assertEqual(asignar_prioridad(ev(1, tipo)), BAJA)

    def test_fraude_gana_al_tipo(self):
        self.assertEqual(asignar_prioridad(ev(1, "view", es_fraude=True)), FRAUDE_O_PAGO)
        self.assertEqual(asignar_prioridad(ev(1, "view", es_fraude="true")), FRAUDE_O_PAGO)
        self.assertEqual(asignar_prioridad(ev(1, "view", es_fraude=False)), BAJA)
        self.assertEqual(asignar_prioridad(ev(1, "view", es_fraude="False")), BAJA)

    def test_respeta_la_prioridad_del_generador(self):
        self.assertEqual(asignar_prioridad(ev(1, "view", prioridad=EXPRESS)), EXPRESS)
        self.assertEqual(asignar_prioridad(ev(1, "view", prioridad="1")), EXPRESS)

    def test_prioridad_invalida_se_ignora(self):
        for valor in (7, -1, "abc", None, ""):
            with self.subTest(valor=valor):
                self.assertEqual(asignar_prioridad(ev(1, "purchase", prioridad=valor)), ESTANDAR)


class PruebasEtapa2(unittest.TestCase):

    def test_vacia(self):
        e2 = Etapa2Prioridad()
        self.assertTrue(e2.esta_vacia())
        self.assertEqual(e2.extraer(5), [])
        with self.assertRaises(IndexError):
            e2.siguiente()

    def test_urgente_primero(self):
        e2 = Etapa2Prioridad()
        e2.recibir([
            ev(1, "view"),
            ev(2, "purchase"),
            ev(3, "view", es_fraude=True),
            ev(4, "cart", prioridad=EXPRESS),
        ])
        salida = e2.extraer()
        self.assertEqual([e["event_time"] for e in salida], [3, 4, 2, 1])
        self.assertEqual([e["prioridad"] for e in salida], [0, 1, 2, 3])

    def test_misma_prioridad_sale_el_mas_antiguo(self):
        e2 = Etapa2Prioridad()
        e2.recibir([ev(30), ev(10), ev(20)])
        self.assertEqual([e["event_time"] for e in e2.extraer()], [10, 20, 30])

    def test_empate_total_respeta_orden_de_llegada(self):
        e2 = Etapa2Prioridad()
        e2.recibir([ev(5, product_id=1), ev(5, product_id=2), ev(5, product_id=3)])
        self.assertEqual([e["product_id"] for e in e2.extraer()], [1, 2, 3])

    def test_extraer_por_partes(self):
        e2 = Etapa2Prioridad()
        e2.recibir([ev(t) for t in range(10)])
        self.assertEqual(len(e2.extraer(3)), 3)
        self.assertEqual(len(e2), 7)
        self.assertEqual(len(e2.extraer(100)), 7)
        self.assertTrue(e2.esta_vacia())

    def test_varios_lotes(self):
        # Un fraude que llega en el segundo lote sale antes que lo que ya esperaba
        e2 = Etapa2Prioridad()
        e2.recibir([ev(1), ev(2)])
        e2.recibir([ev(3, es_fraude=True)])
        self.assertEqual(e2.siguiente()["event_time"], 3)

    def test_no_modifica_la_entrada(self):
        lote = [ev(1, "purchase")]
        Etapa2Prioridad().recibir(lote)
        self.assertNotIn("prioridad", lote[0])

    def test_metricas(self):
        e2 = Etapa2Prioridad()
        e2.recibir([ev(1), ev(2, "purchase"), ev(3, es_fraude=True)])
        e2.extraer(1)
        m = e2.metricas()
        self.assertEqual(m["recibidos"], 3)
        self.assertEqual(m["entregados"], 1)
        self.assertEqual(m["en_cola"], 2)
        self.assertEqual(m["por_prioridad"], {"fraude_o_pago": 1, "express": 0, "estandar": 1, "baja": 1})

    def test_integracion_etapas_0_1_2(self):
        # Stream sintético -> etapa 0 -> etapa 1 -> etapa 2
        e0 = Etapa0Ingesta(capacidad=2_000, tam_lote=500)
        e1 = Etapa1Preprocesamiento()
        e2 = Etapa2Prioridad()
        limpios = 0
        for lote in e0.procesar_stream(iterar_eventos(5_000, semilla=42)):
            resultado = e1.procesar(lote)
            limpios += e2.recibir(resultado.eventos)
        salida = e2.extraer()
        self.assertEqual(len(salida), limpios)
        claves = [(e["prioridad"], e["event_time"]) for e in salida]
        self.assertEqual(claves, sorted(claves))
        self.assertTrue(any(e["event_type"] == "purchase" for e in salida))


if __name__ == "__main__":
    unittest.main()
