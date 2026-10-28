import csv
from pathlib import Path

import matplotlib.pyplot as plt


entrada = Path("experimentos/resultados/estructuras_c.csv")
salida = Path("experimentos/figuras/estructuras_c_loglog.png")

with entrada.open(newline="", encoding="utf-8") as archivo:
    filas = list(csv.DictReader(archivo))

if not filas:
    raise ValueError(f"No hay mediciones en {entrada}")

n = [int(fila["n"]) for fila in filas]


def valores(campo):
    return [
        float(fila[campo]) if fila[campo] else None
        for fila in filas
    ]


fig, ejes = plt.subplots(1, 3, figsize=(16, 5))

# Construcción e inserción
ejes[0].loglog(n, valores("kd_build_s"), marker="o", label="KD-Tree")
ejes[0].loglog(n, valores("trie_build_s"), marker="o", label="Trie")
ejes[0].set_title("Construcción e inserción")
ejes[0].set_ylabel("Tiempo (s)")
ejes[0].legend()

# Consultas
ejes[1].loglog(n, valores("kd_query_avg_s"), marker="o", label="KNN en KD-Tree")
ejes[1].loglog(n, valores("trie_query_avg_s"), marker="o", label="Autocompletado Trie")
ejes[1].set_title("Tiempo promedio de consulta")
ejes[1].set_ylabel("Tiempo (s)")
ejes[1].legend()

# Memoria pico
for campo, etiqueta in [
    ("kd_peak_mb", "KD-Tree"),
    ("trie_peak_mb", "Trie"),
]:
    xs = [
        int(fila["n"])
        for fila in filas
        if fila[campo] and float(fila[campo]) > 0
    ]
    ys = [
        float(fila[campo])
        for fila in filas
        if fila[campo] and float(fila[campo]) > 0
    ]
    if xs:
        ejes[2].loglog(xs, ys, marker="o", label=etiqueta)

ejes[2].set_title("Memoria pico")
ejes[2].set_ylabel("Memoria (MB)")
ejes[2].legend()

for eje in ejes:
    eje.set_xlabel("Cantidad de elementos (n)")
    eje.grid(True, which="both", linestyle=":", alpha=0.5)

fig.suptitle("Escalabilidad de KD-Tree y Trie", fontsize=14)
fig.tight_layout()

salida.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(salida, dpi=160, bbox_inches="tight")
print(f"Gráfico guardado en {salida}")