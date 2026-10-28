"""Ejecuta el pipeline de las 10 etapas de punta a punta y muestra sus salidas.

Uso (desde la raíz del proyecto):
    python run_pipeline.py                                  # 10.000 eventos sintéticos con fraude
    python run_pipeline.py --n 100000 --semilla 7
    python run_pipeline.py --csv data/sample/eventos.csv    # muestra de REES46 (sin campos de fraude)
    python run_pipeline.py --csv C:/datos/2019-Oct.csv --limite 200000

Con datos sintéticos el stream trae los campos de fraude (ip, dispositivo_id,
medio_pago) y la etiqueta es_fraude, que solo se usa para medir precisión y
recall de la etapa 6. Un CSV de REES46 no trae esos campos: la etapa 6 deja
pasar todo sin marcar y el resto del pipeline funciona igual.

Muestra:
    1. cuántos eventos pasaron por cada etapa y cuánto tardó cada una
    2. las alertas de fraude, del más urgente al menos urgente
    3. los productos más influyentes (PageRank)
    4. el recorrido de un evento por las 10 etapas
"""

import argparse
import sys
from time import perf_counter

from experimentos.datos_sinteticos import generar_eventos_fraude
from src.etapa0_ingesta import leer_csv
from src.pipeline import ETAPAS, ORDEN_CIERRE, ORDEN_FLUJO, Pipeline


def formato(valor):
    if isinstance(valor, float):
        return f"{valor:.4f}"
    if isinstance(valor, dict):
        return ", ".join(f"{k}={formato(v)}" for k, v in valor.items())
    return str(valor)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=10_000, help="eventos sintéticos a generar")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--csv", help="ruta de un CSV de REES46 en lugar de datos sintéticos")
    p.add_argument("--limite", type=int, help="máximo de filas a leer del CSV")
    p.add_argument("--tam-lote", type=int, default=1_000)
    p.add_argument("--alertas", type=int, default=5, help="alertas de fraude a mostrar")
    args = p.parse_args(argv)

    if args.csv:
        stream, lista_negra = leer_csv(args.csv, limite=args.limite), ()
        origen = f"CSV {args.csv}"
    else:
        eventos, lista_negra = generar_eventos_fraude(args.n, semilla=args.semilla)
        stream = eventos
        origen = f"{args.n:,} eventos sintéticos con fraude (semilla {args.semilla})".replace(",", ".")

    print(f"Pipeline de 10 etapas · {origen}\n")
    inicio = perf_counter()
    pipeline = Pipeline(lista_negra=lista_negra, tam_lote=args.tam_lote, semilla=args.semilla)
    pipeline.procesar(stream)
    pipeline.cerrar()
    total = perf_counter() - inicio

    print("1. Etapas")
    resumen = pipeline.resumen()
    for etapa in ORDEN_FLUJO + ORDEN_CIERRE:
        tiempo = "en la 9" if etapa == 7 else f"{pipeline.tiempos[etapa]:.2f} s"
        print(f"   {etapa}  {ETAPAS[etapa]:<44} {tiempo:>9}   {formato(resumen[etapa])}")
    print(f"   Total: {total:.2f} s (el servicio de la etapa 9 construye los índices de la 7)\n")

    print(f"2. Alertas de fraude: {len(pipeline.alertas)} eventos marcados")
    for alerta in pipeline.servicio.alertas[:args.alertas]:
        print(f"   {alerta['event_type']:<9} producto {alerta['product_id']}  usuario {alerta['user_id']}  "
              f"score {alerta['score']}  ({alerta['motivos']})")
    print()

    print("3. Productos más influyentes (PageRank del grafo de co-compra)")
    for producto, puntaje in pipeline.influyentes(5):
        print(f"   {producto}  {puntaje:.6f}")
    print()

    evento = pipeline.evento_para_demo()
    print(f"4. Recorrido de un evento: {evento['event_type']} del producto {evento['product_id']} "
          f"(usuario {evento['user_id']})")
    for etapa, nombre, resultado in pipeline.recorrido(evento):
        print(f"   {etapa}  {nombre:<44} {resultado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
