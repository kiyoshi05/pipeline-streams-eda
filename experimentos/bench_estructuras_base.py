"""Benchmarks de las estructuras base del integrante B (etapas 2, 3 y 4).

Uso (desde la raíz del proyecto):
    python -m experimentos.bench_estructuras_base --rapido
    python -m experimentos.bench_estructuras_base
    python -m experimentos.bench_estructuras_base --tamanos 1000 10000 100000 1000000 10000000
    python -m experimentos.bench_estructuras_base --experimentos heap hash

Cada experimento compara la estructura propia (la que usa el pipeline) con
alternativas más simples o escritas en C:

    heap               n push + n pop: MinHeap propio, heapq, lista ordenada
    heap_construccion  heapify contra n push
    hash               n inserciones + n búsquedas: TablaHash propia, dict, lista lineal
    lru                n accesos con popularidad Zipf: CacheLRU propia, OrderedDict, lista
    lru_aciertos       tasa de aciertos según la capacidad de la caché (sin tiempos)
    bplus_insercion    n inserciones: B+Tree de orden 16, 64 y 256, lista ordenada
    bplus_rango        100 consultas por rango de 100 claves: B+Tree, bisect, recorrido lineal
    matriz             n interacciones usuario x producto: matriz dispersa propia, dict de pares

Se mide con la misma función que bench_etapas_0_1 (``medir``: GC apagado,
perf_counter, y una corrida aparte con tracemalloc para la memoria), así los
resultados de los tres integrantes son comparables.

Repeticiones: hasta 100 por punto cuando es viable. Para que la corrida
completa termine en un tiempo razonable, cada punto se limita a un
presupuesto de tiempo (--presupuesto segundos, con un mínimo de 3
repeticiones); en 10M se usan --reps-10m. Las variantes cuadráticas se
cortan en un n máximo. El CSV registra las repeticiones usadas de verdad.

Escribe experimentos/resultados/estructuras_base_<experimento>.csv.
"""

import argparse
import bisect
import csv
import heapq
import os
import random
import sys
from collections import OrderedDict
from itertools import accumulate
from time import perf_counter

from experimentos.bench_etapas_0_1 import COLUMNAS, energia, medir, plataforma, sin_modo_eficiencia
from src.etapa2_prioridad.heap import MinHeap
from src.etapa3_lookup import CacheLRU, MatrizDispersa, TablaHash
from src.etapa4_indice import BPlusTree

CARPETA_RESULTADOS = os.path.join(os.path.dirname(__file__), "resultados")
PREFIJO = "estructuras_base_"
EXPERIMENTOS = ("heap", "heap_construccion", "hash", "lru", "lru_aciertos",
                "bplus_insercion", "bplus_rango", "matriz")
COLUMNAS_ACIERTOS = ["experimento", "capacidad_pct", "capacidad", "productos", "accesos",
                     "tasa_aciertos", "expulsiones", "semilla", "plataforma"]

# Variantes cuadráticas: se cortan en este n y usan pocas repeticiones.
MAX_N_LISTA_ORDENADA = 100_000
MAX_N_LISTA_LINEAL = 10_000
MAX_N_LRU_LISTA = 100_000
MAX_N_RANGO_LINEAL = 1_000_000
CONSULTAS_RANGO = 100
LARGO_RANGO = 100


# --- Variantes: etapa 2 (heap) ------------------------------------------------

def heap_propio(datos):
    h = MinHeap()
    push, pop = h.push, h.pop
    for x in datos:
        push(x)
    for _ in range(len(datos)):
        pop()


def heap_heapq(datos):
    h = []
    for x in datos:
        heapq.heappush(h, x)
    for _ in range(len(datos)):
        heapq.heappop(h)


def heap_lista_ordenada(datos):
    # Orden descendente: el mínimo queda al final y sale con pop() en O(1);
    # insertar cuesta O(n) porque desplaza elementos.
    lista = []
    insort = bisect.insort
    for x in datos:
        insort(lista, -x)
    for _ in range(len(datos)):
        lista.pop()


