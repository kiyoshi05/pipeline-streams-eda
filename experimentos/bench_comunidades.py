"""Benchmarks de la etapa 8: ranking de influencia y comunidades en el grafo de co-compra.

Uso (desde la raíz del proyecto):
    python -m experimentos.bench_comunidades --rapido
    python -m experimentos.bench_comunidades
    python -m experimentos.bench_comunidades --tamanos 1000 10000 100000 1000000 10000000
    python -m experimentos.bench_comunidades --experimentos ranking comunidades

Grafo de prueba. El generador del stream casi no produce compras conjuntas,
así que se usa un grafo sintético con comunidades conocidas (modelo de
partición plantada): los productos se reparten en grupos de 20 a 60, y cada
compra conjunta une dos productos del mismo grupo con probabilidad 1 - mezcla
o dos productos cualquiera con probabilidad ``mezcla``. Repetir un par suma
peso a la arista, como en el grafo real. n es la cantidad de compras
conjuntas (pares) y hay n/5 productos, es decir, un grado ponderado medio de
10. Conocer las comunidades reales permite medir si cada algoritmo acierta
(NMI contra la verdad), además de la modularidad.

Experimentos:
    construccion   armar el grafo (lista de adyacencia) con n pares
    ranking        PageRank contra ranking por grado: tiempo, memoria, iteraciones,
                   correlación de Spearman y coincidencias en el Top-10
    comunidades    Louvain contra Label Propagation: tiempo, memoria, modularidad,
                   número y tamaño de comunidades y NMI contra las comunidades reales
    estabilidad    cada método con 10 semillas: modularidad media y desviación,
                   número de comunidades y NMI entre corridas (sin tiempos)

Repeticiones: hasta 100 por punto, limitadas por --presupuesto segundos y con
un mínimo de 3; en 10M se usan --reps-10m (1 por defecto: una corrida de
Louvain en Python puro sobre 10M de pares tarda varios minutos). El CSV
registra las repeticiones usadas.

Escribe experimentos/resultados/comunidades_<experimento>.csv.
"""

import argparse
import csv
import os
import random
import statistics
import sys
from itertools import combinations
from time import perf_counter

