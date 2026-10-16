"""Etapa 1: preprocesamiento por lote (validar, ordenar, deduplicar)."""

from src.etapa1_preprocesamiento.busqueda import busqueda_lineal, contiene, lower_bound, rango, upper_bound
from src.etapa1_preprocesamiento.ordenacion import insercion, merge_sort, quicksort
from src.etapa1_preprocesamiento.preprocesamiento import (
    Etapa1Preprocesamiento,
    ResultadoLote,
    clave_evento,
    contiene_evento,
    deduplicar_exacto,
    deduplicar_ventana,
    evaluar_deduplicacion,
    eventos_en_rango,
    normalizar_evento,
    procesar_lote,
)

__all__ = [
    "Etapa1Preprocesamiento",
    "ResultadoLote",
    "busqueda_lineal",
    "clave_evento",
    "contiene",
    "contiene_evento",
    "deduplicar_exacto",
    "deduplicar_ventana",
    "evaluar_deduplicacion",
    "eventos_en_rango",
    "insercion",
    "lower_bound",
    "merge_sort",
    "normalizar_evento",
    "procesar_lote",
    "quicksort",
    "rango",
    "upper_bound",
]
