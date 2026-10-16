"""Gráficos log-log a partir de los CSV de bench_etapas_0_1.

Uso (desde la raíz del proyecto):
    python -m experimentos.graficar_etapas_0_1
    python -m experimentos.graficar_etapas_0_1 --entrada experimentos/resultados_preliminares --salida experimentos/figuras_preliminares

Por cada experimento genera una figura de tiempo y, si hay datos, otra de
memoria pico, en escala log-log. La implementación propia que usa el pipeline
va en azul; las alternativas en grises con trazos distintos. Cada línea lleva
su nombre y su pendiente al final: cerca de 1 es lineal, cerca de 2 es
cuadrática y n log n queda algo por encima de 1. También imprime la tabla de
pendientes.
"""

import argparse
import csv
import glob
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CARPETA = os.path.dirname(__file__)
TITULOS = {
    "cola": "Etapa 0: encolar y desencolar n elementos",
    "stream": "Etapa 0: stream de n eventos entregado en lotes de 1.000",
    "ordenacion": "Etapa 1: ordenar n claves",
    "deduplicacion": "Etapa 1: ordenar y deduplicar n claves",
    "busqueda": "Etapa 1: 100 búsquedas en n claves ordenadas",
    "pipeline": "Etapas 0 y 1: n eventos de punta a punta",
}
NOMBRES = {
    "lista_enlazada": "Lista enlazada (propia)",
    "buffer_circular": "Buffer circular (propio)",
    "deque": "collections.deque (C)",
    "list_pop0": "list.pop(0)",
    "lista": "Con lista enlazada",
    "circular": "Con buffer circular",
    "merge_sort": "Merge sort (propio)",
    "quicksort": "Quicksort (propio)",
    "sorted_timsort": "sorted() Timsort (C)",
    "insercion": "Inserción (propia)",
    "merge_sort_y_vecinos": "Merge sort + vecinos (propio)",
    "sorted_y_vecinos": "sorted() + vecinos",
    "hash_set": "Conjunto hash",
    "binaria_propia": "Binaria (propia)",
    "bisect_python": "bisect (C)",
    "busqueda_lineal": "Lineal",
    "lotes_1000": "Lotes de 1.000",
}
PANELES = {"_aleatorio": "Entrada en orden aleatorio", "_casi_ordenado": "Entrada casi ordenada (como llega el stream)"}
# La implementación que usa el pipeline: el acento azul. El resto, grises con trazos distintos.
ELEGIDAS = {"lista_enlazada", "lista", "merge_sort", "merge_sort_y_vecinos", "binaria_propia", "lotes_1000"}
AZUL = "#2a78d6"
GRISES = [("#4a4945", (0, (5, 2))), ("#7a7873", (0, (1, 1.5))), ("#a3a19a", (0, (6, 2, 1, 2)))]
TINTA, TINTA_SUAVE, REJILLA = "#1f1f1d", "#52514e", "#e5e4df"


def pendiente(xs, ys):
    """Pendiente por mínimos cuadrados en escala log-log."""
    lx = [math.log10(x) for x in xs]
    ly = [math.log10(y) for y in ys]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    den = sum((x - mx) ** 2 for x in lx)
    return sum((x - mx) * (y - my) for x, y in zip(lx, ly)) / den if den else float("nan")


def leer(ruta):
    series = {}
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            pico = fila["mem_pico_bytes"]
            series.setdefault(fila["variante"], []).append((
                int(fila["n"]), float(fila["prom_s"]), float(fila["desv_s"]),
                float(pico) if pico else None,
            ))
    for puntos in series.values():
        puntos.sort()
    return series


def separar_paneles(series):
    """La ordenación trae variantes '<algoritmo>_<entrada>': un panel por entrada."""
    paneles = {}
    for variante, puntos in series.items():
        for sufijo, titulo in PANELES.items():
            if variante.endswith(sufijo):
                paneles.setdefault(titulo, {})[variante[: -len(sufijo)]] = puntos
                break
        else:
            paneles.setdefault("", {})[variante] = puntos
    return paneles


def estilos(nombres):
    """Mismo estilo para la misma variante en todos los paneles de una figura."""
    grises = iter(GRISES)
    salida = {}
    for nombre in sorted(nombres, key=lambda v: (v not in ELEGIDAS, v)):
        if nombre in ELEGIDAS:
            salida[nombre] = (AZUL, "-", 2.4)
        else:
            color, trazo = next(grises, GRISES[-1])
            salida[nombre] = (color, trazo, 1.8)
    return salida


def etiquetar(ax, fig, etiquetas):
    """Nombre al final de cada línea, separando las que caerían encima de otra."""
    fig.canvas.draw()
    a_pixeles = ax.transData.transform
    puestos = sorted(((a_pixeles((x, y))[1], x, y, texto, color) for x, y, texto, color in etiquetas))
    minimo = 40  # px entre etiquetas, a dpi 200 (una línea de texto de 9 pt mide unos 32 px)
    previo = None
    for py, x, y, texto, color in puestos:
        destino = py if previo is None else max(py, previo + minimo)
        previo = destino
        desplazamiento = (destino - py) * 72 / fig.dpi
        ax.annotate(texto, xy=(x, y), xytext=(8, desplazamiento), textcoords="offset points",
                    va="center", fontsize=9, color=TINTA,
                    arrowprops=None if abs(desplazamiento) < 2 else
                    {"arrowstyle": "-", "color": color, "lw": 0.8, "shrinkA": 0, "shrinkB": 2})


