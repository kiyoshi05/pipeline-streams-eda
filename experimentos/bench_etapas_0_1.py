"""Benchmarks de las etapas 0 y 1.

Uso (desde la raíz del proyecto):
    python -m experimentos.bench_etapas_0_1 --rapido
    python -m experimentos.bench_etapas_0_1
    python -m experimentos.bench_etapas_0_1 --tamanos 1000 10000 100000 1000000 10000000

Escribe un CSV por experimento en experimentos/resultados/ con promedio,
desviación estándar, mínimo, memoria pico, repeticiones, semilla y plataforma.

Repeticiones: se usan las pedidas (100 por defecto) hasta 100K; menos en 1M y
10M, y menos en las variantes cuadráticas. El CSV registra las que se usaron
de verdad. Que 10M lleve menos repeticiones está pendiente de confirmar con
el profesor.

La función ``medir`` es local. Cuando el grupo tenga src/comun/medicion.py,
conviene reemplazarla por la común para que los tres midan igual.
"""

import argparse
import bisect
import csv
import gc
import os
import platform
import random
import statistics
import sys
import tracemalloc
from collections import deque
from time import perf_counter

from experimentos.datos_sinteticos import generar_claves, iterar_eventos
from src.etapa0_ingesta import BufferCircular, ColaFIFO, Etapa0Ingesta
from src.etapa1_preprocesamiento import (
    Etapa1Preprocesamiento,
    busqueda_lineal,
    contiene,
    deduplicar_exacto,
    insercion,
    merge_sort,
    quicksort,
)

CARPETA_RESULTADOS = os.path.join(os.path.dirname(__file__), "resultados")
COLUMNAS = ["experimento", "variante", "n", "repeticiones", "prom_s", "desv_s", "min_s",
            "mem_pico_bytes", "mem_final_bytes", "extra", "semilla", "plataforma"]
EXPERIMENTOS = ("cola", "stream", "ordenacion", "deduplicacion", "busqueda", "pipeline")
# Variantes cuadráticas (o lineales por consulta): se cortan en este n y usan menos repeticiones.
MAX_N_INSERCION_ALEATORIO = 10_000
MAX_N_LIST_POP0 = 100_000
MAX_N_BUSQUEDA_LINEAL = 100_000
ELEMENTO = object()  # se encola siempre el mismo objeto: la memoria medida es solo la de la estructura


def energia():
    """'corriente', 'bateria' o 'desconocida'. En batería Windows baja la frecuencia
    del procesador y los tiempos no son comparables con una corrida enchufada."""
    if sys.platform != "win32":
        return "desconocida"
    import ctypes

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

    estado = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(estado)):
        return "desconocida"
    return {0: "bateria", 1: "corriente"}.get(estado.ACLineStatus, "desconocida")


