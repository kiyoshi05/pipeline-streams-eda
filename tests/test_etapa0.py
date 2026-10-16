import csv
import os
import random
import tempfile
import unittest
from collections import deque

from src.etapa0_ingesta import BufferCircular, ColaFIFO, ColaVaciaError, Etapa0Ingesta, leer_csv


class _PruebasCola:
    """Pruebas comunes a las dos colas. Cada subclase define ``nueva``."""

    def nueva(self, capacidad=None):
        raise NotImplementedError

    def test_vacia(self):
        cola = self.nueva(10)
        self.assertTrue(cola.esta_vacia())
        self.assertEqual(len(cola), 0)
        with self.assertRaises(ColaVaciaError):
            cola.desencolar()
        with self.assertRaises(ColaVaciaError):
            cola.frente()

    def test_orden_fifo(self):
        cola = self.nueva(1000)
        for i in range(1000):
            self.assertTrue(cola.encolar(i))
        self.assertEqual(cola.frente(), 0)
        self.assertEqual([cola.desencolar() for _ in range(1000)], list(range(1000)))
        self.assertTrue(cola.esta_vacia())

    def test_vaciar_y_reutilizar(self):
        cola = self.nueva(10)
        cola.encolar("a")
        cola.encolar("b")
        cola.desencolar()
        cola.desencolar()
        cola.encolar("c")
        self.assertEqual(cola.frente(), "c")
        self.assertEqual(cola.desencolar(), "c")
        self.assertEqual(len(cola), 0)

    def test_capacidad(self):
        cola = self.nueva(3)
        self.assertTrue(all(cola.encolar(i) for i in range(3)))
        self.assertTrue(cola.esta_llena())
        self.assertFalse(cola.encolar(99))
        self.assertEqual(len(cola), 3)
        self.assertEqual(list(cola), [0, 1, 2])

    def test_lotes(self):
        cola = self.nueva(20)
        for i in range(10):
            cola.encolar(i)
        self.assertEqual(cola.desencolar_lote(4), [0, 1, 2, 3])
        self.assertEqual(cola.desencolar_lote(4), [4, 5, 6, 7])
        self.assertEqual(cola.desencolar_lote(4), [8, 9])
        self.assertEqual(cola.desencolar_lote(4), [])
        cola.encolar("x")  # tras vaciar con lote la cola sigue funcionando
        self.assertEqual(cola.desencolar_lote(0), [])
        self.assertEqual(cola.desencolar(), "x")
        with self.assertRaises(ValueError):
            cola.desencolar_lote(-1)

    def test_iterar_no_consume(self):
        cola = self.nueva(5)
        for i in range(5):
            cola.encolar(i)
        self.assertEqual(list(cola), [0, 1, 2, 3, 4])
        self.assertEqual(len(cola), 5)

    def test_contra_deque(self):
        azar = random.Random(7)
        capacidad = 50
        cola = self.nueva(capacidad)
        oraculo = deque()
        for paso in range(20_000):
            op = azar.random()
            if op < 0.5:
                esperado = len(oraculo) < capacidad
                if esperado:
                    oraculo.append(paso)
                self.assertEqual(cola.encolar(paso), esperado)
            elif op < 0.8:
                if oraculo:
                    self.assertEqual(cola.desencolar(), oraculo.popleft())
                else:
                    with self.assertRaises(ColaVaciaError):
                        cola.desencolar()
            else:
                k = azar.randrange(6)
                esperado = [oraculo.popleft() for _ in range(min(k, len(oraculo)))]
                self.assertEqual(cola.desencolar_lote(k), esperado)
            self.assertEqual(len(cola), len(oraculo))
            self.assertEqual(list(cola), list(oraculo))


class TestColaFIFO(_PruebasCola, unittest.TestCase):
    def nueva(self, capacidad=None):
        return ColaFIFO(capacidad)

    def test_sin_capacidad(self):
        cola = ColaFIFO()
        for i in range(10_000):
            self.assertTrue(cola.encolar(i))
        self.assertFalse(cola.esta_llena())

    def test_capacidad_invalida(self):
        with self.assertRaises(ValueError):
            ColaFIFO(0)


