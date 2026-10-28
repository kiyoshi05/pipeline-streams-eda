"""Ejecuta el pipeline de las 10 etapas de punta a punta y muestra sus salidas.

Uso (desde la raíz del proyecto):
    python run_pipeline.py                                  # 1.000 eventos del stream sintético completo
    python run_pipeline.py --n 100000 --semilla 7
    python run_pipeline.py --csv data/sample/eventos.csv    # filas de un CSV con el formato de REES46
    python run_pipeline.py --csv C:/datos/2019-Oct.csv --limite 200000

El stream sintético (experimentos/stream_completo.py) trae duplicados,
inválidos, compras express y programadas, paquetes de compras conjuntas y
fraude. Un CSV de REES46 no trae los campos del stream: se le agregan ip,
dispositivo, medio de pago, prioridad y algo de fraude (aumentar_filas).
La etiqueta es_fraude solo se usa para medir la etapa 6.

Muestra:
    1. cuántos eventos pasaron por cada etapa y cuánto tardó cada una
    2. las alertas de fraude, del más urgente al menos urgente
    3. los productos más influyentes (PageRank)
    4. el recorrido de un evento por las 10 etapas
    5. consultas de productos: ficha (caché LRU) y rango de precios (B+Tree)
    6. similitud frente al método exacto: recall@k de KD-Tree, IVF y MinHash + LSH
"""

import argparse
import sys
from time import perf_counter

from experimentos.stream_completo import aumentar_filas, generar_stream
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
    p.add_argument("--n", type=int, default=1_000, help="eventos sintéticos a generar")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--csv", help="ruta de un CSV de REES46 en lugar de datos sintéticos")
    p.add_argument("--limite", type=int, help="máximo de filas a leer del CSV")
    p.add_argument("--tam-lote", type=int, default=1_000)
    p.add_argument("--alertas", type=int, default=5, help="alertas de fraude a mostrar")
    p.add_argument("--consultas", type=int, default=500, help="visitas a fichas para medir la caché")
    p.add_argument("--cache", type=int, help="capacidad de la caché LRU (por defecto, ~10 %% del catálogo)")
    args = p.parse_args(argv)

    if args.csv:
        stream, lista_negra = aumentar_filas(leer_csv(args.csv, limite=args.limite), semilla=args.semilla)
        origen = f"CSV {args.csv} con los campos del stream agregados"
    else:
        stream, lista_negra = generar_stream(args.n, semilla=args.semilla)
        origen = f"{args.n:,} eventos del stream sintético completo (semilla {args.semilla})".replace(",", ".")

    print(f"Pipeline de 10 etapas · {origen}\n")
    inicio = perf_counter()
    # Caché del ~10 % del catálogo esperado (n/20 productos), para que tenga que elegir qué guardar
    capacidad = args.cache or max(10, args.n // 200)
    pipeline = Pipeline(lista_negra=lista_negra, tam_lote=args.tam_lote, semilla=args.semilla,
                        capacidad_cache=capacidad)
    pipeline.procesar(stream)
    pipeline.cerrar()
    total = perf_counter() - inicio

    print("1. Etapas")
    resumen = pipeline.resumen()
    for etapa in ORDEN_FLUJO + ORDEN_CIERRE:
        tiempo = f"{pipeline.tiempos[etapa]:.2f} s"
        print(f"   {etapa}  {ETAPAS[etapa]:<44} {tiempo:>9}   {formato(resumen[etapa])}")
    print(f"   Total: {total:.2f} s\n")

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
    print()

    print("5. Consultas de productos (etapas 3 y 4)")
    producto = pipeline.influyentes(1)[0][0]
    ficha = pipeline.consultar_producto(producto)
    print(f"   Ficha de {producto}: categoría {ficha['category_code']}, marca {ficha['brand']}, "
          f"precio {ficha['price']}, {ficha['vistas']} vistas, {ficha['compras']} compras")
    rango = pipeline.productos_por_precio(100, 300, limite=5)
    print(f"   Productos entre 100 y 300 (B+Tree): {rango}")
    tasa = pipeline.simular_consultas(n=args.consultas, semilla=args.semilla)
    print(f"   {args.consultas} visitas simuladas a fichas con una caché de {capacidad} productos "
          f"(de {len(pipeline.e3.catalogo)}): la caché LRU acertó el {tasa:.1%}")
    print()

    print("6. Similitud frente al método exacto (recall@5)")
    for metodo, fila in pipeline.comparar_similitud(k=5).items():
        if fila["consultas"]:
            print(f"   {metodo:<15} recall {fila['recall']:.2f}  {fila['ms_por_consulta']:7.3f} ms por consulta  "
                  f"(contra {fila['contra']}, {fila['consultas']} consultas)")
        else:
            print(f"   {metodo:<15} sin consultas: no hay productos con compradores en común")
    return 0


if __name__ == "__main__":
    sys.exit(main())