def sin_modo_eficiencia():
    """En Windows 11, pide que este proceso no quede en modo de eficiencia (EcoQoS)
    cuando la terminal no está en primer plano; solo afecta a este proceso."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    estado = PROCESS_POWER_THROTTLING_STATE(1, 0x1, 0x0)  # controlar EXECUTION_SPEED y apagarlo
    try:
        kernel32.SetProcessInformation(kernel32.GetCurrentProcess(), 4,  # 4 = ProcessPowerThrottling
                                       ctypes.byref(estado), ctypes.sizeof(estado))
    except (OSError, ctypes.ArgumentError):
        pass  # versiones de Windows sin esta opción: se mide igual


def plataforma():
    return (f"{platform.system()} {platform.release()} | {platform.processor() or platform.machine()} | "
            f"{os.cpu_count()} CPU | Python {platform.python_version()} | energia: {energia()}")


def medir(funcion, entrada, repeticiones):
    """Tiempo (sin tracemalloc, con el GC apagado como timeit) y luego memoria
    en una corrida aparte con tracemalloc, que ralentiza y distorsionaría el tiempo.
    La entrada se crea antes de iniciar tracemalloc, así no se cuenta."""
    tiempos = []
    for _ in range(repeticiones):
        gc_activo = gc.isenabled()
        gc.disable()
        try:
            inicio = perf_counter()
            funcion(entrada)
            tiempos.append(perf_counter() - inicio)
        finally:
            if gc_activo:
                gc.enable()
    gc.collect()
    tracemalloc.start()
    try:
        resultado = funcion(entrada)
        actual, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    del resultado
    return {
        "prom_s": statistics.mean(tiempos),
        "desv_s": statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0,
        "min_s": min(tiempos),
        "mem_pico_bytes": pico,
        "mem_final_bytes": actual,
    }


# --- Etapa 0 -----------------------------------------------------------------

def cola_lista_enlazada(n):
    cola = ColaFIFO()
    for _ in range(n):
        cola.encolar(ELEMENTO)
    for _ in range(n):
        cola.desencolar()


def cola_buffer_circular(n):
    cola = BufferCircular(n)
    for _ in range(n):
        cola.encolar(ELEMENTO)
    for _ in range(n):
        cola.desencolar()


def cola_deque(n):
    cola = deque()
    for _ in range(n):
        cola.append(ELEMENTO)
    for _ in range(n):
        cola.popleft()


def cola_list_pop0(n):
    cola = []
    for _ in range(n):
        cola.append(ELEMENTO)
    for _ in range(n):
        cola.pop(0)


def stream_etapa0(estructura):
    def correr(n):
        etapa = Etapa0Ingesta(capacidad=10_000, tam_lote=1_000, estructura=estructura)
        for _ in etapa.procesar_stream(ELEMENTO for _ in range(n)):
            pass
    return correr


# --- Etapa 1 -----------------------------------------------------------------

def _identidad(x):
    return x


def dedup_merge_sort(claves):
    return deduplicar_exacto(merge_sort(claves), clave=_identidad)


def dedup_sorted(claves):
    return deduplicar_exacto(sorted(claves), clave=_identidad)


def dedup_hash(claves):
    """Alternativa con conjunto: O(n) esperado, más memoria y no deja orden."""
    vistos = set()
    conservados, eliminados = [], []
    for clave in claves:
        if clave in vistos:
            eliminados.append(clave)
        else:
            vistos.add(clave)
            conservados.append(clave)
    return conservados, eliminados


def consultas_para(ordenadas, cantidad, semilla):
    azar = random.Random(semilla)
    existentes = [ordenadas[azar.randrange(len(ordenadas))] for _ in range(cantidad // 2)]
    ausentes = [(0, "x", 0, "view", 0, 0.0)] * (cantidad - len(existentes))
    return existentes + ausentes


def buscar_con(funcion):
    def correr(entrada):
        ordenadas, consultas = entrada
        for x in consultas:
            funcion(ordenadas, x)
    return correr


def buscar_bisect(ordenadas, x):
    i = bisect.bisect_left(ordenadas, x)
    return i < len(ordenadas) and ordenadas[i] == x


# --- Ejecución ---------------------------------------------------------------

class Banco:
    def __init__(self, args):
        self.args = args
        self.filas = {}

    def repeticiones(self, n, lenta=False, base=None):
        a = self.args
        reps = base if base is not None else (
            a.repeticiones if n <= 100_000 else a.reps_1m if n <= 1_000_000 else a.reps_10m)
        if lenta:
            reps = min(reps, a.reps_cuadratico)
        return max(1, reps)

    def registrar(self, experimento, variante, n, reps, medida, extra=""):
        fila = {"experimento": experimento, "variante": variante, "n": n, "repeticiones": reps,
                **medida, "extra": extra, "semilla": self.args.semilla, "plataforma": plataforma()}
        self.filas.setdefault(experimento, []).append(fila)
        pico = medida["mem_pico_bytes"]
        texto_pico = f"pico={pico / 1e6:,.1f} MB" if pico != "" else "pico=n/a"
        print(f"  {experimento:<14} {variante:<20} n={n:>10,}  reps={reps:<4} "
              f"prom={medida['prom_s']:.6f}s  desv={medida['desv_s']:.6f}s  "
              f"{texto_pico}  {extra}", flush=True)

    def correr(self, experimento, variante, funcion, entrada, n, extra="", max_n=None):
        """``max_n`` marca una variante lenta: se omite por encima de ese n y
        usa como máximo --reps-cuadratico repeticiones."""
        if max_n is not None and n > max_n:
            return None
        reps = self.repeticiones(n, lenta=max_n is not None)
        medida = medir(funcion, entrada, reps)
        self.registrar(experimento, variante, n, reps, medida, extra)
        return medida

    def guardar(self):
        os.makedirs(self.args.salida, exist_ok=True)
        for experimento, filas in self.filas.items():
            ruta = os.path.join(self.args.salida, f"etapas01_{experimento}.csv")
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
                escritor.writeheader()
                escritor.writerows(filas)
            print(f"guardado {ruta}")


def experimento_cola(banco, n):
    for variante, funcion, max_n in (("lista_enlazada", cola_lista_enlazada, None),
                                     ("buffer_circular", cola_buffer_circular, None),
                                     ("deque", cola_deque, None),
                                     ("list_pop0", cola_list_pop0, MAX_N_LIST_POP0)):
        banco.correr("cola", variante, funcion, n, n, extra=f"operaciones={2 * n}", max_n=max_n)


def experimento_stream(banco, n):
    for variante in ("lista", "circular"):
        banco.correr("stream", variante, stream_etapa0(variante), n, n,
                     extra="capacidad=10000;tam_lote=1000")


def experimento_ordenacion(banco, n, claves):
    """Dos entradas: el stream tal como llega (casi ordenado por tiempo) y la
    misma lista mezclada al azar, que es donde se ve el O(n^2) de inserción."""
    mezcladas = claves[:]
    random.Random(banco.args.semilla).shuffle(mezcladas)
    for orden, entrada in (("casi_ordenado", claves), ("aleatorio", mezcladas)):
        for algoritmo, funcion in (("merge_sort", merge_sort),
                                   ("quicksort", lambda d: quicksort(d, semilla=banco.args.semilla)),
                                   ("sorted_timsort", sorted),
                                   ("insercion", insercion)):
            lenta = algoritmo == "insercion" and orden == "aleatorio"
            banco.correr("ordenacion", f"{algoritmo}_{orden}", funcion, entrada, n,
                         max_n=MAX_N_INSERCION_ALEATORIO if lenta else None)


def experimento_deduplicacion(banco, n, claves):
    for variante, funcion in (("merge_sort_y_vecinos", dedup_merge_sort),
                              ("sorted_y_vecinos", dedup_sorted),
                              ("hash_set", dedup_hash)):
        eliminados = len(funcion(claves)[1])
        banco.correr("deduplicacion", variante, funcion, claves, n, extra=f"eliminados={eliminados}")


def experimento_busqueda(banco, n, claves):
    ordenadas = sorted(claves)
    consultas = consultas_para(ordenadas, banco.args.consultas, banco.args.semilla)
    entrada = (ordenadas, consultas)
    extra = f"consultas={len(consultas)}"
    for variante, funcion, max_n in (("binaria_propia", contiene, None),
                                     ("bisect_python", buscar_bisect, None),
                                     ("busqueda_lineal", busqueda_lineal, MAX_N_BUSQUEDA_LINEAL)):
        banco.correr("busqueda", variante, buscar_con(funcion), entrada, n, extra=extra, max_n=max_n)


def experimento_pipeline(banco, n):
    """Etapa 0 -> etapa 1 por lotes, como en el pipeline. La generación de
    eventos va dentro del tiempo total; el tiempo propio de la etapa 1 sale de
    las mediciones internas de procesar_lote y va en ``extra``."""
    a = banco.args
    reps = banco.repeticiones(n, base=a.reps_pipeline)
    tiempos, internos, ultima = [], [], None
    for r in range(reps):
        inicio = perf_counter()
        etapa0 = Etapa0Ingesta(capacidad=max(a.tam_lote, 10_000), tam_lote=a.tam_lote)
        etapa1 = Etapa1Preprocesamiento()
        for lote in etapa0.procesar_stream(iterar_eventos(n, semilla=a.semilla + r)):
            etapa1.procesar(lote)
        tiempos.append(perf_counter() - inicio)
        m = etapa1.metricas()
        internos.append(m["t_validar"] + m["t_ordenar"] + m["t_deduplicar"])
        ultima = m
    medida = {
        "prom_s": statistics.mean(tiempos),
        "desv_s": statistics.stdev(tiempos) if reps > 1 else 0.0,
        "min_s": min(tiempos),
        "mem_pico_bytes": "",  # no se mide aquí: incluiría al generador de eventos
        "mem_final_bytes": "",
    }
    etapa1_s = statistics.mean(internos)
    extra = (f"tam_lote={a.tam_lote};etapa1_s={etapa1_s:.6f};eventos_por_s_etapa1={n / etapa1_s:,.0f};"
             f"descartados={ultima['descartados']};duplicados={ultima['duplicados']};"
             f"precision={ultima['precision_dedup']};recall={ultima['recall_dedup']}")
    banco.registrar("pipeline", f"lotes_{a.tam_lote}", n, reps, medida, extra)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tamanos", type=int, nargs="+", default=[1_000, 10_000, 100_000])
    p.add_argument("--repeticiones", type=int, default=100, help="hasta 100K elementos")
    p.add_argument("--reps-1m", type=int, default=10)
    p.add_argument("--reps-10m", type=int, default=3)
    p.add_argument("--reps-cuadratico", type=int, default=10)
    p.add_argument("--reps-pipeline", type=int, default=3)
    p.add_argument("--consultas", type=int, default=100)
    p.add_argument("--tam-lote", type=int, default=1_000)
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--experimentos", nargs="+", choices=EXPERIMENTOS, default=list(EXPERIMENTOS))
    p.add_argument("--salida", default=CARPETA_RESULTADOS)
    p.add_argument("--rapido", action="store_true", help="prueba de humo: 1K y 10K con 3 repeticiones")
    args = p.parse_args(argv)
    if args.rapido:
        args.tamanos = [1_000, 10_000]
        args.repeticiones = args.reps_cuadratico = args.reps_pipeline = 3

    sin_modo_eficiencia()
    print(plataforma())
    if energia() == "bateria":
        print("AVISO: la laptop está en batería; para el informe corre esto enchufado.")
    banco = Banco(args)
    for n in sorted(args.tamanos):
        print(f"\n== n = {n:,} ==", flush=True)
        if "cola" in args.experimentos:
            experimento_cola(banco, n)
        if "stream" in args.experimentos:
            experimento_stream(banco, n)
        if {"ordenacion", "deduplicacion", "busqueda"} & set(args.experimentos):
            claves = generar_claves(n, semilla=args.semilla)
            if "ordenacion" in args.experimentos:
                experimento_ordenacion(banco, n, claves)
            if "deduplicacion" in args.experimentos:
                experimento_deduplicacion(banco, n, claves)
            if "busqueda" in args.experimentos:
                experimento_busqueda(banco, n, claves)
            del claves
        if "pipeline" in args.experimentos:
            experimento_pipeline(banco, n)
        banco.guardar()  # después de cada tamaño, para no perder lo medido si una corrida larga se corta


if __name__ == "__main__":
    sys.exit(main())
