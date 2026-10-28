import random
import unittest
from collections import OrderedDict

from src.etapa3_lookup import CacheLRU, Etapa3Lookup, MatrizDispersa, TablaHash


class PruebasTablaHash(unittest.TestCase):

    def test_vacia(self):
        t = TablaHash()
        self.assertEqual(len(t), 0)
        self.assertIsNone(t.obtener(1))
        self.assertEqual(t.obtener(1, "nada"), "nada")
        self.assertFalse(t.eliminar(1))
        with self.assertRaises(KeyError):
            t[1]
        with self.assertRaises(KeyError):
            del t[1]

    def test_insertar_reemplaza(self):
        t = TablaHash()
        t.insertar("a", 1)
        t.insertar("a", 2)
        self.assertEqual(len(t), 1)
        self.assertEqual(t["a"], 2)

    def test_claves_de_varios_tipos(self):
        t = TablaHash()
        claves = [0, -5, 10**12, "producto", (1, "x"), 3.5, None]
        for i, k in enumerate(claves):
            t[k] = i
        for i, k in enumerate(claves):
            self.assertEqual(t[k], i)
            self.assertIn(k, t)

    def test_crece_y_mantiene_carga(self):
        t = TablaHash(capacidad=8)
        for i in range(10_000):
            t[1_000_000 + i] = i
        self.assertEqual(len(t), 10_000)
        self.assertLessEqual(t.factor_carga, t.carga_maxima)
        self.assertGreater(t.redimensionamientos, 0)
        self.assertTrue(all(t[1_000_000 + i] == i for i in range(10_000)))

    def test_ids_consecutivos_se_reparten(self):
        # Los product_id de REES46 son casi consecutivos: ninguna cadena debe quedar larga
        t = TablaHash()
        for i in range(50_000):
            t[1_000_000 + i] = i
        self.assertLessEqual(t.cadena_mas_larga(), 8)

    def test_contra_dict_al_azar(self):
        azar = random.Random(42)
        t, ref = TablaHash(), {}
        for _ in range(20_000):
            k = azar.randrange(3_000)
            op = azar.random()
            if op < 0.5:
                t[k] = op
                ref[k] = op
            elif op < 0.75:
                self.assertEqual(t.eliminar(k), k in ref)
                ref.pop(k, None)
            else:
                self.assertEqual(t.obtener(k), ref.get(k))
            self.assertEqual(len(t), len(ref))
        self.assertEqual(dict(t.items()), ref)
        self.assertEqual(sorted(t), sorted(ref))
        self.assertEqual(sorted(t.valores()), sorted(ref.values()))


class PruebasCacheLRU(unittest.TestCase):

    def test_capacidad_invalida(self):
        with self.assertRaises(ValueError):
            CacheLRU(0)

    def test_expulsa_el_menos_reciente(self):
        c = CacheLRU(2)
        c.poner("a", 1)
        c.poner("b", 2)
        self.assertEqual(c.obtener("a"), 1)          # ahora "b" es el más antiguo
        self.assertEqual(c.poner("c", 3), ("b", 2))  # sale "b"
        self.assertNotIn("b", c)
        self.assertEqual(list(c.claves_por_uso()), ["c", "a"])

    def test_actualizar_no_expulsa(self):
        c = CacheLRU(2)
        c.poner("a", 1)
        c.poner("b", 2)
        self.assertIsNone(c.poner("a", 10))
        self.assertEqual(len(c), 2)
        self.assertEqual(c.obtener("a"), 10)
        self.assertEqual(list(c.claves_por_uso()), ["a", "b"])

    def test_contiene_no_cambia_el_orden(self):
        c = CacheLRU(2)
        c.poner("a", 1)
        c.poner("b", 2)
        self.assertIn("a", c)
        c.poner("c", 3)
        self.assertNotIn("a", c)   # "in" no lo marcó como usado

    def test_eliminar(self):
        c = CacheLRU(3)
        c.poner("a", 1)
        self.assertTrue(c.eliminar("a"))
        self.assertFalse(c.eliminar("a"))
        self.assertEqual(len(c), 0)
        self.assertEqual(list(c.claves_por_uso()), [])

    def test_estadisticas(self):
        c = CacheLRU(1)
        c.poner(1, "x")
        c.obtener(1)
        c.obtener(2)
        c.poner(2, "y")
        self.assertEqual((c.aciertos, c.fallos, c.expulsiones), (1, 1, 1))
        self.assertEqual(c.tasa_aciertos, 0.5)

    def test_contra_ordereddict_al_azar(self):
        azar = random.Random(7)
        capacidad = 50
        c, ref = CacheLRU(capacidad), OrderedDict()
        for _ in range(20_000):
            k = azar.randrange(200)
            if azar.random() < 0.5:
                esperado = ref.get(k)
                if k in ref:
                    ref.move_to_end(k, last=False)
                self.assertEqual(c.obtener(k), esperado)
            else:
                expulsado = None
                if k in ref:
                    ref[k] = k
                    ref.move_to_end(k, last=False)
                else:
                    ref[k] = k
                    ref.move_to_end(k, last=False)
                    if len(ref) > capacidad:
                        expulsado = ref.popitem(last=True)
                self.assertEqual(c.poner(k, k), expulsado)
            self.assertLessEqual(len(c), capacidad)
        self.assertEqual(list(c.claves_por_uso()), list(ref))


