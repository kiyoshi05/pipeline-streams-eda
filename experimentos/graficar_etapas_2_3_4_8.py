"""Gráficos de los benchmarks del integrante B (etapas 2, 3, 4 y 8).

Uso (desde la raíz del proyecto):
    python -m experimentos.graficar_etapas_2_3_4_8
    python -m experimentos.graficar_etapas_2_3_4_8 --entrada experimentos/resultados_prueba --salida experimentos/figuras_prueba

Usa el mismo estilo que graficar_etapas_0_1 (una figura log-log de tiempo y
otra de memoria por experimento, con la pendiente de cada línea), y agrega:

    estructuras_base_lru_aciertos.png   tasa de aciertos de la LRU según su capacidad
    comunidades_calidad.png             modularidad y NMI contra la verdad de Louvain y
                                        Label Propagation en cada tamaño

También imprime la tabla de pendientes y los resúmenes de calidad.
"""

import argparse
import csv
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import experimentos.graficar_etapas_0_1 as base  # noqa: E402

CARPETA = os.path.dirname(__file__)
SIN_FIGURA_LOGLOG = {"estructuras_base_lru_aciertos", "comunidades_estabilidad"}

base.TITULOS.update({
    "estructuras_base_heap": "Etapa 2: n push + n pop",
    "estructuras_base_heap_construccion": "Etapa 2: construir un heap con n elementos",
    "estructuras_base_hash": "Etapa 3: n inserciones + n búsquedas",
    "estructuras_base_lru": "Etapa 3: n accesos a una caché del 10 % del catálogo (popularidad Zipf)",
    "estructuras_base_bplus_insercion": "Etapa 4: insertar n claves en el índice",
    "estructuras_base_bplus_rango": "Etapa 4: 100 consultas por rango de 100 claves en un índice de n claves",
    "estructuras_base_matriz": "Etapa 3: registrar n interacciones usuario x producto",
    "comunidades_construccion": "Etapa 8: armar el grafo con n compras conjuntas",
    "comunidades_ranking": "Etapa 8: ranking de influencia en un grafo de n compras conjuntas",
    "comunidades_comunidades": "Etapa 8: detectar comunidades en un grafo de n compras conjuntas",
})
base.NOMBRES.update({
    "minheap_propio": "MinHeap (propio)",
    "heapq": "heapq (C)",
    "lista_ordenada": "Lista ordenada (insort)",
    "heapify": "heapify (propio)",
    "n_push": "n push (propio)",
    "tabla_hash_propia": "TablaHash (propia)",
    "dict": "dict (C)",
    "lista_lineal": "Lista con búsqueda lineal",
    "cache_lru_propia": "CacheLRU (propia)",
    "ordereddict": "OrderedDict (C)",
    "lista_mover_al_final": "Lista con mover al final",
    "bplus_64": "B+Tree orden 64 (propio)",
    "bplus_16": "B+Tree orden 16",
    "bplus_256": "B+Tree orden 256",
    "bisect_lista": "Lista ordenada + bisect (C)",
    "recorrido_lineal": "Recorrido lineal",
    "matriz_dispersa_propia": "Matriz dispersa, doble índice (propia)",
    "dict_pares": "dict de pares (u, p)",
    "lista_adyacencia": "Lista de adyacencia (propia)",
    "pagerank": "PageRank (propio)",
    "grado_ponderado": "Grado ponderado",
    "louvain": "Louvain (propio)",
    "label_propagation": "Label Propagation (propio)",
})
base.ELEGIDAS.update({"minheap_propio", "heapify", "tabla_hash_propia", "cache_lru_propia", "bplus_64",
                      "matriz_dispersa_propia", "lista_adyacencia", "pagerank", "louvain"})


def leer_filas(ruta):
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def extra_a_dict(texto):
    datos = {}
    for parte in (texto or "").split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            datos[k] = v
    return datos


def estilo_eje(ax):
    ax.grid(True, color=base.REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(base.TINTA_SUAVE)
    ax.tick_params(colors=base.TINTA_SUAVE, labelsize=9)


def figura_aciertos(ruta_csv, ruta_png):
    filas = sorted(leer_filas(ruta_csv), key=lambda f: float(f["capacidad_pct"]))
    if not filas:
        return
    xs = [float(f["capacidad_pct"]) for f in filas]
    ys = [100 * float(f["tasa_aciertos"]) for f in filas]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    ax.plot(xs, ys, color=base.AZUL, linewidth=2.4, marker="o", markersize=6,
            markerfacecolor=base.AZUL, markeredgecolor="white")
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.0f} %", xy=(x, y), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=9, color=base.TINTA)
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g} %" for x in xs])
    ax.set_ylim(0, 105)
    ax.set_xlabel("capacidad de la caché (% del catálogo, escala log)", color=base.TINTA_SUAVE, fontsize=10)
    ax.set_ylabel("tasa de aciertos (%)", color=base.TINTA_SUAVE, fontsize=10)
    estilo_eje(ax)
    fig.suptitle("Etapa 3: tasa de aciertos de la CacheLRU según su capacidad", x=0.01, ha="left",
                 fontsize=13, color=base.TINTA, fontweight="semibold")
    fig.text(0.01, 0.9, f"{int(filas[0]['accesos']):,} accesos con popularidad Zipf sobre "
             f"{int(filas[0]['productos']):,} productos".replace(",", "."), fontsize=9, color=base.TINTA_SUAVE)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(ruta_png, facecolor="white")
    plt.close(fig)
    print("\nAciertos de la LRU:")
    for x, y in zip(xs, ys):
        print(f"  capacidad {x:>4g} % -> {y:5.1f} % de aciertos")


