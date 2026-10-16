"""Etapa 1: preprocesamiento por lote.

Recibe un lote de la etapa 0 y entrega a la etapa 2 un lote limpio, ordenado
por tiempo y sin duplicados. Pasos:

    1. validar y normalizar cada evento            O(n)
    2. ordenar con merge sort por la clave          O(n log n)
    3. deduplicar
         exacto: comparar vecinos                   O(n)
         con ventana de tiempo: búsqueda binaria    O(n log n + n*w)
    total por lote                                  O(n log n)

Los eventos pueden ser dict, namedtuple, dataclass u objeto con atributos:
se leen con ``campo`` y se copian con ``con_cambios``, así la etapa funciona
con la clase de src/comun/evento.py sin depender de ella.

Duplicados solo se detectan dentro del mismo lote; los que caen en lotes
distintos quedan fuera de esta etapa.
"""

import copy
import dataclasses
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain
from time import perf_counter

from src.etapa1_preprocesamiento.busqueda import lower_bound, rango
from src.etapa1_preprocesamiento.ordenacion import merge_sort

TIPOS_REES46 = frozenset({"view", "cart", "remove_from_cart", "purchase"})
CAMPOS_OBLIGATORIOS = ("event_time", "event_type", "product_id", "user_id", "user_session")
SIN_VALOR = "desconocido"
_VERDADEROS = frozenset({"1", "true", "t", "si", "sí", "yes", "y"})


# --- Acceso a campos, independiente del tipo de Evento -----------------------

def campo(evento, nombre, defecto=None):
    if isinstance(evento, dict):
        return evento.get(nombre, defecto)
    return getattr(evento, nombre, defecto)


def con_cambios(evento, cambios):
    """Devuelve una copia del evento con los campos cambiados (no muta la entrada)."""
    if isinstance(evento, dict):
        nuevo = dict(evento)
        nuevo.update(cambios)
        return nuevo
    if hasattr(evento, "_replace"):  # namedtuple
        return evento._replace(**cambios)
    if dataclasses.is_dataclass(evento):
        return dataclasses.replace(evento, **cambios)
    nuevo = copy.copy(evento)
    for nombre, valor in cambios.items():
        setattr(nuevo, nombre, valor)
    return nuevo


def _vacio(valor):
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    return isinstance(valor, float) and math.isnan(valor)


def _es_verdadero(valor):
    if isinstance(valor, str):
        return valor.strip().lower() in _VERDADEROS
    return bool(valor)


# --- Normalización -----------------------------------------------------------

def a_epoch(valor):
    """Convierte event_time a segundos desde 1970 (UTC) como entero.

    Acepta el formato de REES46 "2019-10-01 00:04:46 UTC", ISO con "T",
    datetime, o un número que ya sea epoch. Lanza ValueError si no puede.
    """
    if isinstance(valor, bool):
        raise ValueError("event_time no puede ser booleano")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            raise ValueError("event_time no es un número finito")
        return int(valor)
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return int(valor.timestamp())
    texto = str(valor).strip()
    if texto.isdigit():
        return int(texto)
    if len(texto) >= 19 and texto[4] == "-" and texto[7] == "-" and texto[13] == ":" and texto[16] == ":":
        # Se corta a mano en lugar de strptime porque es varias veces más rápido.
        momento = datetime(
            int(texto[0:4]), int(texto[5:7]), int(texto[8:10]),
            int(texto[11:13]), int(texto[14:16]), int(texto[17:19]),
            tzinfo=timezone.utc,
        )
        return int(momento.timestamp())
    raise ValueError(f"formato de event_time no reconocido: {texto!r}")


def _a_entero(valor):
    if isinstance(valor, bool):
        raise ValueError("un id no puede ser booleano")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if valor.is_integer():
            return int(valor)
        raise ValueError("id con decimales")
    return int(str(valor).strip())


def _texto(valor):
    if _vacio(valor):
        return SIN_VALOR
    return str(valor).strip().lower()


