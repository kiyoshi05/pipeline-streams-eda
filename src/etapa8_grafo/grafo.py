"""Etapa 8: grafo de co-compra.

Nodos = productos. Dos productos quedan unidos si se compraron en la misma
orden, y el peso de la arista cuenta en cuántas órdenes ocurrió. Como REES46
no trae un identificador de orden, se usa ``user_session``: las compras de
una misma sesión forman una orden.

El grafo es no dirigido y se guarda como lista de adyacencia con pesos:

    producto -> {vecino: peso}

Cada arista aparece dos veces (u->v y v->u) con el mismo peso.

Operaciones:
    agregar_arista              O(1) promedio
    agregar_orden con k items   O(k²): une todos los pares
    vecinos(u)                  O(1) para obtenerlos, O(grado) para recorrerlos
Memoria: O(nodos + aristas).
"""

from itertools import combinations


class GrafoCoCompra:
    """Grafo no dirigido y ponderado de productos comprados juntos."""

    def __init__(self):
        self._ady = {}
        self._n_aristas = 0
        self._peso_total = 0.0
        self.version = 0   # cambia con cada modificación; sirve para invalidar resultados guardados

    # --- Construcción -------------------------------------------------------------

    def agregar_nodo(self, u):
        if u not in self._ady:
            self._ady[u] = {}
            self.version += 1

    def agregar_arista(self, u, v, peso=1.0):
        """Suma ``peso`` a la arista u-v (la crea si no existe). No se permiten lazos."""
        if u == v:
            raise ValueError("un producto no forma arista consigo mismo")
        self.agregar_nodo(u)
        self.agregar_nodo(v)
        if v not in self._ady[u]:
            self._n_aristas += 1
            self._ady[u][v] = 0.0
            self._ady[v][u] = 0.0
        self._ady[u][v] += peso
        self._ady[v][u] += peso
        self._peso_total += peso
        self.version += 1

    def agregar_orden(self, productos, peso=1.0):
        """Une todos los pares de productos distintos de una orden."""
        distintos = list(dict.fromkeys(productos))   # sin repetidos, conservando el orden
        for p in distintos:
            self.agregar_nodo(p)
        for u, v in combinations(distintos, 2):
            self.agregar_arista(u, v, peso)

    # --- Consultas --------------------------------------------------------------------

    def nodos(self):
        return self._ady.keys()

    def vecinos(self, u):
        """{vecino: peso}. No copiar ni modificar: es la estructura interna."""
        return self._ady.get(u, {})

    def peso(self, u, v):
        return self._ady.get(u, {}).get(v, 0.0)

    def grado(self, u):
        """Cantidad de vecinos."""
        return len(self._ady.get(u, {}))

    def grado_ponderado(self, u):
        """Suma de los pesos de las aristas de u."""
        return sum(self._ady.get(u, {}).values())

    def aristas(self):
        """Recorre (u, v, peso) una vez por arista."""
        vistos = set()
        for u, vecinos in self._ady.items():
            vistos.add(u)
            for v, w in vecinos.items():
                if v not in vistos:
                    yield u, v, w

    def __contains__(self, u):
        return u in self._ady

    def __len__(self):
        return len(self._ady)

    @property
    def n_nodos(self):
        return len(self._ady)

    @property
    def n_aristas(self):
        return self._n_aristas

    @property
    def peso_total(self):
        """Suma de los pesos de todas las aristas (cada arista una vez)."""
        return self._peso_total

    def adyacencia(self):
        """Copia de la lista de adyacencia: {u: {v: peso}}."""
        return {u: dict(vecinos) for u, vecinos in self._ady.items()}

    @classmethod
    def desde_adyacencia(cls, adyacencia):
        """Construye un grafo a partir de {u: {v: peso}} (simétrico o no: se suma una vez por par)."""
        g = cls()
        for u in adyacencia:
            g.agregar_nodo(u)
        for u, vecinos in adyacencia.items():
            for v, w in vecinos.items():
                if u != v and g.peso(u, v) == 0.0:
                    g.agregar_arista(u, v, w)
        return g
