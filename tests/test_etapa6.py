import math
import random
import unittest
from collections import Counter

from src.etapa6_probabilistico import CountMinSketch, Etapa6Fraude, FiltroBloom
from experimentos.datos_sinteticos import generar_eventos_fraude


class PruebasFiltroBloom(unittest.TestCase):

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            FiltroBloom(n_esperado=0)
        with self.assertRaises(ValueError):
            FiltroBloom(prob_fp=0)
        with self.assertRaises(ValueError):
            FiltroBloom(prob_fp=1)

    def test_sin_falsos_negativos(self):
        # Garantía dura del filtro: lo que se agregó siempre da "contiene".
        b = FiltroBloom(n_esperado=5_000, prob_fp=0.01)
        agregados = [f"ip:10.0.{i // 256}.{i % 256}" for i in range(5_000)]
        b.actualizar(agregados)
        self.assertTrue(all(x in b for x in agregados))
        self.assertEqual(len(b), 5_000)

    def test_falsos_positivos_dentro_de_la_cota(self):
        b = FiltroBloom(n_esperado=10_000, prob_fp=0.01)
        b.actualizar(f"x{i}" for i in range(10_000))
        ausentes = [f"y{i}" for i in range(50_000)]      # ninguno fue agregado
        fp = sum(1 for x in ausentes if x in b) / len(ausentes)
        # La tasa real no debe superar por mucho la objetivo (holgura 2.5x).
        self.assertLess(fp, 0.025)

    def test_mas_liviano_que_un_set(self):
        n = 50_000
        b = FiltroBloom(n_esperado=n, prob_fp=0.01)
        b.actualizar(f"disp-{i:08x}" for i in range(n))
        # Con p=0.01 el filtro usa ~1.2 bytes por clave: mucho menos que un set.
        self.assertLess(b.memoria_bytes, 2 * n)

    def test_superconjunto_de_un_set(self):
        # El Bloom nunca dice "no" cuando el set dice "sí".
        azar = random.Random(42)
        b, ref = FiltroBloom(n_esperado=4_000, prob_fp=0.01), set()
        universo = [f"k{azar.randrange(8_000)}" for _ in range(4_000)]
        for k in universo:
            b.agregar(k)
            ref.add(k)
        for k in ref:
            self.assertIn(k, b)
        for _ in range(4_000):
            k = f"k{azar.randrange(8_000)}"
            if k in ref:
                self.assertIn(k, b)   # si está en el set, obligatoriamente en el Bloom


class PruebasCountMinSketch(unittest.TestCase):

    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            CountMinSketch(ancho=0, profundidad=1)
        with self.assertRaises(ValueError):
            CountMinSketch(ancho=1, profundidad=0)
        with self.assertRaises(ValueError):
            CountMinSketch().sumar("x", -1)

    def test_nunca_subestima(self):
        # Garantía dura: la estimación es siempre >= la cuenta real.
        cm = CountMinSketch(epsilon=0.001, delta=0.01, semilla=1)
        exact = Counter()
        azar = random.Random(0)
        for _ in range(50_000):
            k = f"k{azar.randrange(500)}"
            cm.sumar(k)
            exact[k] += 1
        self.assertTrue(all(cm.estimar(k) >= v for k, v in exact.items()))

    def test_error_acotado(self):
        cm = CountMinSketch(epsilon=0.001, delta=0.01, semilla=1)
        exact = Counter()
        azar = random.Random(2)
        for _ in range(100_000):
            k = f"k{azar.randrange(1_000)}"
            cm.sumar(k)
            exact[k] += 1
        cota = cm.error_absoluto_garantizado           # epsilon * total
        dentro = sum(1 for k, v in exact.items() if cm.estimar(k) - v <= cota)
        # Al menos (1 - delta) de las claves deben respetar la cota de error.
        self.assertGreaterEqual(dentro / len(exact), 1 - cm.delta)

    def test_exacto_sin_colisiones(self):
        # Con un ancho holgado y pocas claves, el mínimo coincide con la cuenta real.
        cm = CountMinSketch(ancho=20_000, profundidad=5, semilla=3)
        exact = Counter()
        azar = random.Random(4)
        for _ in range(10_000):
            k = f"k{azar.randrange(100)}"
            cm.sumar(k)
            exact[k] += 1
        for k, v in exact.items():
            self.assertEqual(cm.estimar(k), v)

    def test_clave_nueva_da_cero_o_mas(self):
        cm = CountMinSketch()
        self.assertGreaterEqual(cm.estimar("nunca-vista"), 0)