def normalizar_evento(evento, tipos_validos=TIPOS_REES46, precio_minimo=0.0):
    """Valida y normaliza un evento.

    Devuelve (evento_normalizado, None) si es válido, o (None, motivo) si se
    descarta. Tras normalizar: event_time es int (epoch UTC), product_id y
    user_id son int, price es float, event_type, brand y category_code van
    en minúsculas y los nulos de brand y category_code pasan a "desconocido".
    """
    for nombre in CAMPOS_OBLIGATORIOS:
        if _vacio(campo(evento, nombre)):
            return None, f"falta_{nombre}"

    try:
        event_time = a_epoch(campo(evento, "event_time"))
    except (ValueError, TypeError, OverflowError):
        return None, "event_time_invalido"

    event_type = str(campo(evento, "event_type")).strip().lower()
    if event_type not in tipos_validos:
        return None, "event_type_invalido"

    try:
        product_id = _a_entero(campo(evento, "product_id"))
    except (ValueError, TypeError):
        return None, "product_id_invalido"
    try:
        user_id = _a_entero(campo(evento, "user_id"))
    except (ValueError, TypeError):
        return None, "user_id_invalido"

    precio_crudo = campo(evento, "price")
    if _vacio(precio_crudo):
        return None, "falta_price"
    try:
        price = float(precio_crudo)
    except (ValueError, TypeError):
        return None, "price_invalido"
    if math.isnan(price) or math.isinf(price) or price < precio_minimo:
        return None, "price_invalido"

    cambios = {
        "event_time": event_time,
        "event_type": event_type,
        "product_id": product_id,
        "user_id": user_id,
        "user_session": str(campo(evento, "user_session")).strip(),
        "price": price,
        "brand": _texto(campo(evento, "brand")),
        "category_code": _texto(campo(evento, "category_code")),
    }
    return con_cambios(evento, cambios), None


# --- Claves ------------------------------------------------------------------

def clave_evento(evento):
    """Clave de orden y de duplicado exacto.

    Empieza por event_time, así un solo ordenamiento deja el lote en orden
    temporal para la etapa 2 y, como incluye todos los campos que definen un
    duplicado, las copias exactas quedan una al lado de la otra.
    """
    return (
        campo(evento, "event_time"),
        campo(evento, "user_session"),
        campo(evento, "product_id"),
        campo(evento, "event_type"),
        campo(evento, "user_id"),
        campo(evento, "price"),
    )


def clave_identidad(evento):
    """Lo que define un duplicado sin contar el tiempo (para la ventana)."""
    return clave_evento(evento)[1:]


def tiempo(evento):
    return campo(evento, "event_time")


# --- Deduplicación -----------------------------------------------------------

def deduplicar_exacto(ordenados, clave=clave_evento):
    """Recorre el lote ordenado y elimina los vecinos con la misma clave.

    Conserva la primera aparición; como merge sort es estable, es la que
    llegó primero. Devuelve (conservados, eliminados).
    """
    conservados = []
    eliminados = []
    anterior = object()  # centinela distinto de cualquier clave
    for evento in ordenados:
        actual = clave(evento)
        if actual == anterior:
            eliminados.append(evento)
        else:
            conservados.append(evento)
            anterior = actual
    return conservados, eliminados


def deduplicar_ventana(ordenados, ventana_seg, identidad=clave_identidad):
    """Elimina eventos iguales a otro ya conservado en los últimos ``ventana_seg`` segundos.

    Para copias cuyo timestamp varía un poco. La búsqueda binaria ubica en
    O(log n) dónde empieza la ventana [t - ventana_seg, t] dentro de los
    conservados, y solo se comparan los w eventos que caen en ella.
    Requiere que ``ordenados`` venga ordenado por tiempo.
    """
    conservados = []
    eliminados = []
    tiempos = []
    identidades = []
    for evento in ordenados:
        t = tiempo(evento)
        ident = identidad(evento)
        inicio = lower_bound(tiempos, t - ventana_seg)
        if any(identidades[i] == ident for i in range(inicio, len(identidades))):
            eliminados.append(evento)
        else:
            conservados.append(evento)
            tiempos.append(t)
            identidades.append(ident)
    return conservados, eliminados


# --- Procesamiento del lote --------------------------------------------------

@dataclass
class ResultadoLote:
    eventos: list        # limpio, ordenado por tiempo y sin duplicados: va a la etapa 2
    duplicados: list     # eliminados por duplicado, para evaluar contra la etiqueta
    descartados: dict    # motivo -> cantidad de eventos inválidos
    recibidos: int
    tiempos: dict        # segundos por paso: validar, ordenar, deduplicar

    @property
    def entregados(self):
        return len(self.eventos)

    def metricas(self):
        return {
            "recibidos": self.recibidos,
            "descartados": sum(self.descartados.values()),
            "duplicados": len(self.duplicados),
            "entregados": self.entregados,
            "descartados_por_motivo": dict(self.descartados),
            **{f"t_{paso}": seg for paso, seg in self.tiempos.items()},
        }


def procesar_lote(lote, ordenar=merge_sort, ventana_seg=0,
                  tipos_validos=TIPOS_REES46, precio_minimo=0.0):
    """Valida, ordena y deduplica un lote. Devuelve un ResultadoLote.

    ``ventana_seg=0`` deduplica solo copias exactas; con un valor positivo
    también elimina copias cuyo timestamp difiere hasta esa cantidad.
    ``ordenar`` permite cambiar el algoritmo para los benchmarks.
    """
    inicio = perf_counter()
    validos = []
    descartes = Counter()
    for evento in lote:
        normalizado, motivo = normalizar_evento(evento, tipos_validos, precio_minimo)
        if motivo is None:
            validos.append(normalizado)
        else:
            descartes[motivo] += 1
    t_validar = perf_counter()

    ordenados = ordenar(validos, clave_evento)
    t_ordenar = perf_counter()

    if ventana_seg > 0:
        conservados, eliminados = deduplicar_ventana(ordenados, ventana_seg)
    else:
        conservados, eliminados = deduplicar_exacto(ordenados)
    t_dedup = perf_counter()

    return ResultadoLote(
        eventos=conservados,
        duplicados=eliminados,
        descartados=dict(descartes),
        recibidos=len(lote),
        tiempos={
            "validar": t_validar - inicio,
            "ordenar": t_ordenar - t_validar,
            "deduplicar": t_dedup - t_ordenar,
        },
    )


