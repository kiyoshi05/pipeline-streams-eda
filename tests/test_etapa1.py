import bisect
import random
import unittest
from collections import namedtuple
from dataclasses import dataclass

from experimentos.datos_sinteticos import generar_eventos
from src.etapa0_ingesta import Etapa0Ingesta
from src.etapa1_preprocesamiento import (
    Etapa1Preprocesamiento,
    busqueda_lineal,
    clave_evento,
    contiene,
    contiene_evento,
    deduplicar_exacto,
    deduplicar_ventana,
    evaluar_deduplicacion,
    eventos_en_rango,
    insercion,
    lower_bound,
    merge_sort,
    normalizar_evento,
    procesar_lote,
    quicksort,
    rango,
    upper_bound,
)

ALGORITMOS = {"merge_sort": merge_sort, "quicksort": quicksort, "insercion": insercion}


def fila(**cambios):
    base = {
        "event_time": "2019-10-01 00:00:00 UTC",
        "event_type": "view",
        "product_id": "44600062",
        "category_code": "",
        "brand": "Shiseido ",
        "price": "35.79",
        "user_id": "541312140",
        "user_session": "72d76fde-8bb3-4e00-8c23-a032dfed738c",
    }
    base.update(cambios)
    return base


class TestOrdenacion(unittest.TestCase):
    def test_casos_borde(self):
        casos = [[], [1], [1, 2, 3], [3, 2, 1], [5] * 20, [2, 1, 2, 1, 2]]
        for nombre, ordenar in ALGORITMOS.items():
            for caso in casos:
                with self.subTest(algoritmo=nombre, caso=caso):
                    self.assertEqual(ordenar(caso), sorted(caso))

    def test_contra_sorted(self):
        azar = random.Random(1)
        for nombre, ordenar in ALGORITMOS.items():
            for _ in range(200):
                n = azar.randrange(0, 300 if nombre == "insercion" else 2_000)
                datos = [azar.randrange(50) for _ in range(n)]
                with self.subTest(algoritmo=nombre, n=n):
                    self.assertEqual(ordenar(datos), sorted(datos))

    def test_con_clave_y_sin_mutar(self):
        datos = [("b", 2), ("a", 3), ("c", 1)]
        copia = list(datos)
        for nombre, ordenar in ALGORITMOS.items():
            with self.subTest(algoritmo=nombre):
                self.assertEqual(ordenar(datos, clave=lambda x: x[1]), [("c", 1), ("b", 2), ("a", 3)])
                self.assertEqual(datos, copia)

    def test_estabilidad(self):
        azar = random.Random(2)
        datos = [(azar.randrange(10), llegada) for llegada in range(1_000)]
        esperado = sorted(datos, key=lambda x: x[0])  # sorted de Python es estable
        for nombre in ("merge_sort", "insercion"):
            with self.subTest(algoritmo=nombre):
                self.assertEqual(ALGORITMOS[nombre](datos, clave=lambda x: x[0]), esperado)

    def test_quicksort_reproducible(self):
        datos = [random.Random(3).random() for _ in range(500)]
        self.assertEqual(quicksort(datos, semilla=9), quicksort(datos, semilla=9))


class TestBusqueda(unittest.TestCase):
    def test_contra_bisect(self):
        azar = random.Random(4)
        for _ in range(300):
            datos = sorted(azar.randrange(30) for _ in range(azar.randrange(0, 60)))
            for x in range(-2, 33):
                self.assertEqual(lower_bound(datos, x), bisect.bisect_left(datos, x))
                self.assertEqual(upper_bound(datos, x), bisect.bisect_right(datos, x))
                self.assertEqual(contiene(datos, x), x in datos)
                self.assertEqual(busqueda_lineal(datos, x), datos.index(x) if x in datos else -1)

    def test_rango_y_clave(self):
        datos = [{"t": t} for t in (1, 3, 3, 5, 8, 8, 9)]
        i, j = rango(datos, 3, 8, clave=lambda d: d["t"])
        self.assertEqual([d["t"] for d in datos[i:j]], [3, 3, 5, 8, 8])
        self.assertEqual(rango(datos, 10, 20, clave=lambda d: d["t"]), (7, 7))


