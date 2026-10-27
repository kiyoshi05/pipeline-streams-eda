import math
import random
import unittest
from bisect import bisect_left, bisect_right

from src.etapa4_indice import BPlusTree, Etapa4Indice


def referencia(pares):
    """Pares (clave, valor) ordenados por clave y, a igual clave, por orden de inserción."""
    return sorted(pares, key=lambda par: par[0])


class PruebasBPlusTree(unittest.TestCase):

    def test_orden_invalido(self):
        with self.assertRaises(ValueError):
            BPlusTree(2)

    def test_vacio(self):
        b = BPlusTree(4)
        self.assertEqual(len(b), 0)
        self.assertEqual(b.buscar(5), [])
        self.assertEqual(list(b.rango()), [])
        self.assertEqual(b.altura, 1)
        with self.assertRaises(ValueError):
            b.minimo()
        b.verificar()

    def test_partir_como_en_papel(self):
        # Orden 3: máximo 2 claves por nodo. Insertar 1..7 obliga a partir hojas e internos.
        b = BPlusTree(3)
        for x in range(1, 8):
            b.insertar(x, f"v{x}")
            b.verificar()
        self.assertEqual(list(b), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(b.altura, 3)
        self.assertEqual(b.buscar(4), ["v4"])

    def test_claves_repetidas(self):
        b = BPlusTree(4)
        for producto in ("a", "b", "c"):
            b.insertar(19.9, producto)
        self.assertEqual(b.buscar(19.9), ["a", "b", "c"])
        self.assertEqual(len(b), 3)
        self.assertEqual(b.n_claves, 1)

    def test_contra_lista_ordenada_al_azar(self):
        azar = random.Random(42)
        for orden in (3, 4, 5, 16, 64):
            with self.subTest(orden=orden):
                b, pares = BPlusTree(orden), []
                for i in range(3_000):
                    k = azar.randrange(1_000)
                    b.insertar(k, i)
                    pares.append((k, i))
                b.verificar()
                ref = referencia(pares)
                self.assertEqual(list(b.items()), ref)
                claves = [k for k, _ in ref]
                for _ in range(200):
                    x = azar.randrange(-10, 1_010)
                    esperado = [v for k, v in ref if k == x]
                    self.assertEqual(b.buscar(x), esperado)
                for _ in range(200):
                    lo, hi = sorted((azar.randrange(-10, 1_010), azar.randrange(-10, 1_010)))
                    esperado = ref[bisect_left(claves, lo):bisect_right(claves, hi)]
                    self.assertEqual(list(b.rango(lo, hi)), esperado)
                    esperado_excl = ref[bisect_left(claves, lo):bisect_left(claves, hi)]
                    self.assertEqual(list(b.rango(lo, hi, incluir_hasta=False)), esperado_excl)

    def test_rango_abierto(self):
        b = BPlusTree(4)
        for x in range(10):
            b.insertar(x, x)
        self.assertEqual([k for k, _ in b.rango(hasta=3)], [0, 1, 2, 3])
        self.assertEqual([k for k, _ in b.rango(desde=7)], [7, 8, 9])
        self.assertEqual((b.minimo(), b.maximo()), (0, 9))

    def test_altura_logaritmica_y_lecturas(self):
        b = BPlusTree(64)
        for x in range(100_000):
            b.insertar(x, x)
        # Con hojas al menos medio llenas, la altura no pasa de log_{b/2}(n) + 1
        self.assertLessEqual(b.altura, math.ceil(math.log(100_000, 32)) + 1)
        b.buscar(54_321)
        self.assertEqual(b.nodos_leidos, b.altura)   # una lectura de página por nivel

    def test_insercion_ascendente_y_descendente(self):
        for valores in (range(2_000), range(2_000, 0, -1)):
            b = BPlusTree(5)
            for x in valores:
                b.insertar(x, x)
            b.verificar()
            self.assertEqual(list(b), sorted(valores))

    def test_eliminar(self):
        b = BPlusTree(4)
        for x in range(20):
            b.insertar(x % 5, x)
        self.assertEqual(b.eliminar(2, 7), 1)
        self.assertEqual(b.eliminar(2, 7), 0)         # ya no está
        self.assertEqual(b.eliminar(99), 0)           # clave inexistente
        self.assertEqual(b.buscar(2), [2, 12, 17])
        self.assertEqual(b.eliminar(2), 3)            # todos los valores de la clave
        self.assertNotIn(2, b)
        self.assertEqual(len(b), 16)
        b.verificar()

    def test_eliminar_al_azar_contra_referencia(self):
        azar = random.Random(5)
        b, pares = BPlusTree(4), []
        for i in range(2_000):
            k = azar.randrange(300)
            b.insertar(k, i)
            pares.append((k, i))
        azar.shuffle(pares)
        quitados, quedan = pares[:1_500], pares[1_500:]
        for k, v in quitados:
            self.assertEqual(b.eliminar(k, v), 1)
        b.verificar()
        self.assertEqual(sorted(b.items()), sorted(quedan))
        for k, v in quedan[:100]:
            b.insertar(k, -v)     # se puede seguir insertando después de borrar
        b.verificar()
        self.assertEqual(b.maximo(), max(k for k, _ in quedan))

    def test_vaciar_todo(self):
        b = BPlusTree(3)
        for x in range(50):
            b.insertar(x, x)
        for x in range(50):
            b.eliminar(x)
        self.assertEqual(len(b), 0)
        self.assertEqual(list(b.rango()), [])
        with self.assertRaises(ValueError):
            b.maximo()


def ev(t, producto, precio, tipo="view"):
    return {"event_time": t, "event_type": tipo, "product_id": producto, "price": precio,
            "user_id": 1, "user_session": "s1"}


class PruebasEtapa4(unittest.TestCase):

    def test_eventos_entre(self):
        e4 = Etapa4Indice(orden=4)
        lote = [ev(t, t % 3, 10.0) for t in (5, 1, 9, 3, 7)]
        self.assertEqual(e4.procesar(lote), lote)
        self.assertEqual([e["event_time"] for e in e4.eventos_entre(3, 7)], [3, 5, 7])
        self.assertEqual([e["event_time"] for e in e4.eventos_entre(3, 7, incluir_hasta=False)], [3, 5])
        self.assertEqual(len(e4.eventos_en(9)), 1)

    def test_productos_por_precio(self):
        e4 = Etapa4Indice(orden=4)
        e4.procesar([ev(1, "a", 50.0), ev(2, "b", 10.0), ev(3, "c", 30.0), ev(4, "d", 30.0)])
        self.assertEqual(e4.productos_por_precio(20, 40), [(30.0, "c"), (30.0, "d")])
        self.assertEqual(e4.productos_por_precio(limite=2), [(10.0, "b"), (30.0, "c")])
        self.assertEqual(e4.productos_con_precio(50.0), ["a"])

    def test_cambio_de_precio_no_duplica(self):
        e4 = Etapa4Indice(orden=4)
        e4.procesar([ev(1, "a", 50.0), ev(2, "a", 40.0), ev(3, "a", 40.0)])
        self.assertEqual(e4.productos_por_precio(), [(40.0, "a")])
        self.assertEqual(e4.precio("a"), 40.0)
        self.assertEqual(e4.metricas()["cambios_de_precio"], 1)

    def test_evento_viejo_no_pisa_el_precio(self):
        e4 = Etapa4Indice(orden=4)
        e4.procesar([ev(10, "a", 50.0), ev(5, "a", 20.0)])
        self.assertEqual(e4.precio("a"), 50.0)
        self.assertEqual(e4.productos_por_precio(), [(50.0, "a")])

    def test_contra_referencia_al_azar(self):
        azar = random.Random(11)
        e4 = Etapa4Indice(orden=8)
        vigente = {}
        for t in range(3_000):
            p, precio = azar.randrange(200), float(azar.randrange(1, 100))
            e4.procesar([ev(t, p, precio)])
            vigente[p] = precio
        self.assertEqual(sorted(e4.productos_por_precio()), sorted((pr, p) for p, pr in vigente.items()))
        self.assertEqual(len(e4.eventos_entre(1_000, 1_999)), 1_000)
        e4.por_tiempo.verificar()
        e4.por_precio.verificar()


if __name__ == "__main__":
    unittest.main()
