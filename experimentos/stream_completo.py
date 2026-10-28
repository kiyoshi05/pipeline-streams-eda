"""Stream sintético completo: un solo generador que ejercita las 10 etapas.

Los generadores de datos_sinteticos.py prueban partes del pipeline por
separado (duplicados e inválidos por un lado, fraude por otro). Este los
junta y agrega lo que faltaba para una prueba de punta a punta:

    etapa 1   duplicados exactos (es_duplicado) y eventos inválidos
    etapa 2   compras express (prioridad 1) y programadas (prioridad 3),
              además de las estándar (sin campo: la etapa 2 les da 2)
    etapa 3   un catálogo estable: cada producto tiene su categoría, marca y
              precio, con cambios de precio ocasionales; las vistas siguen una
              popularidad Zipf, así la caché tiene productos que se repiten
    etapa 6   ip, dispositivo_id y medio_pago en cada evento, actores de
              fraude conocidos (lista negra) y ráfagas de actores nuevos
    etapas 7 y 8  compras de paquetes: productos de la misma categoría que una
              sesión compra juntos, así hay co-compras y compradores en común

``es_fraude`` y ``es_duplicado`` son etiquetas de verdad: solo sirven para
medir, el pipeline nunca las usa para decidir.

``aumentar_filas`` hace lo mismo sobre filas reales de REES46: les agrega los
campos sintéticos del stream (ip, dispositivo, medio de pago, prioridad y
algo de fraude), como recomienda el enunciado.
"""

import random
from itertools import accumulate

from experimentos.datos_sinteticos import (
    CATEGORIAS,
    INICIO_OCTUBRE_2019,
    MARCAS,
    MEDIOS_PAGO,
    _corromper,
    _ip_aleatoria,
    _texto_tiempo,
)

EXPRESS = 1
PROGRAMADA = 3
TIPOS_NAVEGACION = ("view", "cart", "remove_from_cart")
PESOS_NAVEGACION = (0.92, 0.06, 0.02)


def _actores(n_actores, azar, frac_conocidos):
    actores, lista_negra = [], set()
    for a in range(n_actores):
        conocido = a < int(n_actores * frac_conocidos)
        actor = {"ip": _ip_aleatoria(azar), "disp": f"disp-fraude-{a:04x}", "conocido": conocido}
        actores.append(actor)
        if conocido:
            lista_negra.update({f"ip:{actor['ip']}", f"disp:{actor['disp']}"})
    return actores, lista_negra