def figura_calidad(ruta_csv, ruta_png):
    filas = leer_filas(ruta_csv)
    if not filas:
        return
    por_metodo = {}
    for f in filas:
        e = extra_a_dict(f["extra"])
        por_metodo.setdefault(f["variante"], []).append(
            (int(f["n"]), float(e["modularidad"]), float(e["nmi_verdad"]), float(e["modularidad_real"])))
    fig, ejes = plt.subplots(1, 2, figsize=(12, 4.4), dpi=200)
    estilos = {"louvain": (base.AZUL, "-"), "label_propagation": (base.GRISES[0][0], base.GRISES[0][1])}
    reales = {}
    for metodo, puntos in por_metodo.items():
        puntos.sort()
        color, trazo = estilos.get(metodo, (base.GRISES[1][0], base.GRISES[1][1]))
        ns = [p[0] for p in puntos]
        for ax, col in ((ejes[0], 1), (ejes[1], 2)):
            ax.plot(ns, [p[col] for p in puntos], color=color, linestyle=trazo, linewidth=2.2, marker="o",
                    markersize=5, markerfacecolor=color, markeredgecolor="white",
                    label=base.NOMBRES.get(metodo, metodo))
        for p in puntos:
            reales[p[0]] = p[3]
    ns = sorted(reales)
    ejes[0].plot(ns, [reales[n] for n in ns], color=base.GRISES[2][0], linestyle=":", linewidth=1.6,
                 label="Comunidades reales (referencia)")
    ejes[0].set_title("Modularidad (más alta = comunidades más claras)", loc="left", fontsize=10.5, color=base.TINTA)
    ejes[1].set_title("NMI contra las comunidades reales (1 = las encontró todas)", loc="left", fontsize=10.5,
                      color=base.TINTA)
    for ax in ejes:
        ax.set_xscale("log")
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("n (compras conjuntas, escala log)", color=base.TINTA_SUAVE, fontsize=10)
        estilo_eje(ax)
        ax.legend(loc="lower left", fontsize=8, frameon=False)
    fig.suptitle("Etapa 8: calidad de las comunidades", x=0.01, ha="left", fontsize=13, color=base.TINTA,
                 fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(ruta_png, facecolor="white")
    plt.close(fig)
    print("\nCalidad de las comunidades:")
    for metodo, puntos in sorted(por_metodo.items()):
        for n, q, nmi, q_real in sorted(puntos):
            print(f"  {metodo:<18} n={n:>10,}  Q={q:.4f} (real {q_real:.4f})  NMI con la verdad={nmi:.4f}")


def imprimir_estabilidad(ruta_csv):
    print("\nEstabilidad (varias semillas):")
    for f in leer_filas(ruta_csv):
        print(f"  {f['metodo']:<18} n={int(f['n']):>8,}  Q={float(f['modularidad_media']):.4f}"
              f"±{float(f['modularidad_desv']):.4f}  comunidades={f['comunidades_media']}±{f['comunidades_desv']}  "
              f"NMI entre corridas={float(f['nmi_entre_corridas_media']):.4f} (mín {float(f['nmi_entre_corridas_min']):.4f})")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entrada", default=os.path.join(CARPETA, "resultados"))
    p.add_argument("--salida", default=os.path.join(CARPETA, "figuras"))
    args = p.parse_args(argv)
    os.makedirs(args.salida, exist_ok=True)

    rutas = sorted(glob.glob(os.path.join(args.entrada, "estructuras_base_*.csv")) +
                   glob.glob(os.path.join(args.entrada, "comunidades_*.csv")))
    print("Pendientes en escala log-log (1 = lineal, 2 = cuadrática, algo más de 1 = n log n):")
    for ruta in rutas:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        if nombre in SIN_FIGURA_LOGLOG:
            continue
        series = base.leer(ruta)
        pendientes = base.figura(nombre, series, 1, os.path.join(args.salida, f"{nombre}.png"), True)
        base.figura(nombre, series, 3, os.path.join(args.salida, f"{nombre}_memoria.png"), False)
        print(f"  {nombre}")
        for variante, m in sorted(pendientes.items(), key=lambda kv: kv[1]):
            print(f"    {base.NOMBRES.get(variante, variante):<42} {m:5.2f}")

    aciertos = os.path.join(args.entrada, "estructuras_base_lru_aciertos.csv")
    if os.path.exists(aciertos):
        figura_aciertos(aciertos, os.path.join(args.salida, "estructuras_base_lru_aciertos.png"))
    calidad = os.path.join(args.entrada, "comunidades_comunidades.csv")
    if os.path.exists(calidad):
        figura_calidad(calidad, os.path.join(args.salida, "comunidades_calidad.png"))
    estabilidad = os.path.join(args.entrada, "comunidades_estabilidad.csv")
    if os.path.exists(estabilidad):
        imprimir_estabilidad(estabilidad)
    print(f"\nFiguras en {args.salida}")


if __name__ == "__main__":
    main()