class TestBufferCircular(_PruebasCola, unittest.TestCase):
    def nueva(self, capacidad=None):
        return BufferCircular(capacidad or 10_000)

    def test_vuelta_del_indice(self):
        buf = BufferCircular(4)
        for i in range(4):
            buf.encolar(i)
        buf.desencolar()
        buf.desencolar()
        buf.encolar(4)
        buf.encolar(5)
        self.assertEqual(list(buf), [2, 3, 4, 5])
        self.assertEqual(buf.desencolar_lote(10), [2, 3, 4, 5])

    def test_capacidad_obligatoria(self):
        with self.assertRaises(ValueError):
            BufferCircular(None)
        with self.assertRaises(ValueError):
            BufferCircular(0)


class TestEtapa0Ingesta(unittest.TestCase):
    def test_lotes_y_orden(self):
        for estructura in ("lista", "circular"):
            etapa = Etapa0Ingesta(capacidad=5_000, tam_lote=1_000, estructura=estructura)
            lotes = list(etapa.procesar_stream(range(2_500)))
            self.assertEqual([len(l) for l in lotes], [1_000, 1_000, 500])
            self.assertEqual([x for l in lotes for x in l], list(range(2_500)))
            self.assertEqual(etapa.metricas(), {
                "recibidos": 2_500, "entregados": 2_500, "lotes": 3,
                "en_buffer": 0, "contrapresion": 0,
            })

    def test_stream_vacio(self):
        self.assertEqual(list(Etapa0Ingesta(10, 5).procesar_stream([])), [])

    def test_contrapresion_con_buffer_lleno(self):
        etapa = Etapa0Ingesta(capacidad=5, tam_lote=2)
        for i in range(5):
            self.assertTrue(etapa.recibir(i))
        self.assertFalse(etapa.recibir(99))
        lotes = list(etapa.procesar_stream([5, 6]))
        self.assertEqual([x for l in lotes for x in l], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(etapa.contrapresion, 1)
        self.assertEqual(etapa.recibidos, 7)

    def test_sin_capacidad_maxima(self):
        etapa = Etapa0Ingesta(capacidad=None, tam_lote=10)
        self.assertEqual([len(l) for l in etapa.procesar_stream(range(25))], [10, 10, 5])
        with self.assertRaises(ValueError):
            Etapa0Ingesta(capacidad=None, tam_lote=10, estructura="circular")

    def test_configuracion_invalida(self):
        with self.assertRaises(ValueError):
            Etapa0Ingesta(capacidad=10, tam_lote=20)
        with self.assertRaises(ValueError):
            Etapa0Ingesta(capacidad=10, tam_lote=0)
        with self.assertRaises(ValueError):
            Etapa0Ingesta(estructura="pila")


class TestLeerCsv(unittest.TestCase):
    CABECERA = ["event_time", "event_type", "product_id", "category_id", "category_code",
                "brand", "price", "user_id", "user_session"]

    def _csv(self, filas, cabecera=None):
        fd, ruta = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.remove, ruta)
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(cabecera or self.CABECERA)
            escritor.writerows(filas)
        return ruta

    def test_lee_solo_campos_del_contrato(self):
        fila = ["2019-10-01 00:00:00 UTC", "view", "44600062", "2103807459595387724", "",
                "shiseido", "35.79", "541312140", "72d76fde-8bb3-4e00-8c23-a032dfed738c"]
        ruta = self._csv([fila] * 5)
        eventos = list(leer_csv(ruta, limite=3))
        self.assertEqual(len(eventos), 3)
        self.assertNotIn("category_id", eventos[0])
        self.assertEqual(eventos[0]["brand"], "shiseido")

    def test_a_evento(self):
        ruta = self._csv([["2019-10-01 00:00:00 UTC", "view", "1", "2", "", "", "1.0", "3", "s"]])
        eventos = list(leer_csv(ruta, a_evento=lambda d: tuple(sorted(d))))
        self.assertIsInstance(eventos[0], tuple)

    def test_columna_faltante(self):
        ruta = self._csv([["x"]], cabecera=["event_time"])
        with self.assertRaises(ValueError):
            list(leer_csv(ruta))


if __name__ == "__main__":
    unittest.main()
