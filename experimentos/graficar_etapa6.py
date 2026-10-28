"""Gráficos de la etapa 6 a partir de los CSV de bench_etapa6.

Uso (desde la raíz del proyecto):
    python -m experimentos.graficar_etapa6

Genera, en escala log-log, tiempo y memoria vs n comparando la estructura propia
(azul) contra su equivalente de Python (gris): Bloom vs set y Count-Min vs dict.
También una figura del detector de fraude (eventos/s y recall vs n). Cada línea
lleva su pendiente al final: cerca de 1 es lineal.
"""

import argparse
import csv
import math
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CARPETA = os.path.dirname(__file__)
AZUL, GRIS = "#2a78d6", "#7a7873"
TINTA, REJILLA = "#1f1f1d", "#e5e4df"

NOMBRES = {
    "bloom_propio": "Filtro de Bloom (propio)",
    "set_python": "set de Python",
    "count_min_propio": "Count-Min Sketch (propio)",
    "dict_python": "dict de Python",
}


def _leer(nombre):
    ruta = os.path.join(CARPETA, "resultados", f"etapa6_{nombre}.csv")
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def _series(filas, columna):
    """{estructura: [(n, valor), ...]} ordenado por n, descartando vacíos."""
    datos = defaultdict(list)
    for fila in filas:
        valor = fila.get(columna)
        if valor in (None, "", "None"):
            continue
        datos[fila["estructura"]].append((int(fila["n"]), float(valor)))
    return {k: sorted(v) for k, v in datos.items()}


def _pendiente(xs, ys):
    pares = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
    if len(pares) < 2:
        return float("nan")
    lx = [math.log(x) for x, _ in pares]
    ly = [math.log(y) for _, y in pares]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    num = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
    den = sum((x - mx) ** 2 for x in lx)
    return num / den if den else float("nan")


def _panel_loglog(ax, series, titulo, ylabel):
    ax.set_title(titulo, color=TINTA, fontsize=11)
    for estructura, puntos in series.items():
        xs = [n for n, _ in puntos]
        ys = [v for _, v in puntos]
        es_propio = estructura.endswith("_propio")
        color = AZUL if es_propio else GRIS
        estilo = "-" if es_propio else (0, (5, 2))
        ax.plot(xs, ys, color=color, linestyle=estilo, marker="o", markersize=3,
                label=NOMBRES.get(estructura, estructura))
        if len(xs) >= 2:
            ax.annotate(f"  m={_pendiente(xs, ys):.2f}", (xs[-1], ys[-1]), color=color, fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (claves)")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", color=REJILLA, linewidth=0.6)
    ax.legend(fontsize=8)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default=os.path.join(CARPETA, "figuras"))
    args = parser.parse_args(argv)
    os.makedirs(args.salida, exist_ok=True)

    # Bloom vs set
    bloom = _leer("bloom")
    if bloom:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
        _panel_loglog(a1, _series(bloom, "construccion_media_s"),
                      "Etapa 6: construir Bloom vs set", "tiempo (s)")
        _panel_loglog(a2, _series(bloom, "memoria_pico_mb"),
                      "Etapa 6: memoria Bloom vs set", "memoria pico (MB)")
        fig.tight_layout()
        fig.savefig(os.path.join(args.salida, "etapa6_bloom.png"), dpi=120)
        plt.close(fig)
        print("  -> etapa6_bloom.png")

    # Count-Min vs dict
    cm = _leer("count_min")
    if cm:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
        _panel_loglog(a1, _series(cm, "construccion_media_s"),
                      "Etapa 6: contar con Count-Min vs dict", "tiempo (s)")
        _panel_loglog(a2, _series(cm, "memoria_pico_mb"),
                      "Etapa 6: memoria Count-Min vs dict", "memoria pico (MB)")
        fig.tight_layout()
        fig.savefig(os.path.join(args.salida, "etapa6_count_min.png"), dpi=120)
        plt.close(fig)
        print("  -> etapa6_count_min.png")

    # Detector de fraude
    det = _leer("detector")
    if det:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
        serie_tps = _series(det, "eventos_por_s")
        a1.set_title("Etapa 6: rendimiento del detector", color=TINTA, fontsize=11)
        for _, puntos in serie_tps.items():
            a1.plot([n for n, _ in puntos], [v for _, v in puntos], "-o", color=AZUL, markersize=3)
        a1.set_xscale("log")
        a1.set_xlabel("n (eventos)")
        a1.set_ylabel("eventos / s")
        a1.grid(True, which="both", color=REJILLA, linewidth=0.6)
        serie_recall = _series(det, "recall")
        a2.set_title("Etapa 6: recall del detector", color=TINTA, fontsize=11)
        for _, puntos in serie_recall.items():
            a2.plot([n for n, _ in puntos], [v for _, v in puntos], "-o", color=AZUL, markersize=3)
        a2.set_xscale("log")
        a2.set_ylim(0, 1.05)
        a2.set_xlabel("n (eventos)")
        a2.set_ylabel("recall")
        a2.grid(True, which="both", color=REJILLA, linewidth=0.6)
        fig.tight_layout()
        fig.savefig(os.path.join(args.salida, "etapa6_detector.png"), dpi=120)
        plt.close(fig)
        print("  -> etapa6_detector.png")


if __name__ == "__main__":
    main()