def dibujar_panel(ax, fig, series, estilo, columna, con_error, titulo_panel):
    pendientes, etiquetas = {}, []
    for variante, puntos in sorted(series.items(), key=lambda kv: (kv[0] not in ELEGIDAS, kv[0])):
        datos = [(p[0], p[columna], p[2]) for p in puntos if p[columna]]
        if not datos:
            continue
        ns = [d[0] for d in datos]
        ys = [d[1] for d in datos]
        color, trazo, grosor = estilo[variante]
        nombre = NOMBRES.get(variante, variante)
        leyenda = nombre
        if len(ns) >= 2:
            pendientes[variante] = pendiente(ns, ys)
            leyenda = f"{nombre} · pendiente {format(pendientes[variante], '.2f').replace('.', ',')}"
        ax.plot(ns, ys, color=color, linestyle=trazo, linewidth=grosor, marker="o", markersize=5,
                markerfacecolor=color, markeredgecolor="white", markeredgewidth=1, label=leyenda, zorder=3)
        if con_error:
            ax.errorbar(ns, ys, yerr=[[min(d[2], d[1] * 0.99) for d in datos], [d[2] for d in datos]],
                        fmt="none", ecolor=color, elinewidth=1, capsize=2, alpha=0.7, zorder=2)
        etiquetas.append((ns[-1], ys[-1], nombre, color))
    if not etiquetas:
        return pendientes
    ax.set_xscale("log")
    ax.set_yscale("log")
    xs = [e[0] for e in etiquetas]
    ax.set_xlim(min(min(p[0] for p in pts) for pts in series.values()) / 1.6, max(xs) * 12)
    ax.grid(True, which="major", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_SUAVE)
    ax.tick_params(colors=TINTA_SUAVE, labelsize=9)
    ax.set_xlabel("n (elementos, escala log)", color=TINTA_SUAVE, fontsize=10)
    if titulo_panel:
        ax.set_title(titulo_panel, color=TINTA, fontsize=10.5, loc="left")
    # Leyenda debajo del eje: dentro taparía las curvas que suben hacia la esquina.
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.17), ncol=2, fontsize=8, frameon=False)
    etiquetar(ax, fig, etiquetas)
    return pendientes


def figura(experimento, series, columna, ruta, con_error):
    paneles = separar_paneles(series)
    nombres = {v for panel in paneles.values() for v in panel}
    estilo = estilos(nombres)
    tiene_datos = any(p[columna] for pts in series.values() for p in pts)
    if not tiene_datos:
        return {}
    fig, ejes = plt.subplots(1, len(paneles), figsize=(7.2 * len(paneles), 4.6), dpi=200,
                             sharey=True, squeeze=False)
    pendientes = {}
    for ax, (titulo_panel, panel) in zip(ejes[0], sorted(paneles.items(), key=lambda kv: kv[0])):
        sufijo = next((s for s, t in PANELES.items() if t == titulo_panel), "")
        for variante, m in dibujar_panel(ax, fig, panel, estilo, columna, con_error, titulo_panel).items():
            pendientes[variante + sufijo] = m
    unidad = "tiempo promedio por corrida (s, escala log)" if columna == 1 else "memoria pico (bytes, escala log)"
    ejes[0][0].set_ylabel(unidad, color=TINTA_SUAVE, fontsize=10)
    titulo = TITULOS.get(experimento, experimento) + ("" if columna == 1 else ": memoria pico")
    fig.suptitle(titulo, x=0.01, y=0.985, ha="left", fontsize=13, color=TINTA, fontweight="semibold")
    fig.text(0.01, 0.925, "Pendiente en log-log: 1 = lineal, 2 = cuadrática, algo más de 1 = n log n, cerca de 0 = log n",
             fontsize=9, color=TINTA_SUAVE, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(ruta, facecolor="white")
    plt.close(fig)
    return pendientes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entrada", default=os.path.join(CARPETA, "resultados"))
    p.add_argument("--salida", default=os.path.join(CARPETA, "figuras"))
    args = p.parse_args(argv)
    os.makedirs(args.salida, exist_ok=True)

    rutas = sorted(glob.glob(os.path.join(args.entrada, "etapas01_*.csv")))
    if not rutas:
        print(f"No hay CSV en {args.entrada}. Corre antes experimentos.bench_etapas_0_1.")
        return 1
    tabla = []
    for ruta in rutas:
        experimento = os.path.basename(ruta)[len("etapas01_"):-len(".csv")]
        series = leer(ruta)
        pendientes = figura(experimento, series, 1,
                            os.path.join(args.salida, f"etapas01_{experimento}.png"), con_error=True)
        figura(experimento, series, 3,
               os.path.join(args.salida, f"etapas01_{experimento}_memoria.png"), con_error=False)
        tabla.extend((experimento, variante, m) for variante, m in sorted(pendientes.items()))
    print(f"figuras en {args.salida}")
    print(f"\n{'experimento':<15}{'variante':<30}{'pendiente tiempo':>18}")
    for experimento, variante, m in tabla:
        print(f"{experimento:<15}{variante:<30}{m:>18.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
