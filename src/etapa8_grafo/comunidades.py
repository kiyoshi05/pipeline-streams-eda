"""Etapa 8: detección de comunidades en el grafo de co-compra.

Una comunidad es un grupo de productos que se compran mucho entre sí y poco
con el resto: sirve para agrupaciones de consumo y cross-selling.

Modularidad (Newman), con m = peso total de las aristas:

    Q = Σ_c [ L_c / m  -  (D_c / 2m)² ]

    L_c   peso de las aristas dentro de la comunidad c
    D_c   suma de los grados ponderados de los nodos de c

Q compara las aristas internas con las que se esperarían al azar: 0 es
como el azar, y valores sobre 0,3 indican comunidades claras.

Louvain (Blondel et al., 2008), el método elegido:
    1. Cada nodo empieza solo. Se recorren los nodos y cada uno se mueve a la
       comunidad vecina que más aumenta Q; se repite hasta que nadie se mueve.
    2. Cada comunidad se convierte en un nodo (las aristas internas pasan a
       ser un lazo) y se vuelve al paso 1 con ese grafo más chico.
    Termina cuando una pasada completa no mueve ningún nodo.
    Complejidad: O(m) por pasada en la práctica; casi lineal en total.

Label Propagation (Raghavan et al., 2007), la alternativa más simple:
    Cada nodo empieza con su propia etiqueta y toma, una y otra vez, la
    etiqueta con más peso entre sus vecinos (empates al azar). Termina cuando
    ningún nodo cambia. No optimiza Q explícitamente: es más rápido pero da
    resultados que cambian más de una semilla a otra.
    Complejidad: O(m) por iteración, pocas iteraciones.

Las particiones se devuelven como {nodo: comunidad}, con comunidades
numeradas 0, 1, 2... de la más grande a la más chica.
"""

import math
import random
from collections import Counter


# --- Modularidad y resúmenes ------------------------------------------------------

def modularidad(grafo, particion):
    """Modularidad ponderada de una partición {nodo: comunidad}."""
    m = grafo.peso_total
    if m == 0:
        return 0.0
    internas = Counter()
    grados = Counter()
    for u in grafo.nodos():
        c = particion[u]
        for v, w in grafo.vecinos(u).items():
            grados[c] += w
            if particion[v] == c:
                internas[c] += w   # cada arista interna se cuenta dos veces (u-v y v-u)
    return sum(internas[c] / (2 * m) - (grados[c] / (2 * m)) ** 2 for c in grados)


def resumen(particion):
    """Cantidad de comunidades y tamaños de mayor a menor."""
    tamanos = sorted(Counter(particion.values()).values(), reverse=True)
    return {"comunidades": len(tamanos), "tamanos": tamanos}


def renumerar(particion):
    """Numera las comunidades 0, 1, 2... de la más grande a la más chica (empate: menor id de nodo)."""
    miembros = {}
    for u, c in particion.items():
        miembros.setdefault(c, []).append(u)
    orden = sorted(miembros.values(), key=lambda grupo: (-len(grupo), min(map(_clave_orden, grupo))))
    return {u: i for i, grupo in enumerate(orden) for u in grupo}


def _clave_orden(u):
    return (0, u) if isinstance(u, (int, float)) else (1, str(u))


def informacion_mutua_normalizada(p1, p2):
    """NMI entre dos particiones de los mismos nodos: 1 = idénticas, 0 = independientes.

    Mide la estabilidad: se corre el algoritmo con semillas distintas y se
    comparan los resultados.
    """
    nodos = [u for u in p1 if u in p2]
    n = len(nodos)
    if n == 0:
        return 1.0
    ca = Counter(p1[u] for u in nodos)
    cb = Counter(p2[u] for u in nodos)
    conjunta = Counter((p1[u], p2[u]) for u in nodos)
    ha = -sum(c / n * math.log(c / n) for c in ca.values())
    hb = -sum(c / n * math.log(c / n) for c in cb.values())
    if ha == 0 and hb == 0:
        return 1.0
    im = sum(c / n * math.log((c / n) / ((ca[a] / n) * (cb[b] / n))) for (a, b), c in conjunta.items())
    return 2 * im / (ha + hb)


# --- Label Propagation -----------------------------------------------------------------

