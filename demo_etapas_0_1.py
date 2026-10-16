"""Demo de las etapas 0 y 1.

Un stream entra por la cola FIFO (etapa 0), se entrega por lotes a la etapa 1
y sale validado, ordenado por tiempo y sin duplicados, listo para la etapa 2.

Uso (desde la raíz del proyecto):
    python demo_etapas_0_1.py
    python demo_etapas_0_1.py --csv C:/datos/2019-Oct.csv --limite 200000
    python demo_etapas_0_1.py --ventana 3
"""

import argparse
from datetime import datetime, timezone
from time import perf_counter

from experimentos.datos_sinteticos import iterar_eventos
from src.etapa0_ingesta import Etapa0Ingesta, leer_csv
from src.etapa1_preprocesamiento import Etapa1Preprocesamiento, eventos_en_rango
from src.etapa1_preprocesamiento.preprocesamiento import campo


def hora(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def porcentaje(valor):
    return "n/a (los eventos no traen es_duplicado)" if valor is None else f"{valor:.2%}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="CSV de REES46; sin esto se usan eventos sintéticos")
    p.add_argument("--limite", type=int, default=20_000, help="cantidad de eventos a leer o generar")
    p.add_argument("--tam-lote", type=int, default=1_000)
    p.add_argument("--capacidad", type=int, default=10_000)
    p.add_argument("--ventana", type=int, default=0, help="segundos de tolerancia para duplicados (0 = exactos)")
    p.add_argument("--semilla", type=int, default=42)
    args = p.parse_args(argv)

    if args.csv:
        fuente = leer_csv(args.csv, limite=args.limite)
        origen = f"{args.csv} (primeros {args.limite:,} eventos)"
    else:
        fuente = iterar_eventos(args.limite, semilla=args.semilla)
        origen = f"{args.limite:,} eventos sintéticos (semilla {args.semilla})"

    etapa0 = Etapa0Ingesta(capacidad=args.capacidad, tam_lote=args.tam_lote)
    etapa1 = Etapa1Preprocesamiento(ventana_seg=args.ventana)
    primer_resultado = None
    inicio = perf_counter()
    for lote in etapa0.procesar_stream(fuente):
        resultado = etapa1.procesar(lote)
        if primer_resultado is None:
            primer_resultado = resultado
    total = perf_counter() - inicio

    m0 = etapa0.metricas()
    m1 = etapa1.metricas()
    print(f"Origen: {origen}")
    print(f"Buffer: capacidad {args.capacidad:,}, lotes de {args.tam_lote:,}, "
          f"deduplicación {'exacta' if args.ventana == 0 else f'con ventana de {args.ventana} s'}\n")

    print("Etapa 0 (cola FIFO)")
    print(f"  recibidos {m0['recibidos']:,} | entregados {m0['entregados']:,} | "
          f"lotes {m0['lotes']:,} | buffer lleno {m0['contrapresion']} veces")

    print("\nEtapa 1 (preprocesamiento)")
    print(f"  recibidos   {m1['recibidos']:,}")
    print(f"  descartados {m1['descartados']:,}")
    for motivo, cantidad in sorted(m1["descartados_por_motivo"].items(), key=lambda x: -x[1]):
        print(f"      {motivo:<22}{cantidad:,}")
    print(f"  duplicados  {m1['duplicados']:,}")
    print(f"  entregados  {m1['entregados']:,}  -> a la etapa 2")
    print(f"  precisión de la deduplicación {porcentaje(m1['precision_dedup'])}")
    print(f"  recall de la deduplicación    {porcentaje(m1['recall_dedup'])}")
    print(f"  tiempo: validar {m1['t_validar']:.3f} s | ordenar {m1['t_ordenar']:.3f} s | "
          f"deduplicar {m1['t_deduplicar']:.3f} s")
    etapa1_s = m1["t_validar"] + m1["t_ordenar"] + m1["t_deduplicar"]
    if etapa1_s > 0:
        print(f"  {m1['recibidos'] / etapa1_s:,.0f} eventos/s en la etapa 1; "
              f"{m0['recibidos'] / total:,.0f} eventos/s contando lectura y etapa 0")

    eventos = primer_resultado.eventos if primer_resultado else []
    if eventos:
        print("\nPrimeros eventos del primer lote limpio:")
        for e in eventos[:3]:
            print(f"  {hora(campo(e, 'event_time'))}  {campo(e, 'event_type'):<16}"
                  f"producto {campo(e, 'product_id')}  {campo(e, 'brand')}  {campo(e, 'price'):.2f}")
        t0 = campo(eventos[0], "event_time")
        en_minuto = eventos_en_rango(eventos, t0, t0 + 59)
        print(f"\nBúsqueda binaria: {len(en_minuto):,} eventos del primer lote entre "
              f"{hora(t0)} y {hora(t0 + 59)}")


if __name__ == "__main__":
    main()