def construir_heapify(datos):
    return MinHeap(datos)


def construir_n_push(datos):
    h = MinHeap()
    for x in datos:
        h.push(x)
    return h


# --- Variantes: etapa 3 (hash, LRU y matriz) ----------------------------------------

def hash_propia(entrada):
    claves, consultas = entrada
    t = TablaHash()
    insertar, obtener = t.insertar, t.obtener
    for k in claves:
        insertar(k, k)
    for k in consultas:
        obtener(k)
    return t


def hash_dict(entrada):
    claves, consultas = entrada
    d = {}
    for k in claves:
        d[k] = k
    for k in consultas:
        d.get(k)
    return d


def hash_lista_lineal(entrada):
    claves, consultas = entrada
    lista = []
    for k in claves:
        lista.append(k)
    for k in consultas:
        k in lista   # búsqueda lineal O(n)


def lru_propia(entrada):
    accesos, capacidad = entrada
    c = CacheLRU(capacidad)
    obtener, poner = c.obtener, c.poner
    for k in accesos:
        if obtener(k) is None:
            poner(k, k)
    return c


def lru_ordereddict(entrada):
    accesos, capacidad = entrada
    od = OrderedDict()
    for k in accesos:
        if k in od:
            od.move_to_end(k)
        else:
            od[k] = k
            if len(od) > capacidad:
                od.popitem(last=False)


def lru_lista(entrada):
    # Lista con "mover al final": buscar y quitar cuestan O(capacidad).
    accesos, capacidad = entrada
    lista = []
    for k in accesos:
        if k in lista:
            lista.remove(k)
        elif len(lista) >= capacidad:
            lista.pop(0)
        lista.append(k)


def matriz_dispersa(interacciones):
    m = MatrizDispersa()
    sumar = m.sumar
    for u, p, w in interacciones:
        sumar(u, p, w)
    return m


def matriz_dict_pares(interacciones):
    # Un solo índice (usuario, producto): menos memoria, pero leer una columna cuesta O(nnz).
    d = {}
    for u, p, w in interacciones:
        d[(u, p)] = d.get((u, p), 0.0) + w
    return d


# --- Variantes: etapa 4 (B+Tree) --------------------------------------------------------

def bplus_con_orden(orden):
    def insertar_todo(claves):
        b = BPlusTree(orden)
        insertar = b.insertar
        for i, k in enumerate(claves):
            insertar(k, i)
        return b
    insertar_todo.__name__ = f"bplus_{orden}"
    return insertar_todo


def lista_ordenada_insercion(claves):
    lista = []
    insort = bisect.insort
    for k in claves:
        insort(lista, k)
    return lista


def rango_bplus(entrada):
    arbol, _, consultas = entrada
    total = 0
    for lo, hi in consultas:
        for _ in arbol.rango(lo, hi):
            total += 1
    return total


def rango_bisect(entrada):
    _, ordenada, consultas = entrada
    total = 0
    for lo, hi in consultas:
        total += len(ordenada[bisect.bisect_left(ordenada, lo):bisect.bisect_right(ordenada, hi)])
    return total


def rango_lineal(entrada):
    _, ordenada, consultas = entrada
    total = 0
    for lo, hi in consultas:
        total += sum(1 for k in ordenada if lo <= k <= hi)
    return total


# --- Datos de entrada -----------------------------------------------------------------------

def enteros(n, semilla):
    azar = random.Random(semilla)
    return [azar.randrange(10 * n) for _ in range(n)]


def datos_hash(n, semilla):
    """Claves como product_id (1.000.000 + id) y n consultas: la mitad existe y la mitad no."""
    azar = random.Random(semilla)
    ids = azar.sample(range(2 * n), 2 * n)
    claves = [1_000_000 + i for i in ids[:n]]
    faltan = [1_000_000 + i for i in ids[n:]]
    consultas = [azar.choice(claves) if azar.random() < 0.5 else azar.choice(faltan) for _ in range(n)]
    return claves, consultas