class TestNormalizacion(unittest.TestCase):
    def test_evento_valido(self):
        evento, motivo = normalizar_evento(fila())
        self.assertIsNone(motivo)
        self.assertEqual(evento["event_time"], 1569888000)
        self.assertEqual(evento["product_id"], 44600062)
        self.assertEqual(evento["user_id"], 541312140)
        self.assertEqual(evento["price"], 35.79)
        self.assertEqual(evento["brand"], "shiseido")
        self.assertEqual(evento["category_code"], "desconocido")

    def test_no_muta_la_entrada(self):
        original = fila()
        normalizar_evento(original)
        self.assertEqual(original, fila())

    def test_motivos_de_descarte(self):
        casos = {
            "falta_user_session": fila(user_session="  "),
            "falta_event_time": fila(event_time=None),
            "event_time_invalido": fila(event_time="fecha-mala"),
            "event_type_invalido": fila(event_type="click"),
            "product_id_invalido": fila(product_id="abc"),
            "user_id_invalido": fila(user_id="1.5"),
            "price_invalido": fila(price="-1"),
            "falta_price": fila(price=""),
        }
        for motivo, evento in casos.items():
            with self.subTest(motivo=motivo):
                self.assertEqual(normalizar_evento(evento), (None, motivo))

    def test_formatos_de_tiempo(self):
        for valor in ("2019-10-01T00:00:00", "1569888000", 1569888000, 1569888000.0):
            with self.subTest(valor=valor):
                evento, _ = normalizar_evento(fila(event_time=valor))
                self.assertEqual(evento["event_time"], 1569888000)

    def test_otros_tipos_de_evento(self):
        @dataclass
        class EventoDC:
            event_time: object
            event_type: str
            product_id: object
            category_code: object
            brand: object
            price: object
            user_id: object
            user_session: str

        EventoNT = namedtuple("EventoNT", list(fila()))
        for tipo in (EventoDC, EventoNT):
            with self.subTest(tipo=tipo.__name__):
                original = tipo(**fila())
                evento, motivo = normalizar_evento(original)
                self.assertIsNone(motivo)
                self.assertIsInstance(evento, tipo)
                self.assertEqual(evento.event_time, 1569888000)
                self.assertEqual(original.event_time, "2019-10-01 00:00:00 UTC")


class TestDeduplicacion(unittest.TestCase):
    def _normalizados(self, filas):
        return [normalizar_evento(f)[0] for f in filas]

    def test_exacto_conserva_el_primero(self):
        eventos = self._normalizados([
            fila(orden=0), fila(orden=1), fila(product_id="2", orden=2), fila(orden=3),
        ])
        ordenados = merge_sort(eventos, clave_evento)
        conservados, eliminados = deduplicar_exacto(ordenados)
        self.assertEqual(sorted(e["orden"] for e in conservados), [0, 2])
        self.assertEqual(sorted(e["orden"] for e in eliminados), [1, 3])

    def test_ventana(self):
        eventos = self._normalizados([
            fila(event_time="2019-10-01 00:00:00 UTC"),
            fila(event_time="2019-10-01 00:00:03 UTC"),
            fila(event_time="2019-10-01 00:00:03 UTC", product_id="2"),
        ])
        ordenados = merge_sort(eventos, clave_evento)
        conservados, eliminados = deduplicar_ventana(ordenados, ventana_seg=5)
        self.assertEqual((len(conservados), len(eliminados)), (2, 1))
        conservados, eliminados = deduplicar_ventana(ordenados, ventana_seg=2)
        self.assertEqual((len(conservados), len(eliminados)), (3, 0))


