"""Etapa 4: B+Tree para un índice ordenado.

Un B+Tree guarda las claves ordenadas en nodos con muchos hijos. Simula un
índice de disco: cada nodo sería una página, y el ``orden`` es cuántos hijos
caben en ella. Con orden 64 y 1M de claves, una búsqueda lee solo 4 o 5 nodos.

    nodos internos   solo claves separadoras e hijos; sirven para bajar
    hojas            todas las claves con sus valores, enlazadas de izquierda
                     a derecha; una consulta por rango baja una sola vez y
                     después recorre hojas vecinas

Una clave puede tener varios valores (por ejemplo, varios productos con el
mismo precio): cada clave guarda una lista. ``len`` cuenta valores.

Regla para bajar: en un nodo interno con separadores s0 < s1 < ..., la clave
x va al hijo i = cantidad de separadores <= x. Al partir una hoja, su primera
clave de la derecha se copia arriba como separador.

Borrado perezoso: eliminar quita el valor y, si la clave se queda sin
valores, la quita de su hoja, pero no fusiona ni redistribuye nodos. Las
búsquedas siguen siendo correctas y la altura nunca crece por borrar; el
costo es que algunas hojas pueden quedar medio vacías. En este pipeline casi
no se borra (solo cuando cambia el precio de un producto), así que conviene.

Operaciones (n claves, orden b):
    buscar, insertar      O(log_b n) nodos visitados, O(log n) comparaciones
    rango con m valores   O(log_b n + m)
    eliminar              O(log_b n)
    altura                ≈ log_b n
"""

from bisect import bisect_left, bisect_right


class _Hoja:
    __slots__ = ("claves", "valores", "siguiente")

    def __init__(self):
        self.claves = []
        self.valores = []      # valores[i] es la lista de valores de claves[i]
        self.siguiente = None


class _Interno:
    __slots__ = ("claves", "hijos")

    def __init__(self):
        self.claves = []
        self.hijos = []