from experimentos.bench_etapas_0_1 import COLUMNAS, energia, medir, plataforma, sin_modo_eficiencia
from src.etapa8_grafo import (
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

CARPETA_RESULTADOS = os.path.join(os.path.dirname(__file__), "resultados")
PREFIJO = "comunidades_"
EXPERIMENTOS = ("construccion", "ranking", "comunidades", "estabilidad")
COLUMNAS_ESTABILIDAD = ["experimento", "metodo", "n", "nodos", "aristas", "semillas",
                        "modularidad_media", "modularidad_desv", "comunidades_media", "comunidades_desv",
                        "nmi_entre_corridas_media", "nmi_entre_corridas_min", "nmi_verdad_media",
                        "semilla", "plataforma"]
METODOS = {"louvain": louvain, "label_propagation": label_propagation}


# --- Grafo sintético con comunidades conocidas ------------------------------------------------

def generar_pares(n, semilla, mezcla=0.15, tam_min=20, tam_max=60):
    """(pares, verdad, nodos): n compras conjuntas (u, v) y la comunidad real de cada producto."""
    azar = random.Random(semilla)
    nodos = max(tam_max, n // 5)
    grupos, verdad, inicio = [], {}, 0
    while inicio < nodos:
        tam = min(nodos - inicio, azar.randint(tam_min, tam_max))
        if tam < 2 and grupos:                      # un resto de 1 producto se suma al último grupo
            grupos[-1] = range(grupos[-1].start, nodos)
            for u in range(inicio, nodos):
                verdad[u] = len(grupos) - 1
            break
        grupos.append(range(inicio, inicio + tam))
        for u in range(inicio, inicio + tam):
            verdad[u] = len(grupos) - 1
        inicio += tam
    pares = []
    for _ in range(n):
        grupo = grupos[azar.randrange(len(grupos))]
        u = azar.choice(grupo)
        v = u
        while v == u:
            v = azar.randrange(nodos) if azar.random() < mezcla else azar.choice(grupo)
        pares.append((u, v))
    return pares, verdad, nodos


def construir(pares):
    g = GrafoCoCompra()
    agregar = g.agregar_arista
    for u, v in pares:
        agregar(u, v)
    return g


# --- Ejecución ----------------------------------------------------------------------------------------

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

    def repeticiones(self, funcion, entrada, n):
        a = self.args
        if n >= 10_000_000:
            return a.reps_10m
        base = a.repeticiones if n <= 100_000 else a.reps_1m
        inicio = perf_counter()
        funcion(entrada)
        estimado = perf_counter() - inicio
        if estimado <= 0:
            return base
        return max(min(3, base), min(base, int(a.presupuesto / estimado)))

    def correr(self, experimento, variante, funcion, entrada, n, extra=""):
        reps = self.repeticiones(funcion, entrada, n)
        medida = medir(funcion, entrada, reps)
        extra = extra() if callable(extra) else extra
        fila = {"experimento": experimento, "variante": variante, "n": n, "repeticiones": reps,
                **medida, "extra": extra, "semilla": self.args.semilla, "plataforma": plataforma()}
        self.filas.setdefault(experimento, []).append(fila)
        print(f"  {experimento:<13} {variante:<18} n={n:>10,}  reps={reps:<4} "
              f"prom={medida['prom_s']:.6f}s  desv={medida['desv_s']:.6f}s  "
              f"pico={medida['mem_pico_bytes'] / 1e6:,.1f} MB  {extra}", flush=True)

    def agregar_fila(self, experimento, fila):
        self.filas.setdefault(experimento, []).append(fila)

    def guardar(self):
        os.makedirs(self.args.salida, exist_ok=True)
        for experimento, filas in self.filas.items():
            ruta = os.path.join(self.args.salida, f"{PREFIJO}{experimento}.csv")
            columnas = COLUMNAS_ESTABILIDAD if experimento == "estabilidad" else COLUMNAS
            if self.args.anexar and os.path.exists(ruta):
                filas = combinar(ruta, filas)
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                escritor = csv.DictWriter(f, fieldnames=columnas)
                escritor.writeheader()
                escritor.writerows(filas)
        print(f"guardado en {self.args.salida}", flush=True)


def experimento_construccion(banco, n, pares, grafo, verdad):
    extra = f"nodos={grafo.n_nodos};aristas={grafo.n_aristas};peso_total={grafo.peso_total:.0f}"
    banco.correr("construccion", "lista_adyacencia", construir, pares, n, extra=extra)


def experimento_ranking(banco, n, pares, grafo, verdad):
    guardado = {}

    def con_pagerank(g):
        info = {}
        guardado["pagerank"] = pagerank(g, estadisticas=info)
        guardado["info"] = info

    def con_grado(g):
        guardado["grado"] = ranking_por_grado(g)

    banco.correr("ranking", "pagerank", con_pagerank, grafo, n,
                 extra=lambda: f"iteraciones={guardado['info']['iteraciones']};error={guardado['info']['error']:.1e}")

    def comparacion():
        pr, gr = guardado["pagerank"], guardado["grado"]
        top_pr = {u for u, _ in mayores_k(pr, 10)}
        top_gr = {u for u, _ in mayores_k(gr, 10)}
        return f"spearman_con_pagerank={correlacion_rangos(pr, gr):.4f};coinciden_top10={len(top_pr & top_gr)}"

    banco.correr("ranking", "grado_ponderado", con_grado, grafo, n, extra=comparacion)


def experimento_comunidades(banco, n, pares, grafo, verdad):
    q_verdad = modularidad(grafo, verdad)
    for metodo, algoritmo in METODOS.items():
        guardado = {}

        def correr(g, algoritmo=algoritmo, guardado=guardado):
            guardado["p"] = algoritmo(g, semilla=banco.args.semilla)

        def calidad(guardado=guardado):
            p = guardado["p"]
            r = resumen(p)
            return (f"modularidad={modularidad(grafo, p):.4f};comunidades={r['comunidades']};"
                    f"mayor={r['tamanos'][0]};nmi_verdad={informacion_mutua_normalizada(p, verdad):.4f};"
                    f"comunidades_reales={len(set(verdad.values()))};modularidad_real={q_verdad:.4f}")

        banco.correr("comunidades", metodo, correr, grafo, n, extra=calidad)


def experimento_estabilidad(banco, n, pares, grafo, verdad):
    semillas = list(range(banco.args.semillas_estabilidad))
    for metodo, algoritmo in METODOS.items():
        particiones = [algoritmo(grafo, semilla=s) for s in semillas]
        qs = [modularidad(grafo, p) for p in particiones]
        ks = [resumen(p)["comunidades"] for p in particiones]
        nmis = [informacion_mutua_normalizada(a, b) for a, b in combinations(particiones, 2)]
        nmi_verdad = [informacion_mutua_normalizada(p, verdad) for p in particiones]
        fila = {
            "experimento": "estabilidad", "metodo": metodo, "n": n, "nodos": grafo.n_nodos,
            "aristas": grafo.n_aristas, "semillas": len(semillas),
            "modularidad_media": round(statistics.mean(qs), 6),
            "modularidad_desv": round(statistics.stdev(qs), 6) if len(qs) > 1 else 0.0,
            "comunidades_media": round(statistics.mean(ks), 2),
            "comunidades_desv": round(statistics.stdev(ks), 2) if len(ks) > 1 else 0.0,
            "nmi_entre_corridas_media": round(statistics.mean(nmis), 6) if nmis else 1.0,
            "nmi_entre_corridas_min": round(min(nmis), 6) if nmis else 1.0,
            "nmi_verdad_media": round(statistics.mean(nmi_verdad), 6),
            "semilla": banco.args.semilla, "plataforma": plataforma(),
        }
        banco.agregar_fila("estabilidad", fila)
        print(f"  estabilidad   {metodo:<18} n={n:>10,}  Q={fila['modularidad_media']:.4f}±{fila['modularidad_desv']:.4f}  "
              f"comunidades={fila['comunidades_media']}±{fila['comunidades_desv']}  "
              f"NMI entre corridas={fila['nmi_entre_corridas_media']:.4f} (mín {fila['nmi_entre_corridas_min']:.4f})  "
              f"NMI con la verdad={fila['nmi_verdad_media']:.4f}", flush=True)


FUNCIONES = {
    "construccion": experimento_construccion,
    "ranking": experimento_ranking,
    "comunidades": experimento_comunidades,
    "estabilidad": experimento_estabilidad,
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tamanos", type=int, nargs="+", default=[1_000, 10_000, 100_000, 1_000_000])
    p.add_argument("--repeticiones", type=int, default=100, help="máximo hasta 100K pares")
    p.add_argument("--reps-1m", type=int, default=10)
    p.add_argument("--reps-10m", type=int, default=1)
    p.add_argument("--presupuesto", type=float, default=30.0,
                   help="segundos aproximados por punto (variante y tamaño); mínimo 3 repeticiones")
    p.add_argument("--semillas-estabilidad", type=int, default=10)
    p.add_argument("--max-n-estabilidad", type=int, default=100_000,
                   help="la estabilidad corre cada método varias veces: se limita a este n")
    p.add_argument("--mezcla", type=float, default=0.15, help="fracción de compras conjuntas entre grupos distintos")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--experimentos", nargs="+", choices=EXPERIMENTOS, default=list(EXPERIMENTOS))
    p.add_argument("--salida", default=CARPETA_RESULTADOS)
    p.add_argument("--anexar", action="store_true",
                   help="suma los resultados a los CSV existentes en vez de reemplazarlos")
    p.add_argument("--rapido", action="store_true", help="prueba de humo: 1K y 10K con 3 repeticiones")
    args = p.parse_args(argv)
    if args.rapido:
        args.tamanos = [1_000, 10_000]
        args.repeticiones = 3
        args.semillas_estabilidad = 3

    sin_modo_eficiencia()
    print(plataforma())
    if energia() == "bateria":
        print("AVISO: la laptop está en batería; para el informe corre esto enchufado.")
    banco = Banco(args)
    for n in sorted(args.tamanos):
        print(f"\n== n = {n:,} compras conjuntas ==", flush=True)
        pares, verdad, _ = generar_pares(n, args.semilla, mezcla=args.mezcla)
        grafo = construir(pares)
        print(f"  grafo: {grafo.n_nodos:,} productos, {grafo.n_aristas:,} aristas, "
              f"{len(set(verdad.values())):,} comunidades reales", flush=True)
        for nombre in args.experimentos:
            if nombre == "estabilidad" and n > args.max_n_estabilidad:
                continue
            FUNCIONES[nombre](banco, n, pares, grafo, verdad)
        del pares, grafo, verdad
        banco.guardar()


if __name__ == "__main__":
    sys.exit(main())
