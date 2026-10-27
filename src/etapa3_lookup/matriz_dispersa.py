"""Etapa 3: matriz dispersa usuario x producto.

Con millones de usuarios y cientos de miles de productos, una matriz densa
no cabe en memoria, y casi todas sus celdas serían 0: cada usuario toca unos
pocos productos. Solo se guardan las celdas distintas de 0 (formato DOK,
"diccionario de claves"), con dos índices para leer en O(1) tanto una fila
como una columna:

    filas      usuario  -> {producto: valor}
    columnas   producto -> {usuario: valor}

Cada valor se guarda dos veces (una por índice): se paga el doble de memoria
para que "productos de un usuario" y "usuarios de un producto" cuesten lo
mismo. La etapa 7 usa las columnas para la similitud de Jaccard (MinHash).

Operaciones:
    sumar, asignar, obtener               O(1) promedio
    fila(u), columna(p)                   O(1) para obtenerla, O(k) para recorrerla
    conjuntos_por_columna                 O(nnz)
    coseno / jaccard entre dos columnas   O(min(k1, k2))
Memoria: O(nnz), donde nnz es la cantidad de celdas distintas de 0.

Los índices usan dict de Python, que también es una tabla hash: con millones
de celdas es bastante más rápido que la TablaHash escrita en Python, y la
complejidad es la misma.
"""

import math


class MatrizDispersa:
    """Matriz con solo las celdas distintas de 0."""

    def __init__(self):
        self._filas = {}
        self._columnas = {}
        self._nnz = 0

    # --- Escritura --------------------------------------------------------------

    def asignar(self, fila, columna, valor):
        """Fija el valor de una celda. Asignar 0 la elimina."""
        celdas = self._filas.get(fila)
        existia = celdas is not None and columna in celdas
        if valor == 0:
            if existia:
                del celdas[columna]
                del self._columnas[columna][fila]
                if not celdas:
                    del self._filas[fila]
                if not self._columnas[columna]:
                    del self._columnas[columna]
                self._nnz -= 1
            return
        self._filas.setdefault(fila, {})[columna] = valor
        self._columnas.setdefault(columna, {})[fila] = valor
        if not existia:
            self._nnz += 1

    def sumar(self, fila, columna, valor=1.0):
        """Suma ``valor`` a la celda. Si el resultado es 0, la celda se elimina."""
        self.asignar(fila, columna, self.obtener(fila, columna) + valor)

    # --- Lectura -------------------------------------------------------------------

    def obtener(self, fila, columna, defecto=0.0):
        celdas = self._filas.get(fila)
        if celdas is None:
            return defecto
        return celdas.get(columna, defecto)

    def fila(self, fila):
        """Celdas de una fila como {columna: valor}. Es una copia: modificarla no cambia la matriz."""
        return dict(self._filas.get(fila, {}))

    def columna(self, columna):
        """Celdas de una columna como {fila: valor} (copia)."""
        return dict(self._columnas.get(columna, {}))

    def filas(self):
        return self._filas.keys()

    def columnas(self):
        return self._columnas.keys()

    @property
    def nnz(self):
        """Cantidad de celdas distintas de 0."""
        return self._nnz

    @property
    def forma(self):
        """(filas con datos, columnas con datos)."""
        return len(self._filas), len(self._columnas)

    @property
    def densidad(self):
        """Fracción de celdas ocupadas. En datos de comercio electrónico es muy baja."""
        n_filas, n_columnas = self.forma
        return self._nnz / (n_filas * n_columnas) if n_filas and n_columnas else 0.0

    def items(self):
        """Recorre (fila, columna, valor) de todas las celdas distintas de 0."""
        for f, celdas in self._filas.items():
            for c, v in celdas.items():
                yield f, c, v

    # --- Para la etapa 7 (similitud) -------------------------------------------------

    def conjuntos_por_columna(self, minimo=None):
        """{columna: conjunto de filas}. Con ``minimo`` solo cuenta celdas con valor >= minimo.

        Con usuarios en las filas y productos en las columnas da, para cada
        producto, el conjunto de usuarios que interactuó con él: la entrada
        de MinHash + LSH.
        """
        return {
            c: {f for f, v in celdas.items() if minimo is None or v >= minimo}
            for c, celdas in self._columnas.items()
            if minimo is None or any(v >= minimo for v in celdas.values())
        }

    def jaccard_columnas(self, c1, c2):
        """|A ∩ B| / |A ∪ B| entre los conjuntos de filas de dos columnas."""
        a = self._columnas.get(c1, {})
        b = self._columnas.get(c2, {})
        if not a and not b:
            return 0.0
        if len(a) > len(b):
            a, b = b, a
        comunes = sum(1 for f in a if f in b)
        return comunes / (len(a) + len(b) - comunes)

    def coseno_columnas(self, c1, c2):
        """Similitud coseno entre dos columnas, usando los valores."""
        a = self._columnas.get(c1, {})
        b = self._columnas.get(c2, {})
        if not a or not b:
            return 0.0
        chico, grande = (a, b) if len(a) <= len(b) else (b, a)
        punto = sum(v * grande[f] for f, v in chico.items() if f in grande)
        norma = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
        return punto / norma if norma else 0.0