def ev(t, ip, disp, es_fraude=False, tipo="purchase"):
    return {
        "event_time": t, "event_type": tipo, "product_id": 1, "user_id": 7,
        "user_session": "s7", "price": 10.0, "brand": "acme", "category_code": "x",
        "ip": ip, "dispositivo_id": disp, "medio_pago": "tarjeta", "es_fraude": es_fraude,
    }


class PruebasEtapa6Fraude(unittest.TestCase):

    def test_lista_negra_marca_evento_suelto(self):
        e6 = Etapa6Fraude(lista_negra=["ip:1.2.3.4"], umbral_velocidad=100)
        salida = e6.procesar([ev(1000, "1.2.3.4", "d1", es_fraude=True)])
        self.assertTrue(salida[0]["fraude_predicho"])
        self.assertIn("lista_negra", salida[0]["fraude_motivos"])

    def test_evento_normal_no_se_marca(self):
        e6 = Etapa6Fraude(lista_negra=[], umbral_velocidad=8)
        salida = e6.procesar([ev(1000, "9.9.9.9", "dok")])
        self.assertFalse(salida[0]["fraude_predicho"])

    def test_velocidad_marca_tras_el_umbral(self):
        e6 = Etapa6Fraude(lista_negra=[], ventana_seg=10, umbral_velocidad=5)
        lote = [ev(1000, "5.5.5.5", "dr", es_fraude=True) for _ in range(5)]
        salida = e6.procesar(lote)
        # Los primeros 4 aún no cruzan el umbral; a partir del 5.º sí.
        self.assertFalse(salida[0]["fraude_predicho"])
        self.assertTrue(salida[-1]["fraude_predicho"])
        self.assertIn("velocidad", salida[-1]["fraude_motivos"])

    def test_sospechoso_queda_fichado(self):
        # Tras disparar velocidad, el siguiente evento del actor se marca al instante.
        e6 = Etapa6Fraude(lista_negra=[], ventana_seg=10, umbral_velocidad=3)
        e6.procesar([ev(1000, "7.7.7.7", "df", es_fraude=True) for _ in range(3)])
        # En una ventana muy posterior la velocidad se reinicia, pero el actor
        # ya está fichado: su único evento se marca igual.
        despues = e6.procesar([ev(5000, "7.7.7.7", "df", es_fraude=True)])
        self.assertTrue(despues[0]["fraude_predicho"])
        self.assertIn("sospechoso_previo", despues[0]["fraude_motivos"])

    def test_ventana_reinicia_el_conteo(self):
        # Pocos eventos por ventana no deben acumularse entre ventanas lejanas.
        e6 = Etapa6Fraude(lista_negra=[], ventana_seg=10, umbral_velocidad=5)
        salida = []
        for w in range(10):
            salida += e6.procesar([ev(1000 + w * 100, "8.8.8.8", "dv") for _ in range(2)])
        self.assertFalse(any(s["fraude_predicho"] for s in salida))

    def test_sin_etiqueta_no_calcula_metricas(self):
        e6 = Etapa6Fraude(lista_negra=[])
        e6.procesar([{"event_time": 1, "event_type": "view", "product_id": 1,
                      "user_id": 1, "user_session": "s", "price": 1.0,
                      "ip": "1.1.1.1", "dispositivo_id": "d"}])
        m = e6.metricas()
        self.assertFalse(m["con_etiqueta"])
        self.assertIsNone(m["precision"])
        self.assertIsNone(m["recall"])

    def test_calidad_sobre_datos_sinteticos(self):
        eventos, lista_negra = generar_eventos_fraude(20_000, semilla=42)
        e6 = Etapa6Fraude(lista_negra=lista_negra, ventana_seg=10, umbral_velocidad=8)
        e6.procesar(eventos)
        m = e6.metricas()
        self.assertTrue(m["con_etiqueta"])
        self.assertEqual(m["fp"], 0)            # sin falsas alarmas sobre este generador
        self.assertEqual(m["precision"], 1.0)
        self.assertGreater(m["recall"], 0.9)    # casi todo el fraude detectado

    def test_no_muta_la_entrada(self):
        original = ev(1000, "1.2.3.4", "d1")
        e6 = Etapa6Fraude(lista_negra=["ip:1.2.3.4"])
        e6.procesar([original])
        self.assertNotIn("fraude_predicho", original)


if __name__ == "__main__":
    unittest.main()
