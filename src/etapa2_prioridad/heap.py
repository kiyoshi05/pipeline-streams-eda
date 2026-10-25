"""Etapa 2: heap mínimo implementado sobre una lista.

Para el nodo en la posición i:
    padre            (i - 1) // 2
    hijo izquierdo   2*i + 1
    hijo derecho     2*i + 2

Operaciones:
    len       O(1)
    peek      O(1)
    push      O(log n)
    pop       O(log n)
    heapify   O(n)
"""


class MinHeap:
    """Heap mínimo: el elemento más pequeño siempre está en la posición 0."""

    def __init__(self, elementos=None):
        self._datos = []
        if elementos:
            self._datos = list(elementos)
            self.heapify()

    def __len__(self):
        """Cantidad de elementos. Permite escribir len(h)."""
        return len(self._datos)

    def peek(self):
        """Devuelve el mínimo sin sacarlo. O(1)."""
        if not self._datos:
            raise IndexError("peek en un heap vacío")
        return self._datos[0]

    def push(self, elemento):
        """Inserta un elemento. O(log n)."""
        self._datos.append(elemento)
        self._subir(len(self._datos) - 1)

    def pop(self):
        """Saca y devuelve el mínimo. O(log n)."""
        if not self._datos:
            raise IndexError("pop en un heap vacío")
        minimo = self._datos[0]
        ultimo = self._datos.pop()
        if self._datos:
            self._datos[0] = ultimo
            self._bajar(0)
        return minimo

    def heapify(self):
        """Acomoda self._datos para que cumpla la regla del heap. O(n)."""
        for i in range(len(self._datos) // 2 - 1, -1, -1):
            self._bajar(i)

    # --- Métodos internos -------------------------------------------------

    def _subir(self, i):
        """Sube el elemento de la posición i mientras sea menor que su padre."""
        datos = self._datos
        while i > 0:
            padre = (i - 1) // 2
            if datos[i] < datos[padre]:
                datos[i], datos[padre] = datos[padre], datos[i]
                i = padre
            else:
                break

    def _bajar(self, i):
        """Baja el elemento de la posición i mientras sea mayor que algún hijo."""
        datos = self._datos
        n = len(datos)
        while True:
            izq = 2 * i + 1
            der = 2 * i + 2
            menor = i
            if izq < n and datos[izq] < datos[menor]:
                menor = izq
            if der < n and datos[der] < datos[menor]:
                menor = der
            if menor == i:
                break
            datos[i], datos[menor] = datos[menor], datos[i]
            i = menor