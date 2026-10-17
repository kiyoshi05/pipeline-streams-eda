import heapq
import random
import unittest

from src.etapa2_prioridad.heap import MinHeap


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


if __name__ == "__main__":
    unittest.main()