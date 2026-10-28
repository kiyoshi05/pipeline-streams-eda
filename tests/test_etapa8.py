import random
import unittest

from src.etapa8_grafo import (
    Etapa8Grafo,
    GrafoCoCompra,
    correlacion_rangos,
    informacion_mutua_normalizada,
    label_propagation,
    louvain,
    mayores_k,
    modularidad,
    pagerank,
    ranking_por_grado,
    resumen,
)


def dos_triangulos():
    """Triángulos 1-2-3 y 4-5-6 unidos por la arista 3-4."""
    g = GrafoCoCompra()
    g.agregar_orden([1, 2, 3])
    g.agregar_orden([4, 5, 6])
    g.agregar_arista(3, 4)
    return g


def anillo_de_cliques(cliques=8, tamano=5):
    """Cliques unidos en anillo por una sola arista: las comunidades obvias son los cliques."""
    g = GrafoCoCompra()
    for c in range(cliques):
        g.agregar_orden(range(c * tamano, (c + 1) * tamano))
        g.agregar_arista(c * tamano, ((c + 1) % cliques) * tamano + 1)
    return g


def grafo_al_azar(n=60, aristas=200, semilla=1):
    azar = random.Random(semilla)
    g = GrafoCoCompra()
    for u in range(n):
        g.agregar_nodo(u)
    while g.n_aristas < aristas:
        u, v = azar.sample(range(n), 2)
        g.agregar_arista(u, v, azar.choice([1, 2, 3]))
    return g


def grupos(particion):
    """Partición como conjunto de conjuntos, sin importar los números de comunidad."""
    por_comunidad = {}
    for u, c in particion.items():
        por_comunidad.setdefault(c, set()).add(u)
    return {frozenset(s) for s in por_comunidad.values()}


class PruebasGrafo(unittest.TestCase):

    def test_orden_une_todos_los_pares(self):
        g = GrafoCoCompra()
        g.agregar_orden([1, 2, 3, 2])   # el 2 repetido no cuenta dos veces
        self.assertEqual((g.n_nodos, g.n_aristas, g.peso_total), (3, 3, 3.0))
        self.assertEqual(g.vecinos(1), {2: 1.0, 3: 1.0})

    def test_pesos_se_acumulan(self):
        g = GrafoCoCompra()
        g.agregar_orden([1, 2])
        g.agregar_orden([2, 1])
        self.assertEqual(g.peso(1, 2), 2.0)
        self.assertEqual(g.peso(2, 1), 2.0)
        self.assertEqual(g.n_aristas, 1)
        self.assertEqual(g.grado_ponderado(1), 2.0)

    def test_sin_lazos(self):
        with self.assertRaises(ValueError):
            GrafoCoCompra().agregar_arista(1, 1)

    def test_aristas_una_vez(self):
        g = dos_triangulos()
        aristas = list(g.aristas())
        self.assertEqual(len(aristas), 7)
        self.assertEqual(len({frozenset((u, v)) for u, v, _ in aristas}), 7)

    def test_adyacencia_ida_y_vuelta(self):
        g = grafo_al_azar()
        h = GrafoCoCompra.desde_adyacencia(g.adyacencia())
        self.assertEqual(h.adyacencia(), g.adyacencia())
        self.assertEqual(h.peso_total, g.peso_total)