class PruebasMatrizDispersa(unittest.TestCase):

    def test_sumar_y_obtener(self):
        m = MatrizDispersa()
        m.sumar("u1", "p1", 1)
        m.sumar("u1", "p1", 2)
        m.sumar("u2", "p1")
        self.assertEqual(m.obtener("u1", "p1"), 3)
        self.assertEqual(m.obtener("u9", "p9"), 0.0)
        self.assertEqual(m.nnz, 2)
        self.assertEqual(m.forma, (2, 1))

    def test_cero_elimina_la_celda(self):
        m = MatrizDispersa()
        m.sumar(1, 10, 2)
        m.sumar(1, 10, -2)
        self.assertEqual(m.nnz, 0)
        self.assertEqual(m.forma, (0, 0))
        m.asignar(1, 10, 5)
        m.asignar(1, 10, 0)
        self.assertEqual(m.nnz, 0)

    def test_filas_y_columnas_coinciden(self):
        azar = random.Random(3)
        m, ref = MatrizDispersa(), {}
        for _ in range(5_000):
            f, c, v = azar.randrange(50), azar.randrange(80), azar.choice([1, 2, 4, -1])
            m.sumar(f, c, v)
            ref[(f, c)] = ref.get((f, c), 0) + v
            if ref[(f, c)] == 0:
                del ref[(f, c)]
        self.assertEqual({(f, c): v for f, c, v in m.items()}, ref)
        self.assertEqual(m.nnz, len(ref))
        for f in range(50):
            self.assertEqual(m.fila(f), {c: v for (ff, c), v in ref.items() if ff == f})
        for c in range(80):
            self.assertEqual(m.columna(c), {f: v for (f, cc), v in ref.items() if cc == c})

    def test_fila_es_copia(self):
        m = MatrizDispersa()
        m.sumar(1, 2, 3)
        m.fila(1)[2] = 99
        self.assertEqual(m.obtener(1, 2), 3)

    def test_densidad(self):
        m = MatrizDispersa()
        m.sumar(1, 1)
        m.sumar(2, 2)
        self.assertEqual(m.densidad, 0.5)   # 2 celdas de 2 x 2

    def test_conjuntos_jaccard_y_coseno(self):
        m = MatrizDispersa()
        for u in (1, 2, 3):
            m.sumar(u, "A", 1)
        for u in (2, 3, 4):
            m.sumar(u, "B", 1)
        self.assertEqual(m.conjuntos_por_columna(), {"A": {1, 2, 3}, "B": {2, 3, 4}})
        self.assertAlmostEqual(m.jaccard_columnas("A", "B"), 2 / 4)
        self.assertAlmostEqual(m.coseno_columnas("A", "B"), 2 / 3)
        self.assertEqual(m.jaccard_columnas("A", "Z"), 0.0)
        self.assertEqual(m.coseno_columnas("A", "Z"), 0.0)

    def test_conjuntos_con_minimo(self):
        m = MatrizDispersa()
        m.sumar(1, "A", 1)   # solo vista
        m.sumar(2, "A", 4)   # compra
        m.sumar(3, "B", 1)
        self.assertEqual(m.conjuntos_por_columna(minimo=4), {"A": {2}})