def label_propagation(grafo, semilla=42, max_iteraciones=100, estadisticas=None):
    """Comunidades por propagación de etiquetas (asíncrona y ponderada)."""
    azar = random.Random(semilla)
    nodos = list(grafo.nodos())
    etiqueta = {u: i for i, u in enumerate(nodos)}
    iteraciones = 0
    for iteraciones in range(1, max_iteraciones + 1):
        azar.shuffle(nodos)
        cambios = 0
        for u in nodos:
            vecinos = grafo.vecinos(u)
            if not vecinos:
                continue
            pesos = Counter()
            for v, w in vecinos.items():
                pesos[etiqueta[v]] += w
            mejor = max(pesos.values())
            candidatas = [e for e, w in pesos.items() if w == mejor]
            if etiqueta[u] in candidatas:
                continue   # conservar la propia en un empate ayuda a que converja
            etiqueta[u] = candidatas[0] if len(candidatas) == 1 else azar.choice(sorted(candidatas))
            cambios += 1
        if cambios == 0:
            break
    if estadisticas is not None:
        estadisticas.update(iteraciones=iteraciones)
    return renumerar(etiqueta)


# --- Louvain ---------------------------------------------------------------------------------

def louvain(grafo, semilla=42, tolerancia=1e-12, estadisticas=None):
    """Comunidades por el método de Louvain (maximiza la modularidad)."""
    azar = random.Random(semilla)
    # Grafo de trabajo: {u: {v: peso}}, simétrico. Los lazos (u, u) aparecen
    # al agregar comunidades y guardan el peso interno una sola vez.
    ady = grafo.adyacencia()
    pertenencia = {u: u for u in ady}   # nodo original -> nodo del nivel actual
    niveles = 0
    while True:
        comunidad, movidos = _fase_local(ady, azar, tolerancia)
        niveles += 1
        pertenencia = {u: comunidad[c] for u, c in pertenencia.items()}
        if not movidos or len(set(comunidad.values())) == len(ady):
            break
        ady = _agregar(ady, comunidad)
    if estadisticas is not None:
        estadisticas.update(niveles=niveles)
    return renumerar(pertenencia)


def _grado(ady, u):
    """Grado ponderado; un lazo cuenta doble, como en la suma de grados = 2m."""
    return sum(w * 2 if v == u else w for v, w in ady[u].items())


def _fase_local(ady, azar, tolerancia):
    """Fase 1: mueve nodos entre comunidades vecinas mientras suba la modularidad."""
    k = {u: _grado(ady, u) for u in ady}
    dos_m = sum(k.values())
    comunidad = {u: u for u in ady}
    if dos_m == 0:
        return comunidad, False
    total = dict(k)          # suma de grados de cada comunidad
    orden = list(ady)
    azar.shuffle(orden)
    hubo_movimientos = False
    mejora = True
    while mejora:
        mejora = False
        for u in orden:
            actual = comunidad[u]
            hacia = Counter()   # peso de u hacia cada comunidad vecina
            for v, w in ady[u].items():
                if v != u:
                    hacia[comunidad[v]] += w
            total[actual] -= k[u]   # sacar u de su comunidad
            # Ganancia de entrar a c (salvo constantes): k_u,in(c) - total(c)·k_u / 2m
            mejor, ganancia_mejor = actual, hacia[actual] - total[actual] * k[u] / dos_m
            for c, w_in in hacia.items():
                ganancia = w_in - total[c] * k[u] / dos_m
                if ganancia > ganancia_mejor + tolerancia:
                    mejor, ganancia_mejor = c, ganancia
            total[mejor] += k[u]
            if mejor != actual:
                comunidad[u] = mejor
                mejora = True
                hubo_movimientos = True
    return comunidad, hubo_movimientos


def _agregar(ady, comunidad):
    """Fase 2: cada comunidad pasa a ser un nodo; las aristas internas, un lazo."""
    nuevo = {c: {} for c in set(comunidad.values())}
    for u, vecinos in ady.items():
        cu = comunidad[u]
        for v, w in vecinos.items():
            cv = comunidad[v]
            if u == v:
                aporte = w              # el lazo aparece una sola vez
            elif cu == cv:
                aporte = w / 2          # la arista interna aparece dos veces (u-v y v-u)
            else:
                aporte = w              # se suma una vez en nuevo[cu][cv] y otra en nuevo[cv][cu]
            nuevo[cu][cv] = nuevo[cu].get(cv, 0.0) + aporte
    return nuevo