class PruebasRanking(unittest.TestCase):

    def test_vacio(self):
        self.assertEqual(pagerank(GrafoCoCompra()), {})

    def test_suma_uno_y_converge(self):
        info = {}
        pr = pagerank(grafo_al_azar(), estadisticas=info)
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=9)
        self.assertTrue(info["convergio"])

    def test_simetria(self):
        # En un ciclo todos los nodos son equivalentes
        g = GrafoCoCompra()
        for i in range(6):
            g.agregar_arista(i, (i + 1) % 6)
        pr = pagerank(g)
        for v in pr.values():
            self.assertAlmostEqual(v, 1 / 6, places=9)

    def test_estrella(self):
        g = GrafoCoCompra()
        for hoja in range(1, 6):
            g.agregar_arista(0, hoja)
        pr = pagerank(g)
        self.assertEqual(mayores_k(pr, 1)[0][0], 0)
        # Valor exacto: c = (1-d)/6 + d·5h y h = (1-d)/6 + d·c/5  =>  c = (1 + 5d) / (6(1 + d))
        d = 0.85
        centro = (1 + 5 * d) / (6 * (1 + d))
        self.assertAlmostEqual(pr[0], centro, places=9)
        self.assertAlmostEqual(pr[1], (1 - centro) / 5, places=9)

    def test_igual_que_sistema_lineal(self):
        # PageRank resuelve (I - d·M) x = (1 - d)/n·1, con M_vu = w(u,v)/W(u)
        import numpy as np
        g = grafo_al_azar(n=30, aristas=80, semilla=4)
        nodos = list(g.nodos())
        idx = {u: i for i, u in enumerate(nodos)}
        n, d = len(nodos), 0.85
        M = np.zeros((n, n))
        for u in nodos:
            for v, w in g.vecinos(u).items():
                M[idx[v], idx[u]] = w / g.grado_ponderado(u)
        x = np.linalg.solve(np.eye(n) - d * M, np.full(n, (1 - d) / n))
        pr = pagerank(g)
        for u in nodos:
            self.assertAlmostEqual(pr[u], x[idx[u]], places=8)

    def test_nodo_aislado(self):
        g = dos_triangulos()
        g.agregar_nodo(99)   # sin aristas: su PageRank se reparte y no se pierde
        pr = pagerank(g)
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=9)
        self.assertEqual(min(pr, key=pr.get), 99)

    def test_personalizado(self):
        g = anillo_de_cliques()
        pr = pagerank(g, personalizacion={7: 1.0})
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=9)
        top = [u for u, _ in mayores_k(pr, 5)]
        self.assertTrue(set(top) <= set(range(5, 10)) | {0, 1, 11})   # el clique de 7 y sus puentes
        self.assertEqual(top[0], 7)
        with self.assertRaises(ValueError):
            pagerank(g, personalizacion={"no_existe": 1.0})

    def test_ranking_por_grado(self):
        g = dos_triangulos()
        self.assertEqual(ranking_por_grado(g), {1: 2, 2: 2, 3: 3, 4: 3, 5: 2, 6: 2})
        g.agregar_orden([1, 2])
        self.assertEqual(ranking_por_grado(g)[1], 3)
        self.assertEqual(ranking_por_grado(g, ponderado=False)[1], 2)

    def test_mayores_k(self):
        puntajes = {"a": 3, "b": 9, "c": 1, "d": 9, "e": 5}
        self.assertEqual(mayores_k(puntajes, 3), [("b", 9), ("d", 9), ("e", 5)])
        self.assertEqual(mayores_k(puntajes, 0), [])
        self.assertEqual(len(mayores_k(puntajes, 99)), 5)
        azar = random.Random(2)
        grande = {i: azar.random() for i in range(5_000)}
        esperado = sorted(grande.items(), key=lambda par: -par[1])[:20]
        self.assertEqual(mayores_k(grande, 20), esperado)

    def test_empates_por_id_menor(self):
        self.assertEqual(mayores_k({5: 1.0, 2: 1.0, 9: 1.0}, 2), [(2, 1.0), (5, 1.0)])

    def test_correlacion_rangos(self):
        a = {1: 1, 2: 2, 3: 3, 4: 4}
        self.assertAlmostEqual(correlacion_rangos(a, {1: 10, 2: 20, 3: 30, 4: 40}), 1.0)
        self.assertAlmostEqual(correlacion_rangos(a, {1: 4, 2: 3, 3: 2, 4: 1}), -1.0)


class PruebasComunidades(unittest.TestCase):

    def test_modularidad_conocida(self):
        g = dos_triangulos()
        # Q = 2 · (3/7 - (7/14)²) = 5/14
        self.assertAlmostEqual(modularidad(g, {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1}), 5 / 14)
        self.assertAlmostEqual(modularidad(g, {u: 0 for u in g.nodos()}), 0.0)
        self.assertLess(modularidad(g, {u: u for u in g.nodos()}), 0)

    def test_modularidad_grafo_vacio(self):
        self.assertEqual(modularidad(GrafoCoCompra(), {}), 0.0)

    def test_louvain_dos_triangulos(self):
        p = louvain(dos_triangulos())
        self.assertEqual(grupos(p), {frozenset({1, 2, 3}), frozenset({4, 5, 6})})

    def test_ambos_encuentran_los_cliques(self):
        g = anillo_de_cliques()
        esperado = {frozenset(range(c * 5, c * 5 + 5)) for c in range(8)}
        for algoritmo in (louvain, label_propagation):
            with self.subTest(algoritmo=algoritmo.__name__):
                self.assertEqual(grupos(algoritmo(g, semilla=3)), esperado)

    def test_componentes_separadas_no_se_mezclan(self):
        g = GrafoCoCompra()
        g.agregar_orden([1, 2, 3])
        g.agregar_orden([10, 11, 12])
        g.agregar_nodo(99)
        for algoritmo in (louvain, label_propagation):
            p = algoritmo(g)
            self.assertNotEqual(p[1], p[10])
            self.assertEqual(p[1], p[3])
            self.assertEqual(resumen(p)["comunidades"], 3)

    def test_louvain_supera_al_azar_y_a_singletons(self):
        g = grafo_al_azar(n=120, aristas=400, semilla=8)
        q = modularidad(g, louvain(g))
        self.assertGreater(q, modularidad(g, {u: u for u in g.nodos()}))
        self.assertGreater(q, 0.2)

    def test_louvain_al_menos_tan_bueno_como_label_propagation(self):
        for semilla in range(5):
            g = grafo_al_azar(n=100, aristas=300, semilla=semilla)
            self.assertGreaterEqual(modularidad(g, louvain(g)) + 1e-9,
                                    modularidad(g, label_propagation(g)) - 0.05)

    def test_misma_semilla_mismo_resultado(self):
        g = grafo_al_azar()
        self.assertEqual(louvain(g, semilla=5), louvain(g, semilla=5))
        self.assertEqual(label_propagation(g, semilla=5), label_propagation(g, semilla=5))

    def test_numeradas_de_mayor_a_menor(self):
        g = GrafoCoCompra()
        g.agregar_orden([1, 2])
        g.agregar_orden([10, 11, 12, 13])
        p = louvain(g)
        self.assertEqual(p[10], 0)
        self.assertEqual(resumen(p), {"comunidades": 2, "tamanos": [4, 2]})

    def test_informacion_mutua(self):
        p = {1: 0, 2: 0, 3: 1, 4: 1}
        self.assertAlmostEqual(informacion_mutua_normalizada(p, {1: 5, 2: 5, 3: 9, 4: 9}), 1.0)
        self.assertAlmostEqual(informacion_mutua_normalizada(p, {1: 0, 2: 1, 3: 0, 4: 1}), 0.0)
        self.assertEqual(informacion_mutua_normalizada({1: 0}, {1: 0}), 1.0)