def ev(t, tipo, producto, usuario=1, precio=10.0, **extra):
    evento = {"event_time": t, "event_type": tipo, "product_id": producto, "user_id": usuario,
              "user_session": f"s{usuario}", "price": precio, "brand": "acme", "category_code": "ropa"}
    evento.update(extra)
    return evento


class PruebasEtapa3(unittest.TestCase):

    def test_ficha_y_contadores(self):
        e3 = Etapa3Lookup()
        lote = [ev(1, "view", 7), ev(2, "cart", 7), ev(3, "purchase", 7), ev(4, "view", 8)]
        salida = e3.procesar(lote)
        self.assertEqual(salida, lote)   # pasa los eventos sin cambios
        ficha = e3.consultar(7)
        self.assertEqual((ficha["vistas"], ficha["carritos"], ficha["compras"]), (1, 1, 1))
        self.assertEqual(ficha["ultima_vez"], 3)
        self.assertIsNone(e3.consultar(999))

    def test_precio_del_evento_mas_reciente(self):
        # La etapa 2 entrega por urgencia: un evento viejo que llega después no pisa el precio
        e3 = Etapa3Lookup()
        e3.procesar([ev(20, "view", 1, precio=15.0), ev(10, "purchase", 1, precio=12.0)])
        self.assertEqual(e3.consultar(1)["price"], 15.0)

    def test_cache_acierta_y_se_invalida(self):
        e3 = Etapa3Lookup(capacidad_cache=10)
        e3.procesar([ev(1, "view", 5)])
        e3.consultar(5)                     # fallo: va al catálogo
        e3.consultar(5)                     # acierto
        self.assertEqual((e3.cache.fallos, e3.cache.aciertos), (1, 1))
        e3.procesar([ev(2, "view", 5, precio=99.0)])
        self.assertNotIn(5, e3.cache)       # la ficha cambió: se quitó de la caché
        self.assertEqual(e3.consultar(5)["price"], 99.0)

    def test_consultar_devuelve_copia(self):
        e3 = Etapa3Lookup()
        e3.procesar([ev(1, "view", 5)])
        e3.consultar(5)["vistas"] = 1000
        self.assertEqual(e3.consultar(5)["vistas"], 1)

    def test_matriz_de_interacciones(self):
        e3 = Etapa3Lookup()
        e3.procesar([ev(1, "view", 5, usuario=1), ev(2, "purchase", 5, usuario=1),
                     ev(3, "remove_from_cart", 6, usuario=1), ev(4, "cart", 6, usuario=2)])
        self.assertEqual(e3.productos_de_usuario(1), {5: 5.0})   # 1 vista + 4 compra; quitar no suma
        self.assertEqual(e3.usuarios_por_producto(), {5: {1}, 6: {2}})
        self.assertEqual(e3.usuarios_por_producto(minimo=4), {5: {1}})

    def test_compradores_por_producto(self):
        e3 = Etapa3Lookup()
        e3.procesar([ev(1, "purchase", 5, usuario=1), ev(2, "purchase", 5, usuario=2),
                     ev(3, "view", 6, usuario=3), ev(4, "purchase", 5, usuario=1)])
        self.assertEqual(e3.compradores_por_producto(), {5: {1, 2}})   # una vista no es una compra

    def test_compradores_igual_que_la_etapa_7(self):
        from experimentos.stream_completo import generar_stream
        from src.etapa1_preprocesamiento import Etapa1Preprocesamiento
        from src.etapa7_similitud.minhash_lsh import conjuntos_usuarios_por_producto
        eventos, _ = generar_stream(1_000)
        limpios = Etapa1Preprocesamiento().procesar(eventos).eventos
        e3 = Etapa3Lookup()
        e3.procesar(limpios)
        self.assertEqual(e3.compradores_por_producto(), conjuntos_usuarios_por_producto(limpios))

    def test_metricas(self):
        e3 = Etapa3Lookup(capacidad_cache=1)
        e3.procesar([ev(1, "view", 1), ev(2, "view", 2)])
        e3.consultar(1)
        e3.consultar(2)
        m = e3.metricas()
        self.assertEqual(m["recibidos"], 2)
        self.assertEqual(m["productos"], 2)
        self.assertEqual(m["cache_expulsiones"], 1)
        self.assertEqual(m["matriz_celdas"], 2)


if __name__ == "__main__":
    unittest.main()
