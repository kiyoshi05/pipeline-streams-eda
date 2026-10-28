"""Etapa 8: ranking de influencia en el grafo de co-compra.

PageRank (Brin y Page, 1998), versión ponderada. Un producto es influyente
si está conectado, con aristas de mucho peso, a otros productos influyentes.
Se calcula con el método de las potencias:

    PR(v) = (1 - d) · p(v)  +  d · Σ_u PR(u) · w(u, v) / W(u)  +  d · C · p(v)

    d      factor de amortiguación (0,85): probabilidad de seguir una arista
    p      vector de teletransporte: uniforme en PageRank clásico, o
           concentrado en algunos productos en Personalized PageRank
    W(u)   suma de pesos de las aristas de u
    C      PageRank acumulado en nodos sin aristas (colgantes); se reparte
           según p para que la suma siga siendo 1

Se itera hasta que el cambio total (norma L1) sea menor que la tolerancia.

Línea base: ranking por grado ponderado, que solo cuenta cuántas compras
conjuntas tiene cada producto, sin mirar quiénes son sus vecinos.

Complejidad:
    pagerank            O(iteraciones · (nodos + aristas)), memoria O(nodos)
    ranking_por_grado   O(nodos + aristas)
    mayores_k           O(n log k) con un heap mínimo de tamaño k
"""

from src.etapa2_prioridad.heap import MinHeap


def pagerank(grafo, amortiguacion=0.85, tolerancia=1e-10, max_iteraciones=200,
             personalizacion=None, estadisticas=None):
    """{nodo: puntaje} con suma 1.

    ``personalizacion`` es un dict {nodo: peso} para Personalized PageRank
    (los nodos que no aparecen reciben 0). Si se pasa un dict en
    ``estadisticas``, se llena con 'iteraciones', 'error' y 'convergio'.
    """
    nodos = list(grafo.nodos())
    n = len(nodos)
    if n == 0:
        return {}
    if not 0 <= amortiguacion < 1:
        raise ValueError("la amortiguación debe estar en [0, 1)")

    if personalizacion:
        total_p = sum(max(0.0, personalizacion.get(u, 0.0)) for u in nodos)
        if total_p <= 0:
            raise ValueError("la personalización no tiene peso en ningún nodo del grafo")
        p = {u: max(0.0, personalizacion.get(u, 0.0)) / total_p for u in nodos}
    else:
        p = {u: 1.0 / n for u in nodos}

    d = amortiguacion
    salida = {u: grafo.grado_ponderado(u) for u in nodos}
    colgantes = [u for u in nodos if salida[u] == 0]
    pr = dict(p) if personalizacion else {u: 1.0 / n for u in nodos}

    error, iteraciones = float("inf"), 0
    while iteraciones < max_iteraciones:
        iteraciones += 1
        masa_colgante = sum(pr[u] for u in colgantes)
        nuevo = {u: (1.0 - d + d * masa_colgante) * p[u] for u in nodos}
        for u in nodos:
            if salida[u]:
                reparto = d * pr[u] / salida[u]
                for v, w in grafo.vecinos(u).items():
                    nuevo[v] += reparto * w
        error = sum(abs(nuevo[u] - pr[u]) for u in nodos)
        pr = nuevo
        if error < tolerancia:
            break

    if estadisticas is not None:
        estadisticas.update(iteraciones=iteraciones, error=error, convergio=error < tolerancia)
    return pr


def ranking_por_grado(grafo, ponderado=True):
    """{nodo: grado}. Con ``ponderado`` suma los pesos; si no, cuenta vecinos."""
    if ponderado:
        return {u: grafo.grado_ponderado(u) for u in grafo.nodos()}
    return {u: grafo.grado(u) for u in grafo.nodos()}


def mayores_k(puntajes, k):
    """Los k pares (nodo, puntaje) de mayor puntaje, de mayor a menor.

    Mantiene un heap mínimo de tamaño k (el MinHeap de la etapa 2): la raíz
    es el peor de los k mejores, y un candidato solo entra si lo supera.
    A igual puntaje gana el nodo con id menor, para que el resultado sea estable.
    """
    if k <= 0:
        return []
    heap = MinHeap()
    for nodo, puntaje in puntajes.items():
        # Clave (puntaje, -id): en empate, el id menor queda "más grande" y sobrevive.
        clave = (puntaje, _desempate(nodo), nodo)
        if len(heap) < k:
            heap.push(clave)
        elif clave > heap.peek():
            heap.pop()
            heap.push(clave)
    ordenados = []
    while len(heap):
        ordenados.append(heap.pop())
    ordenados.reverse()
    return [(nodo, puntaje) for puntaje, _, nodo in ordenados]


def _desempate(nodo):
    try:
        return -nodo
    except TypeError:   # ids que no son números: se ordena por su texto
        return tuple(-ord(c) for c in str(nodo))


def correlacion_rangos(a, b):
    """Correlación de Spearman entre dos rankings {nodo: puntaje} sobre sus nodos comunes.

    Sirve para medir cuánto se parecen PageRank y el ranking por grado. Los
    empates reciben el rango promedio.
    """
    comunes = [u for u in a if u in b]
    n = len(comunes)
    if n < 2:
        return 1.0
    ra = _rangos({u: a[u] for u in comunes})
    rb = _rangos({u: b[u] for u in comunes})
    ma = sum(ra.values()) / n
    mb = sum(rb.values()) / n
    cov = sum((ra[u] - ma) * (rb[u] - mb) for u in comunes)
    va = sum((ra[u] - ma) ** 2 for u in comunes)
    vb = sum((rb[u] - mb) ** 2 for u in comunes)
    if va == 0 or vb == 0:
        return 1.0 if va == vb else 0.0
    return cov / (va * vb) ** 0.5


def _rangos(puntajes):
    orden = sorted(puntajes, key=lambda u: puntajes[u])
    rangos = {}
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and puntajes[orden[j + 1]] == puntajes[orden[i]]:
            j += 1
        promedio = (i + j) / 2 + 1
        for u in orden[i:j + 1]:
            rangos[u] = promedio
        i = j + 1
    return rangos