# --- Consultas sobre el lote limpio (búsqueda binaria) -----------------------

def eventos_en_rango(eventos_ordenados, t_desde, t_hasta):
    """Eventos con event_time en [t_desde, t_hasta], en O(log n + resultado)."""
    i, j = rango(eventos_ordenados, t_desde, t_hasta, clave=tiempo)
    return eventos_ordenados[i:j]


def contiene_evento(eventos_ordenados, evento):
    """True si el lote limpio ya tiene un evento con la misma clave. O(log n).

    El evento consultado debe estar normalizado (mismos tipos que el lote).
    """
    buscada = clave_evento(evento)
    i = lower_bound(eventos_ordenados, buscada, clave=clave_evento)
    return i < len(eventos_ordenados) and clave_evento(eventos_ordenados[i]) == buscada


# --- Evaluación contra la etiqueta del generador -----------------------------

def evaluar_deduplicacion(resultado, etiqueta="es_duplicado"):
    """Compara lo eliminado con la etiqueta de verdad del generador sintético.

    vp: eliminado y marcado como duplicado
    fp: eliminado sin ser duplicado (un evento legítimo perdido)
    fn: conservado pero marcado como duplicado (se escapó)
    Precisión o recall valen None cuando su denominador es 0 o cuando los
    eventos no traen la etiqueta (por ejemplo, REES46 sin el generador).
    """
    con_etiqueta = any(campo(e, etiqueta) is not None
                       for e in chain(resultado.duplicados, resultado.eventos))
    if not con_etiqueta:
        return {"vp": 0, "fp": 0, "fn": 0, "precision": None, "recall": None, "con_etiqueta": False}
    vp = sum(1 for e in resultado.duplicados if _es_verdadero(campo(e, etiqueta)))
    fp = len(resultado.duplicados) - vp
    fn = sum(1 for e in resultado.eventos if _es_verdadero(campo(e, etiqueta)))
    return {
        "vp": vp,
        "fp": fp,
        "fn": fn,
        "precision": vp / (vp + fp) if vp + fp else None,
        "recall": vp / (vp + fn) if vp + fn else None,
        "con_etiqueta": True,
    }


class Etapa1Preprocesamiento:
    """Envoltorio para el orquestador: aplica procesar_lote y acumula métricas."""

    def __init__(self, ordenar=merge_sort, ventana_seg=0,
                 tipos_validos=TIPOS_REES46, precio_minimo=0.0):
        self.ordenar = ordenar
        self.ventana_seg = ventana_seg
        self.tipos_validos = tipos_validos
        self.precio_minimo = precio_minimo
        self.totales = Counter()
        self.descartes = Counter()
        self.tiempos = Counter()

    def procesar(self, lote):
        resultado = procesar_lote(lote, self.ordenar, self.ventana_seg,
                                  self.tipos_validos, self.precio_minimo)
        evaluacion = evaluar_deduplicacion(resultado)
        self.totales.update({
            "lotes": 1,
            "recibidos": resultado.recibidos,
            "descartados": sum(resultado.descartados.values()),
            "duplicados": len(resultado.duplicados),
            "entregados": resultado.entregados,
            "vp": evaluacion["vp"],
            "fp": evaluacion["fp"],
            "fn": evaluacion["fn"],
            "lotes_con_etiqueta": int(evaluacion["con_etiqueta"]),
        })
        self.descartes.update(resultado.descartados)
        self.tiempos.update(resultado.tiempos)
        return resultado

    def metricas(self):
        t = self.totales
        hay_etiqueta = t["lotes_con_etiqueta"] > 0
        eliminados = t["vp"] + t["fp"] if hay_etiqueta else 0
        marcados = t["vp"] + t["fn"] if hay_etiqueta else 0
        return {
            **{k: t[k] for k in ("lotes", "recibidos", "descartados", "duplicados", "entregados")},
            "descartados_por_motivo": dict(self.descartes),
            "precision_dedup": t["vp"] / eliminados if eliminados else None,
            "recall_dedup": t["vp"] / marcados if marcados else None,
            **{f"t_{paso}": self.tiempos[paso] for paso in ("validar", "ordenar", "deduplicar")},
        }