class TestProcesarLote(unittest.TestCase):
    def test_lote_sintetico(self):
        lote = generar_eventos(5_000, semilla=11)
        resultado = procesar_lote(lote)
        m = resultado.metricas()
        self.assertEqual(m["recibidos"], m["entregados"] + m["descartados"] + m["duplicados"])
        self.assertGreater(m["duplicados"], 0)
        self.assertGreater(m["descartados"], 0)
        claves = [clave_evento(e) for e in resultado.eventos]
        self.assertEqual(claves, sorted(claves))
        self.assertEqual(len(claves), len(set(claves)))
        evaluacion = evaluar_deduplicacion(resultado)
        self.assertEqual(evaluacion["precision"], 1.0)
        self.assertEqual(evaluacion["recall"], 1.0)

    def test_mismo_resultado_con_otros_algoritmos(self):
        lote = generar_eventos(1_000, semilla=12)
        base = [clave_evento(e) for e in procesar_lote(lote).eventos]
        for ordenar in (quicksort, insercion, lambda d, c: sorted(d, key=c)):
            self.assertEqual([clave_evento(e) for e in procesar_lote(lote, ordenar=ordenar).eventos], base)

    def test_lote_vacio(self):
        resultado = procesar_lote([])
        self.assertEqual((resultado.eventos, resultado.duplicados, resultado.recibidos), ([], [], 0))

    def test_ventana_con_copias_desplazadas(self):
        lote = generar_eventos(3_000, semilla=13, jitter_seg=3, prop_invalidos=0)
        exacto = evaluar_deduplicacion(procesar_lote(lote))
        ventana = evaluar_deduplicacion(procesar_lote(lote, ventana_seg=3))
        self.assertLess(exacto["recall"], 0.2)
        self.assertGreater(ventana["recall"], 0.95)

    def test_consultas_binarias(self):
        resultado = procesar_lote(generar_eventos(2_000, semilla=14))
        eventos = resultado.eventos
        t0, t1 = eventos[100]["event_time"], eventos[500]["event_time"]
        esperados = [e for e in eventos if t0 <= e["event_time"] <= t1]
        self.assertEqual(eventos_en_rango(eventos, t0, t1), esperados)
        self.assertTrue(contiene_evento(eventos, eventos[777]))
        falso, _ = normalizar_evento(fila(product_id="1"))
        self.assertFalse(contiene_evento(eventos, falso))


class TestIntegracionEtapas0y1(unittest.TestCase):
    def test_ningun_evento_se_pierde(self):
        n = 20_000
        etapa0 = Etapa0Ingesta(capacidad=4_000, tam_lote=1_000)
        etapa1 = Etapa1Preprocesamiento()
        for lote in etapa0.procesar_stream(generar_eventos(n, semilla=15)):
            etapa1.procesar(lote)
        m = etapa1.metricas()
        self.assertEqual(m["lotes"], 20)
        self.assertEqual(m["recibidos"], n)
        self.assertEqual(m["entregados"] + m["descartados"] + m["duplicados"], n)
        self.assertEqual(m["precision_dedup"], 1.0)
        # Las copias que caen en otro lote se escapan: es el límite documentado.
        self.assertGreater(m["recall_dedup"], 0.9)

    def test_sin_lotes_y_sin_etiqueta(self):
        m = Etapa1Preprocesamiento().metricas()
        self.assertEqual((m["recibidos"], m["t_validar"], m["precision_dedup"]), (0, 0, None))
        etapa1 = Etapa1Preprocesamiento()
        etapa1.procesar([fila(), fila()])  # datos reales: no traen es_duplicado
        m = etapa1.metricas()
        self.assertEqual(m["duplicados"], 1)
        self.assertIsNone(m["precision_dedup"])
        self.assertIsNone(m["recall_dedup"])


if __name__ == "__main__":
    unittest.main()