def compra(t, producto, sesion, tipo="purchase"):
    return {"event_time": t, "event_type": tipo, "product_id": producto, "user_session": sesion,
            "user_id": 1, "price": 10.0}


class PruebasEtapa8(unittest.TestCase):

    def test_arma_el_grafo_con_compras(self):
        e8 = Etapa8Grafo()
        lote = [compra(1, "A", "s1"), compra(2, "B", "s1"), compra(3, "C", "s1"),
                compra(4, "A", "s2"), compra(5, "B", "s2"), compra(6, "Z", "s3", tipo="view")]
        self.assertEqual(e8.procesar(lote), lote)
        g = e8.grafo
        self.assertEqual(g.peso("A", "B"), 2.0)   # juntos en dos órdenes
        self.assertEqual(g.peso("A", "C"), 1.0)
        self.assertNotIn("Z", g)                  # una vista no entra al grafo
        self.assertEqual(e8.relacionados("A", 2), [("B", 2.0), ("C", 1.0)])

    def test_compra_repetida_en_la_orden(self):
        e8 = Etapa8Grafo()
        e8.procesar([compra(1, "A", "s1"), compra(2, "B", "s1"), compra(3, "A", "s1")])
        self.assertEqual(e8.grafo.peso("A", "B"), 1.0)

    def test_ordenes_en_varios_lotes(self):
        e8 = Etapa8Grafo()
        e8.procesar([compra(1, "A", "s1")])
        e8.procesar([compra(2, "B", "s1")])
        self.assertEqual(e8.grafo.peso("A", "B"), 1.0)

    def test_ventana_olvida_sesiones_viejas(self):
        e8 = Etapa8Grafo(ventana_seg=100)
        e8.procesar([compra(0, "A", "s1")])
        e8.procesar([compra(500, "X", "s2")])     # s1 quedó fuera de la ventana
        e8.procesar([compra(501, "B", "s1")])     # la vuelve a abrir, pero ya sin "A"
        self.assertEqual(e8.grafo.peso("A", "B"), 0.0)
        self.assertEqual(e8.metricas()["ordenes_activas"], 2)

    def test_influyentes_y_comunidades(self):
        e8 = Etapa8Grafo()
        eventos = []
        t = 0
        for c in range(4):                        # 4 grupos de productos que se compran juntos
            productos = [c * 10 + i for i in range(4)]
            for s in range(3):
                for p in productos:
                    t += 1
                    eventos.append(compra(t, p, f"g{c}-s{s}"))
        eventos.append(compra(t + 1, 0, "puente"))
        eventos.append(compra(t + 2, 10, "puente"))
        e8.procesar(eventos)
        self.assertEqual(len(e8.influyentes(3)), 3)
        self.assertIn(e8.influyentes(1)[0][0], (0, 10))   # los productos puente son los más influyentes
        self.assertEqual(e8.comunidad_de(20), [21, 22, 23])
        m = e8.metricas(con_comunidades=True)
        self.assertEqual(m["louvain"]["comunidades"], 4)
        self.assertGreater(m["louvain"]["modularidad"], 0.6)
        self.assertEqual(m["label_propagation"]["comunidades"], 4)

    def test_resultados_guardados_se_recalculan(self):
        e8 = Etapa8Grafo()
        e8.procesar([compra(1, "A", "s1"), compra(2, "B", "s1")])
        primero = e8.puntajes()
        self.assertIs(e8.puntajes(), primero)            # sin cambios: no recalcula
        e8.procesar([compra(3, "C", "s1")])
        self.assertIsNot(e8.puntajes(), primero)
        self.assertIn("C", e8.puntajes())

    def test_metodo_desconocido(self):
        e8 = Etapa8Grafo()
        with self.assertRaises(ValueError):
            e8.puntajes("otro")
        with self.assertRaises(ValueError):
            e8.comunidades("otro")


if __name__ == "__main__":
    unittest.main()
