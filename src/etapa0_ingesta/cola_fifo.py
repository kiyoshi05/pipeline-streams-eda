"""Colas FIFO implementadas a mano para el buffer de ingesta.

ColaFIFO es la estructura principal de la etapa 0: una lista enlazada simple
con punteros a la cabeza y a la cola. BufferCircular es la alternativa con
arreglo de tamaño fijo que se usa como comparación en los benchmarks.

Complejidad de ambas:
    encolar, desencolar, frente, len  -> O(1)
    desencolar_lote(k)                -> O(k)
    espacio                           -> O(n)
"""


class ColaVaciaError(IndexError):
    """Se lanza al desencolar o consultar el frente de una cola vacía."""


class _Nodo:
    # __slots__ evita el diccionario por instancia y reduce la memoria por nodo.
    __slots__ = ("dato", "siguiente")

    def __init__(self, dato):
        self.dato = dato
        self.siguiente = None


class ColaFIFO:
    """Cola FIFO sobre lista enlazada simple.

    Se encola por la cola y se desencola por la cabeza. Como se guardan los
    dos punteros, ninguna operación recorre la lista.

    Si se indica ``capacidad``, ``encolar`` devuelve False cuando la cola está
    llena y no modifica nada; quien produce decide si espera o descarta.
    """

    __slots__ = ("_cabeza", "_cola", "_tamano", "capacidad")

    def __init__(self, capacidad=None):
        if capacidad is not None and capacidad <= 0:
            raise ValueError("la capacidad debe ser positiva o None")
        self._cabeza = None
        self._cola = None
        self._tamano = 0
        self.capacidad = capacidad

    def encolar(self, dato):
        if self.capacidad is not None and self._tamano >= self.capacidad:
            return False
        nodo = _Nodo(dato)
        if self._cola is None:
            self._cabeza = nodo
        else:
            self._cola.siguiente = nodo
        self._cola = nodo
        self._tamano += 1
        return True

    def desencolar(self):
        nodo = self._cabeza
        if nodo is None:
            raise ColaVaciaError("desencolar de una cola vacía")
        self._cabeza = nodo.siguiente
        if self._cabeza is None:
            # Si no se limpia, el siguiente encolar se engancharía a un nodo viejo.
            self._cola = None
        self._tamano -= 1
        return nodo.dato

    def desencolar_lote(self, k):
        """Saca hasta k elementos en orden de llegada (menos si no hay k)."""
        if k < 0:
            raise ValueError("k no puede ser negativo")
        lote = []
        nodo = self._cabeza
        while nodo is not None and len(lote) < k:
            lote.append(nodo.dato)
            nodo = nodo.siguiente
        self._cabeza = nodo
        if nodo is None:
            self._cola = None
        self._tamano -= len(lote)
        return lote

    def frente(self):
        if self._cabeza is None:
            raise ColaVaciaError("frente de una cola vacía")
        return self._cabeza.dato

    def esta_vacia(self):
        return self._tamano == 0

    def esta_llena(self):
        return self.capacidad is not None and self._tamano >= self.capacidad

    def __len__(self):
        return self._tamano

    def __iter__(self):
        """Recorre de la cabeza a la cola sin consumir elementos."""
        nodo = self._cabeza
        while nodo is not None:
            yield nodo.dato
            nodo = nodo.siguiente

    def __repr__(self):
        return f"ColaFIFO(tamano={self._tamano}, capacidad={self.capacidad})"


class BufferCircular:
    """Cola FIFO sobre un arreglo de tamaño fijo con índices que dan la vuelta.

    Usa una sola lista de referencias en lugar de un objeto nodo por elemento,
    por eso gasta menos memoria; a cambio la capacidad es obligatoria.
    """

    __slots__ = ("_datos", "_inicio", "_tamano", "capacidad")

    def __init__(self, capacidad):
        if capacidad is None or capacidad <= 0:
            raise ValueError("el buffer circular necesita una capacidad positiva")
        self._datos = [None] * capacidad
        self._inicio = 0
        self._tamano = 0
        self.capacidad = capacidad

    def encolar(self, dato):
        if self._tamano >= self.capacidad:
            return False
        fin = (self._inicio + self._tamano) % self.capacidad
        self._datos[fin] = dato
        self._tamano += 1
        return True

    def desencolar(self):
        if self._tamano == 0:
            raise ColaVaciaError("desencolar de un buffer vacío")
        dato = self._datos[self._inicio]
        self._datos[self._inicio] = None  # suelta la referencia para no retener memoria
        self._inicio = (self._inicio + 1) % self.capacidad
        self._tamano -= 1
        return dato

    def desencolar_lote(self, k):
        if k < 0:
            raise ValueError("k no puede ser negativo")
        cantidad = min(k, self._tamano)
        return [self.desencolar() for _ in range(cantidad)]

    def frente(self):
        if self._tamano == 0:
            raise ColaVaciaError("frente de un buffer vacío")
        return self._datos[self._inicio]

    def esta_vacia(self):
        return self._tamano == 0

    def esta_llena(self):
        return self._tamano >= self.capacidad

    def __len__(self):
        return self._tamano

    def __iter__(self):
        for i in range(self._tamano):
            yield self._datos[(self._inicio + i) % self.capacidad]

    def __repr__(self):
        return f"BufferCircular(tamano={self._tamano}, capacidad={self.capacidad})"