def datos_lru(n, semilla, capacidad_pct=10):
    """n accesos a productos con popularidad Zipf (pocos productos concentran las vistas)."""
    azar = random.Random(semilla)
    productos = max(100, n // 10)
    pesos = list(accumulate(1.0 / r for r in range(1, productos + 1)))
    ids = azar.sample(range(productos), productos)   # el producto más popular no es el id 0
    rangos = azar.choices(range(productos), cum_weights=pesos, k=n)
    accesos = [1_000_000 + ids[r] for r in rangos]
    capacidad = max(1, productos * capacidad_pct // 100)
    return accesos, capacidad, productos


def datos_matriz(n, semilla):
    azar = random.Random(semilla)
    usuarios, productos = max(10, n // 10), max(100, n // 20)
    pesos = (1.0, 1.0, 1.0, 2.0, 4.0)   # vista, vista, vista, carrito, compra
    return [(500_000_000 + azar.randrange(usuarios), 1_000_000 + azar.randrange(productos), azar.choice(pesos))
            for _ in range(n)], usuarios, productos


def consultas_rango(ordenada, semilla):
    azar = random.Random(semilla)
    consultas = []
    for _ in range(CONSULTAS_RANGO):
        i = azar.randrange(len(ordenada))
        j = min(len(ordenada) - 1, i + LARGO_RANGO - 1)
        consultas.append((ordenada[i], ordenada[j]))
    return consultas


# --- Ejecución -----------------------------------------------------------------------------------

def combinar(ruta, nuevas):
    """Filas del CSV existente más las nuevas; una fila nueva reemplaza a la vieja del mismo punto."""
    def clave(f):
        return (f.get("variante") or f.get("metodo") or f.get("capacidad_pct"), str(f["n"] if "n" in f else f.get("accesos")))
    with open(ruta, encoding="utf-8") as f:
        viejas = list(csv.DictReader(f))
    reemplazadas = {clave(f) for f in nuevas}
    return [f for f in viejas if clave(f) not in reemplazadas] + list(nuevas)


class Banco:
    def __init__(self, args):
        self.args = args
        self.filas = {}

    def repeticiones(self, funcion, entrada, n, lenta):
        a = self.args
        if n >= 10_000_000:
            return a.reps_10m
        base = a.repeticiones if n <= 100_000 else a.reps_1m
        if lenta:
            base = min(base, a.reps_cuadratico)
        inicio = perf_counter()
        funcion(entrada)
        estimado = perf_counter() - inicio
        if estimado <= 0:
            return base
        return max(min(3, base), min(base, int(a.presupuesto / estimado)))

    def correr(self, experimento, variante, funcion, entrada, n, extra="", max_n=None):
        if max_n is not None and n > max_n:
            return None
        reps = self.repeticiones(funcion, entrada, n, lenta=max_n is not None)
        medida = medir(funcion, entrada, reps)
        extra = extra() if callable(extra) else extra
        fila = {"experimento": experimento, "variante": variante, "n": n, "repeticiones": reps,
                **medida, "extra": extra, "semilla": self.args.semilla, "plataforma": plataforma()}
        self.filas.setdefault(experimento, []).append(fila)
        print(f"  {experimento:<18} {variante:<20} n={n:>10,}  reps={reps:<4} "
              f"prom={medida['prom_s']:.6f}s  desv={medida['desv_s']:.6f}s  "
              f"pico={medida['mem_pico_bytes'] / 1e6:,.1f} MB  {extra}", flush=True)
        return medida

    def agregar_fila(self, experimento, fila):
        self.filas.setdefault(experimento, []).append(fila)

    def guardar(self):
        os.makedirs(self.args.salida, exist_ok=True)
        for experimento, filas in self.filas.items():
            ruta = os.path.join(self.args.salida, f"{PREFIJO}{experimento}.csv")
            columnas = COLUMNAS_ACIERTOS if experimento == "lru_aciertos" else COLUMNAS
            if self.args.anexar and os.path.exists(ruta):
                filas = combinar(ruta, filas)
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                escritor = csv.DictWriter(f, fieldnames=columnas)
                escritor.writeheader()
                escritor.writerows(filas)
        print(f"guardado en {self.args.salida}", flush=True)


def experimento_heap(banco, n):
    datos = enteros(n, banco.args.semilla)
    banco.correr("heap", "minheap_propio", heap_propio, datos, n)
    banco.correr("heap", "heapq", heap_heapq, datos, n)
    banco.correr("heap", "lista_ordenada", heap_lista_ordenada, datos, n, max_n=MAX_N_LISTA_ORDENADA)


def experimento_heap_construccion(banco, n):
    datos = enteros(n, banco.args.semilla)
    banco.correr("heap_construccion", "heapify", construir_heapify, datos, n)
    banco.correr("heap_construccion", "n_push", construir_n_push, datos, n)


def experimento_hash(banco, n):
    entrada = datos_hash(n, banco.args.semilla)

    def estadisticas():
        t = hash_propia(entrada)
        consecutiva = TablaHash()
        for i in range(n):
            consecutiva.insertar(1_000_000 + i, i)
        return (f"cubetas={t.capacidad};carga={t.factor_carga:.3f};cadena_max={t.cadena_mas_larga()};"
                f"redimensionamientos={t.redimensionamientos};cadena_max_ids_consecutivos={consecutiva.cadena_mas_larga()}")

    banco.correr("hash", "tabla_hash_propia", hash_propia, entrada, n, extra=estadisticas)
    banco.correr("hash", "dict", hash_dict, entrada, n)
    banco.correr("hash", "lista_lineal", hash_lista_lineal, entrada, n, max_n=MAX_N_LISTA_LINEAL)


def experimento_lru(banco, n):
    accesos, capacidad, productos = datos_lru(n, banco.args.semilla)
    entrada = (accesos, capacidad)

    def estadisticas():
        c = lru_propia(entrada)
        return (f"productos={productos};capacidad={capacidad};tasa_aciertos={c.tasa_aciertos:.4f};"
                f"expulsiones={c.expulsiones}")

    banco.correr("lru", "cache_lru_propia", lru_propia, entrada, n, extra=estadisticas)
    banco.correr("lru", "ordereddict", lru_ordereddict, entrada, n)
    banco.correr("lru", "lista_mover_al_final", lru_lista, entrada, n, max_n=MAX_N_LRU_LISTA)


def experimento_lru_aciertos(banco, n):
    for pct in (1, 2, 5, 10, 20, 50):
        accesos, capacidad, productos = datos_lru(n, banco.args.semilla, capacidad_pct=pct)
        c = lru_propia((accesos, capacidad))
        banco.agregar_fila("lru_aciertos", {
            "experimento": "lru_aciertos", "capacidad_pct": pct, "capacidad": capacidad,
            "productos": productos, "accesos": n, "tasa_aciertos": round(c.tasa_aciertos, 6),
            "expulsiones": c.expulsiones, "semilla": banco.args.semilla, "plataforma": plataforma()})
        print(f"  lru_aciertos       capacidad={pct:>2}% ({capacidad:,})  n={n:,}  aciertos={c.tasa_aciertos:.1%}",
              flush=True)


def experimento_bplus_insercion(banco, n):
    claves = enteros(n, banco.args.semilla)
    for orden in (64, 16, 256):
        banco.correr("bplus_insercion", f"bplus_{orden}", bplus_con_orden(orden), claves, n)
    banco.correr("bplus_insercion", "lista_ordenada", lista_ordenada_insercion, claves, n,
                 max_n=MAX_N_LISTA_ORDENADA)


def experimento_bplus_rango(banco, n):
    claves = enteros(n, banco.args.semilla)
    arbol = bplus_con_orden(64)(claves)
    ordenada = sorted(claves)
    entrada = (arbol, ordenada, consultas_rango(ordenada, banco.args.semilla))
    arbol.buscar(ordenada[len(ordenada) // 2])
    extra = f"altura={arbol.altura};nodos_leidos_por_busqueda={arbol.nodos_leidos};claves_distintas={arbol.n_claves}"
    banco.correr("bplus_rango", "bplus_64", rango_bplus, entrada, n, extra=extra)
    banco.correr("bplus_rango", "bisect_lista", rango_bisect, entrada, n)
    banco.correr("bplus_rango", "recorrido_lineal", rango_lineal, entrada, n, max_n=MAX_N_RANGO_LINEAL)


def experimento_matriz(banco, n):
    interacciones, usuarios, productos = datos_matriz(n, banco.args.semilla)

    def estadisticas():
        m = matriz_dispersa(interacciones)
        filas, columnas = m.forma
        densa = usuarios * productos * 8   # float64 por celda
        return (f"usuarios={filas};productos={columnas};celdas={m.nnz};densidad={m.densidad:.2e};"
                f"densa_bytes={densa}")

    banco.correr("matriz", "matriz_dispersa_propia", matriz_dispersa, interacciones, n, extra=estadisticas)
    banco.correr("matriz", "dict_pares", matriz_dict_pares, interacciones, n)


FUNCIONES = {
    "heap": experimento_heap,
    "heap_construccion": experimento_heap_construccion,
    "hash": experimento_hash,
    "lru": experimento_lru,
    "lru_aciertos": experimento_lru_aciertos,
    "bplus_insercion": experimento_bplus_insercion,
    "bplus_rango": experimento_bplus_rango,
    "matriz": experimento_matriz,
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tamanos", type=int, nargs="+", default=[1_000, 10_000, 100_000, 1_000_000])
    p.add_argument("--repeticiones", type=int, default=100, help="máximo hasta 100K elementos")
    p.add_argument("--reps-1m", type=int, default=10)
    p.add_argument("--reps-10m", type=int, default=3)
    p.add_argument("--reps-cuadratico", type=int, default=10)
    p.add_argument("--presupuesto", type=float, default=20.0,
                   help="segundos aproximados por punto (variante y tamaño); mínimo 3 repeticiones")
    p.add_argument("--n-aciertos", type=int, default=1_000_000,
                   help="accesos para la curva de aciertos de la LRU")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--experimentos", nargs="+", choices=EXPERIMENTOS, default=list(EXPERIMENTOS))
    p.add_argument("--salida", default=CARPETA_RESULTADOS)
    p.add_argument("--anexar", action="store_true",
                   help="suma los resultados a los CSV existentes en vez de reemplazarlos")
    p.add_argument("--rapido", action="store_true", help="prueba de humo: 1K y 10K con 3 repeticiones")
    args = p.parse_args(argv)
    if args.rapido:
        args.tamanos = [1_000, 10_000]
        args.repeticiones = args.reps_cuadratico = 3
        args.n_aciertos = 10_000

    sin_modo_eficiencia()
    print(plataforma())
    if energia() == "bateria":
        print("AVISO: la laptop está en batería; para el informe corre esto enchufado.")
    banco = Banco(args)
    if "lru_aciertos" in args.experimentos:
        print(f"\n== curva de aciertos de la LRU ({args.n_aciertos:,} accesos) ==", flush=True)
        experimento_lru_aciertos(banco, args.n_aciertos)
    for n in sorted(args.tamanos):
        print(f"\n== n = {n:,} ==", flush=True)
        for nombre in args.experimentos:
            if nombre != "lru_aciertos":
                FUNCIONES[nombre](banco, n)
        banco.guardar()   # después de cada tamaño, para no perder lo medido si una corrida larga se corta


if __name__ == "__main__":
    sys.exit(main())
