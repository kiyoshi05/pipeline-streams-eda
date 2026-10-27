"""Etapa 3: tabla hash con encadenamiento separado.

Cada cubeta es una lista de pares [clave, valor]. La cantidad de cubetas es
siempre una potencia de 2 y se duplica cuando el factor de carga (elementos /
cubetas) supera ``carga_maxima``, así las cadenas se mantienen cortas.

El índice de la cubeta usa hashing de Fibonacci: se multiplica hash(clave)
por 2^64 / φ y se toman los bits altos. Con los product_id de REES46, que son
enteros casi consecutivos, tomar solo los bits bajos llenaría cubetas vecinas
de forma desigual; la multiplicación reparte esos bits por todo el número.

Operaciones (promedio, con factor de carga <= 0,75):
    insertar, obtener, contiene, eliminar   O(1)
    redimensionar                            O(n), amortizado O(1) por inserción
    recorrer                                 O(n + cubetas)
Peor caso: O(n) por operación si todas las claves caen en la misma cubeta.
"""

_FIBONACCI = 11400714819323198485  # 2^64 / φ, impar
_MASCARA_64 = (1 << 64) - 1


class TablaHash:
    """Diccionario implementado a mano: clave -> valor."""

    def __init__(self, capacidad=8, carga_maxima=0.75):
        if carga_maxima <= 0:
            raise ValueError("carga_maxima debe ser positiva")
        bits = 3
        while (1 << bits) < capacidad:
            bits += 1
        self._bits = bits
        self._cubetas = [[] for _ in range(1 << bits)]
        self._n = 0
        self.carga_maxima = carga_maxima
        self.redimensionamientos = 0

    # --- Información ---------------------------------------------------------

    def __len__(self):
        return self._n

    @property
    def capacidad(self):
        """Cantidad de cubetas."""
        return len(self._cubetas)

    @property
    def factor_carga(self):
        return self._n / len(self._cubetas)

    def cadena_mas_larga(self):
        """Largo de la cubeta más llena. Sirve para ver si el hash reparte bien."""
        return max((len(c) for c in self._cubetas), default=0)

    # --- Operaciones -----------------------------------------------------------

    def _indice(self, clave):
        return ((hash(clave) * _FIBONACCI) & _MASCARA_64) >> (64 - self._bits)

    def insertar(self, clave, valor):
        """Agrega la clave o reemplaza su valor. O(1) promedio."""
        cubeta = self._cubetas[self._indice(clave)]
        for par in cubeta:
            if par[0] == clave:
                par[1] = valor
                return
        cubeta.append([clave, valor])
        self._n += 1
        if self._n > self.carga_maxima * len(self._cubetas):
            self._redimensionar()

    def obtener(self, clave, defecto=None):
        """Devuelve el valor de la clave, o ``defecto`` si no está. O(1) promedio."""
        for k, v in self._cubetas[self._indice(clave)]:
            if k == clave:
                return v
        return defecto

    def contiene(self, clave):
        for k, _ in self._cubetas[self._indice(clave)]:
            if k == clave:
                return True
        return False

    def eliminar(self, clave):
        """Quita la clave. Devuelve True si estaba. O(1) promedio."""
        cubeta = self._cubetas[self._indice(clave)]
        for i, par in enumerate(cubeta):
            if par[0] == clave:
                cubeta[i] = cubeta[-1]   # el orden dentro de la cubeta no importa
                cubeta.pop()
                self._n -= 1
                return True
        return False

    def _redimensionar(self):
        """Duplica las cubetas y reubica todos los pares. O(n)."""
        viejas = self._cubetas
        self._bits += 1
        self._cubetas = [[] for _ in range(1 << self._bits)]
        for cubeta in viejas:
            for par in cubeta:
                self._cubetas[self._indice(par[0])].append(par)
        self.redimensionamientos += 1

    # --- Recorridos y sintaxis de diccionario ------------------------------------

    def items(self):
        for cubeta in self._cubetas:
            for k, v in cubeta:
                yield k, v

    def claves(self):
        for k, _ in self.items():
            yield k

    def valores(self):
        for _, v in self.items():
            yield v

    def __iter__(self):
        return self.claves()

    def __contains__(self, clave):
        return self.contiene(clave)

    def __getitem__(self, clave):
        for k, v in self._cubetas[self._indice(clave)]:
            if k == clave:
                return v
        raise KeyError(clave)

    def __setitem__(self, clave, valor):
        self.insertar(clave, valor)

    def __delitem__(self, clave):
        if not self.eliminar(clave):
            raise KeyError(clave)