def generar_stream(n, semilla=42, prop_compra=0.05, prob_paquete=0.6, prop_express=0.25,
                   prop_programada=0.15, prop_fraude=0.006, frac_conocidos=0.5, tam_rafaga=(8, 16),
                   prop_duplicados=0.03, prop_invalidos=0.01, eventos_por_seg=2):
    """(eventos, lista_negra): n eventos en orden de llegada y los identificadores fichados."""
    azar = random.Random(semilla)

    # Catálogo estable y paquetes de productos de la misma categoría
    n_productos = max(60, n // 20)
    categorias = [c for c in CATEGORIAS if c]
    catalogo = []
    for i in range(n_productos):
        categoria = categorias[i % len(categorias)]
        catalogo.append({
            "product_id": 1_000_000 + i,
            "category_code": categoria if azar.random() > 0.1 else "",   # algunos sin categoría, como en REES46
            "brand": azar.choice(MARCAS),
            "price": round(azar.uniform(5, 2000), 2),
            "grupo": categoria,
        })
    paquetes = []
    for categoria in categorias:
        del_grupo = [p for p in catalogo if p["grupo"] == categoria]
        azar.shuffle(del_grupo)
        for j in range(0, len(del_grupo), 4):
            paquete = del_grupo[j:j + 4]
            if len(paquete) >= 2:
                paquetes.append(paquete)
    paquete_de = {p["product_id"]: paq for paq in paquetes for p in paq}
    popularidad = list(accumulate(1.0 / (r + 1) for r in range(n_productos)))   # Zipf
    orden_popular = azar.sample(catalogo, n_productos)

    # Sesiones normales con su ip y dispositivo, y actores de fraude
    n_sesiones = max(20, n // 10)
    sesiones = [{
        "user_session": f"{azar.getrandbits(64):016x}-{i:x}",
        "user_id": 500_000_000 + azar.randrange(10_000_000),
        "ip": _ip_aleatoria(azar),
        "disp": f"disp-{azar.getrandbits(32):08x}",
        "pago": azar.choice(MEDIOS_PAGO),
    } for i in range(n_sesiones)]
    actores, lista_negra = _actores(max(2, n // 400), random.Random(semilla + 1_000), frac_conocidos)

    eventos, pendientes = [], []
    reloj = 0

    def emitir(evento):
        """Agrega el evento y, a veces, programa una copia exacta o lo corrompe."""
        if azar.random() < prop_invalidos:
            _corromper(evento, azar)
        elif azar.random() < prop_duplicados:
            pendientes.append((len(eventos) + 1 + azar.randrange(4), dict(evento, es_duplicado=True)))
        eventos.append(evento)

    def evento(t, sesion, producto, tipo, es_fraude=False, ip=None, disp=None, prioridad=None):
        e = {
            "event_time": _texto_tiempo(t),
            "event_type": tipo,
            "product_id": producto["product_id"],
            "category_code": producto["category_code"],
            "brand": producto["brand"],
            "price": producto["price"],
            "user_id": sesion["user_id"],
            "user_session": sesion["user_session"],
            "ip": ip or sesion["ip"],
            "dispositivo_id": disp or sesion["disp"],
            "medio_pago": sesion["pago"],
            "es_fraude": es_fraude,
            "es_duplicado": False,
        }
        if prioridad is not None:
            e["prioridad"] = prioridad
        return e

    while len(eventos) < n:
        while pendientes and pendientes[0][0] <= len(eventos) and len(eventos) < n:
            eventos.append(pendientes.pop(0)[1])
        if len(eventos) >= n:
            break
        t = INICIO_OCTUBRE_2019 + reloj // eventos_por_seg
        reloj += 1
        if azar.random() < 0.002:                       # cambio de precio ocasional
            p = azar.choice(catalogo)
            p["price"] = round(p["price"] * azar.uniform(0.85, 1.15), 2)

        r = azar.random()
        if r < prop_fraude:
            actor = azar.choice(actores)
            sesion = azar.choice(sesiones)
            cuantos = 1 if actor["conocido"] and azar.random() < 0.4 else azar.randint(*tam_rafaga)
            for _ in range(cuantos):
                if len(eventos) >= n:
                    break
                producto = azar.choice(catalogo)
                emitir(evento(t, sesion, producto, azar.choice(("view", "cart", "purchase")),
                              es_fraude=True, ip=actor["ip"], disp=actor["disp"]))
        elif r < prop_fraude + prop_compra:
            sesion = azar.choice(sesiones)
            producto = azar.choices(orden_popular, cum_weights=popularidad)[0]
            tipo_orden = azar.random()
            prioridad = EXPRESS if tipo_orden < prop_express else (
                PROGRAMADA if tipo_orden < prop_express + prop_programada else None)
            if azar.random() < prob_paquete and producto["product_id"] in paquete_de:
                paquete = paquete_de[producto["product_id"]]
                comprados = azar.sample(paquete, azar.randint(2, len(paquete)))
            else:
                comprados = [producto]
            for p in comprados:
                if len(eventos) >= n:
                    break
                emitir(evento(t, sesion, p, "purchase", prioridad=prioridad))
        else:
            sesion = azar.choice(sesiones)
            producto = azar.choices(orden_popular, cum_weights=popularidad)[0]
            emitir(evento(t, sesion, producto, azar.choices(TIPOS_NAVEGACION, PESOS_NAVEGACION)[0]))
    return eventos[:n], lista_negra


def aumentar_filas(filas, semilla=42, prop_express=0.25, prop_programada=0.15, prop_fraude=0.01,
                   frac_conocidos=0.5, tam_rafaga=(8, 16), n_actores=20):
    """(filas aumentadas, lista_negra) para filas reales de REES46.

    Cada sesión recibe una ip, un dispositivo y un medio de pago estables; las
    compras, una prioridad express o programada al azar. Con probabilidad
    ``prop_fraude`` una fila se repite como ráfaga desde un actor de fraude
    (o, si es un actor fichado, como un evento suelto). Devuelve un generador,
    así un CSV grande no se carga entero.
    """
    azar = random.Random(semilla)
    actores, lista_negra = _actores(n_actores, random.Random(semilla + 1_000), frac_conocidos)

    cache = {}

    def por_sesion(sesion):
        if sesion not in cache:
            cache[sesion] = (_ip_aleatoria(azar), f"disp-{azar.getrandbits(32):08x}", azar.choice(MEDIOS_PAGO))
        return cache[sesion]

    def generar():
        prioridad_orden = {}
        for fila in filas:
            fila = dict(fila)
            ip, disp, pago = por_sesion(fila.get("user_session"))
            fila.update(ip=ip, dispositivo_id=disp, medio_pago=pago, es_fraude=False)
            if str(fila.get("event_type", "")).strip().lower() == "purchase":
                sesion = fila.get("user_session")
                if sesion not in prioridad_orden:
                    x = azar.random()
                    prioridad_orden[sesion] = EXPRESS if x < prop_express else (
                        PROGRAMADA if x < prop_express + prop_programada else None)
                if prioridad_orden[sesion] is not None:
                    fila["prioridad"] = prioridad_orden[sesion]
            yield fila
            if azar.random() < prop_fraude:
                actor = azar.choice(actores)
                cuantos = 1 if actor["conocido"] and azar.random() < 0.4 else azar.randint(*tam_rafaga)
                for k in range(cuantos):
                    copia = dict(fila, ip=actor["ip"], dispositivo_id=actor["disp"], es_fraude=True,
                                 user_session=f"fraude-{actor['disp']}-{k}")
                    copia.pop("prioridad", None)
                    yield copia

    return generar(), lista_negra


COLUMNAS_REES46 = ("event_time", "event_type", "product_id", "category_code", "brand", "price",
                   "user_id", "user_session")


def escribir_muestra(ruta, n=1_000, semilla=42):
    """Escribe una muestra con solo las columnas de REES46 (data/sample/eventos.csv).

    Sale del stream completo sin fraude: trae duplicados, inválidos y paquetes
    de compras conjuntas, pero no las etiquetas ni los campos del stream, igual
    que un CSV real. Al leerla, ``aumentar_filas`` le agrega ip, dispositivo,
    medio de pago, prioridad y fraude.

    Uso: python -c "from experimentos.stream_completo import escribir_muestra; escribir_muestra('data/sample/eventos.csv')"
    """
    import csv

    eventos, _ = generar_stream(n, semilla=semilla, prop_fraude=0.0)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS_REES46, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(eventos)
    return len(eventos)
