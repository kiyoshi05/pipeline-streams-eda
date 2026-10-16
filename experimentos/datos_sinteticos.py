"""Eventos sintéticos con forma de REES46 para probar y medir las etapas 0 y 1.

No reemplaza al generador oficial del grupo: solo produce lo mínimo que estas
dos etapas necesitan (campos del contrato, desorden leve en el tiempo,
duplicados etiquetados con ``es_duplicado`` y algunos registros inválidos).
Todo es reproducible con la semilla.
"""

import random
from datetime import datetime, timezone

INICIO_OCTUBRE_2019 = 1569888000  # 2019-10-01 00:00:00 UTC
TIPOS = ("view", "cart", "remove_from_cart", "purchase")
PESOS_TIPOS = (0.90, 0.05, 0.02, 0.03)
MARCAS = ("samsung", "apple", "xiaomi", "huawei", "lucente", "sony", "lg", "bosch", "")
CATEGORIAS = (
    "electronics.smartphone", "electronics.audio.headphone", "appliances.kitchen.washer",
    "computers.notebook", "apparel.shoes", "furniture.living_room.sofa", "", "", "",
)


def _texto_tiempo(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _corromper(evento, azar):
    """Deja el evento inválido de una de varias formas posibles."""
    forma = azar.randrange(5)
    if forma == 0:
        evento["price"] = "-1.0"
    elif forma == 1:
        evento["event_type"] = "desconocido"
    elif forma == 2:
        evento["user_session"] = ""
    elif forma == 3:
        evento["event_time"] = "fecha-mala"
    else:
        evento["product_id"] = "abc"


def iterar_eventos(n, semilla=42, prop_duplicados=0.05, prop_invalidos=0.01,
                   jitter_seg=0, desorden_seg=5, eventos_por_seg=2):
    """Genera n eventos (dict) en orden de llegada.

    - El tiempo avanza ``1/eventos_por_seg`` segundos por evento con un
      desorden de hasta ±``desorden_seg``, así el lote llega casi ordenado.
    - Con probabilidad ``prop_duplicados`` se agrega una copia del evento
      unas posiciones después, marcada con ``es_duplicado=True``. Si
      ``jitter_seg`` > 0, la copia trae el tiempo desplazado hasta esos segundos.
    - Con probabilidad ``prop_invalidos`` un evento sale con un campo inválido.
    """
    azar = random.Random(semilla)
    n_sesiones = max(1, n // 10)
    sesiones = [f"{azar.getrandbits(64):016x}-{i:x}" for i in range(n_sesiones)]
    usuarios = [500_000_000 + azar.randrange(10_000_000) for _ in range(n_sesiones)]
    n_productos = max(100, n // 20)
    pendientes = []  # (posición en que sale, copia)
    emitidos = 0
    i = 0
    while emitidos < n:
        while pendientes and pendientes[0][0] <= emitidos and emitidos < n:
            yield pendientes.pop(0)[1]
            emitidos += 1
        if emitidos >= n:
            break
        s = azar.randrange(n_sesiones)
        t = INICIO_OCTUBRE_2019 + i // eventos_por_seg + azar.randint(-desorden_seg, desorden_seg)
        evento = {
            "event_time": _texto_tiempo(t),
            "event_type": azar.choices(TIPOS, PESOS_TIPOS)[0],
            "product_id": 1_000_000 + azar.randrange(n_productos),
            "category_code": azar.choice(CATEGORIAS),
            "brand": azar.choice(MARCAS),
            "price": round(azar.uniform(1, 2000), 2),
            "user_id": usuarios[s],
            "user_session": sesiones[s],
            "es_duplicado": False,
        }
        i += 1
        if azar.random() < prop_invalidos:
            _corromper(evento, azar)
        elif azar.random() < prop_duplicados:
            copia = dict(evento, es_duplicado=True)
            if jitter_seg > 0:
                copia["event_time"] = _texto_tiempo(t + azar.randint(1, jitter_seg))
            pendientes.append((emitidos + 1 + azar.randrange(4), copia))
        yield evento
        emitidos += 1


def generar_eventos(n, **opciones):
    """Lista de n eventos sintéticos; ver ``iterar_eventos`` para las opciones."""
    return list(iterar_eventos(n, **opciones))


def generar_claves(n, semilla=42, prop_duplicados=0.05):
    """Claves ya normalizadas, con la forma de clave_evento, para medir la
    ordenación y la búsqueda sin el costo de memoria de eventos completos.

    Las sesiones, productos, usuarios y precios salen de grupos compartidos,
    así a 10M el costo por fila es solo la tupla y su tiempo.
    """
    azar = random.Random(semilla)
    n_sesiones = max(1, n // 10)
    sesiones = [f"{azar.getrandbits(64):016x}" for _ in range(n_sesiones)]
    productos = [1_000_000 + p for p in range(max(100, n // 20))]
    usuarios = [500_000_000 + u for u in range(n_sesiones)]
    precios = [round(azar.uniform(1, 2000), 2) for _ in range(5_000)]
    claves = []
    for i in range(n):
        if claves and azar.random() < prop_duplicados:
            claves.append(claves[azar.randrange(max(0, len(claves) - 50), len(claves))])
            continue
        s = azar.randrange(n_sesiones)
        claves.append((
            INICIO_OCTUBRE_2019 + i // 2 + azar.randint(-5, 5),
            sesiones[s],
            azar.choice(productos),
            azar.choices(TIPOS, PESOS_TIPOS)[0],
            usuarios[s],
            azar.choice(precios),
        ))
    return claves