class BPlusTree:
    """Índice ordenado clave -> lista de valores."""

    def __init__(self, orden=64):
        if orden < 3:
            raise ValueError("el orden debe ser al menos 3")
        self.orden = orden
        self._max_claves = orden - 1
        self._raiz = _Hoja()
        self._n_valores = 0
        self._n_claves = 0
        self._altura = 1
        self.nodos_leidos = 0   # nodos visitados en la última búsqueda (lecturas de página)

    # --- Información ---------------------------------------------------------

    def __len__(self):
        return self._n_valores

    @property
    def n_claves(self):
        return self._n_claves

    @property
    def altura(self):
        """Niveles del árbol: 1 si la raíz es una hoja."""
        return self._altura

    # --- Bajar hasta una hoja -----------------------------------------------------

    def _hoja_de(self, clave, camino=None):
        nodo = self._raiz
        leidos = 1
        while isinstance(nodo, _Interno):
            i = bisect_right(nodo.claves, clave)
            if camino is not None:
                camino.append((nodo, i))
            nodo = nodo.hijos[i]
            leidos += 1
        self.nodos_leidos = leidos
        return nodo

    # --- Búsqueda -------------------------------------------------------------------

    def buscar(self, clave):
        """Lista (copia) de los valores de la clave; vacía si no está."""
        hoja = self._hoja_de(clave)
        i = bisect_left(hoja.claves, clave)
        if i < len(hoja.claves) and hoja.claves[i] == clave:
            return list(hoja.valores[i])
        return []

    def __contains__(self, clave):
        return bool(self.buscar(clave))

    def rango(self, desde=None, hasta=None, incluir_hasta=True):
        """Recorre (clave, valor) con desde <= clave <= hasta, en orden.

        ``None`` en un extremo deja ese lado abierto. Con ``incluir_hasta=False``
        el extremo derecho es exclusivo.
        """
        if desde is None:
            hoja, i = self._hoja_mas_izquierda(), 0
        else:
            hoja = self._hoja_de(desde)
            i = bisect_left(hoja.claves, desde)
        while hoja is not None:
            claves = hoja.claves
            while i < len(claves):
                k = claves[i]
                if hasta is not None and (k > hasta or (k == hasta and not incluir_hasta)):
                    return
                for v in hoja.valores[i]:
                    yield k, v
                i += 1
            hoja, i = hoja.siguiente, 0

    def _hoja_mas_izquierda(self):
        nodo = self._raiz
        while isinstance(nodo, _Interno):
            nodo = nodo.hijos[0]
        return nodo

    def items(self):
        return self.rango()

    def __iter__(self):
        """Claves distintas en orden."""
        hoja = self._hoja_mas_izquierda()
        while hoja is not None:
            yield from hoja.claves
            hoja = hoja.siguiente

    def minimo(self):
        for k in self:
            return k
        raise ValueError("el índice está vacío")

    def maximo(self):
        nodo = self._raiz
        while isinstance(nodo, _Interno):
            nodo = nodo.hijos[-1]
        # con borrado perezoso la última hoja puede quedar vacía: se recorre desde la izquierda
        if nodo.claves:
            return nodo.claves[-1]
        ultimo = None
        for k in self:
            ultimo = k
        if ultimo is None:
            raise ValueError("el índice está vacío")
        return ultimo

    # --- Inserción ----------------------------------------------------------------------

    def insertar(self, clave, valor):
        """Agrega el valor a la clave (la crea si no existe)."""
        camino = []
        hoja = self._hoja_de(clave, camino)
        i = bisect_left(hoja.claves, clave)
        self._n_valores += 1
        if i < len(hoja.claves) and hoja.claves[i] == clave:
            hoja.valores[i].append(valor)
            return
        hoja.claves.insert(i, clave)
        hoja.valores.insert(i, [valor])
        self._n_claves += 1
        if len(hoja.claves) > self._max_claves:
            self._partir_hoja(hoja, camino)

    def _partir_hoja(self, hoja, camino):
        mitad = len(hoja.claves) // 2
        nueva = _Hoja()
        nueva.claves = hoja.claves[mitad:]
        nueva.valores = hoja.valores[mitad:]
        del hoja.claves[mitad:]
        del hoja.valores[mitad:]
        nueva.siguiente = hoja.siguiente
        hoja.siguiente = nueva
        self._subir(nueva.claves[0], nueva, camino)   # la clave se copia arriba

    def _partir_interno(self, nodo, camino):
        mitad = len(nodo.claves) // 2
        separador = nodo.claves[mitad]                 # la clave del medio sube (no se copia)
        nuevo = _Interno()
        nuevo.claves = nodo.claves[mitad + 1:]
        nuevo.hijos = nodo.hijos[mitad + 1:]
        del nodo.claves[mitad:]
        del nodo.hijos[mitad + 1:]
        self._subir(separador, nuevo, camino)

    def _subir(self, separador, nodo_derecho, camino):
        """Inserta el separador y el nuevo hijo derecho en el padre; parte el padre si se llena."""
        if not camino:
            raiz = _Interno()
            raiz.claves = [separador]
            raiz.hijos = [self._raiz, nodo_derecho]
            self._raiz = raiz
            self._altura += 1
            return
        padre, i = camino.pop()
        padre.claves.insert(i, separador)
        padre.hijos.insert(i + 1, nodo_derecho)
        if len(padre.claves) > self._max_claves:
            self._partir_interno(padre, camino)

    # --- Borrado (perezoso) -------------------------------------------------------------------

    def eliminar(self, clave, valor=None):
        """Quita un valor de la clave (o todos si ``valor`` es None). Devuelve cuántos quitó."""
        hoja = self._hoja_de(clave)
        i = bisect_left(hoja.claves, clave)
        if i >= len(hoja.claves) or hoja.claves[i] != clave:
            return 0
        valores = hoja.valores[i]
        if valor is None:
            quitados = len(valores)
            valores.clear()
        else:
            try:
                valores.remove(valor)
            except ValueError:
                return 0
            quitados = 1
        self._n_valores -= quitados
        if not valores:
            del hoja.claves[i]
            del hoja.valores[i]
            self._n_claves -= 1
        return quitados

    # --- Verificación (para pruebas) ---------------------------------------------------------

    def verificar(self):
        """Lanza AssertionError si el árbol no cumple sus invariantes."""
        profundidades = set()

        def revisar(nodo, minimo, maximo, profundidad, es_raiz):
            assert nodo.claves == sorted(nodo.claves), "claves desordenadas"
            assert len(nodo.claves) <= self._max_claves, "nodo con demasiadas claves"
            for k in nodo.claves:
                assert minimo is None or k >= minimo, "clave menor que su separador"
                assert maximo is None or k < maximo, "clave mayor que su separador"
            if isinstance(nodo, _Hoja):
                assert len(nodo.claves) == len(nodo.valores)
                profundidades.add(profundidad)
                return
            assert len(nodo.hijos) == len(nodo.claves) + 1, "hijos y claves no cuadran"
            assert es_raiz or len(nodo.hijos) >= 2
            limites = [minimo] + nodo.claves + [maximo]
            for j, hijo in enumerate(nodo.hijos):
                revisar(hijo, limites[j], limites[j + 1], profundidad + 1, False)

        revisar(self._raiz, None, None, 1, True)
        assert profundidades == {self._altura}, "las hojas no están todas al mismo nivel"
        claves = list(self)
        assert claves == sorted(set(claves)), "la cadena de hojas no está ordenada"
        assert len(claves) == self._n_claves
        assert sum(1 for _ in self.items()) == self._n_valores
