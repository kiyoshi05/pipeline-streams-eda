class _Nodo:
    def __init__(self):
        self.hijos = {}
        self.palabra = None


class Trie:
    def __init__(self):
        self.raiz = _Nodo()

    def insertar(self, palabra):
        original = palabra.strip()
        normalizada = original.casefold()

        if not normalizada:
            return

        nodo = self.raiz
        for caracter in normalizada:
            nodo = nodo.hijos.setdefault(caracter, _Nodo())

        if nodo.palabra is None:
            nodo.palabra = original

    def autocompletar(self, prefijo, k=10):
        if k < 0:
            raise ValueError("k no puede ser negativo")
        if k == 0:
            return []

        nodo = self.raiz
        for caracter in prefijo.strip().casefold():
            nodo = nodo.hijos.get(caracter)
            if nodo is None:
                return []

        encontrados = []

        def recorrer(actual):
            if len(encontrados) >= k:
                return
            if actual.palabra is not None:
                encontrados.append(actual.palabra)

            for caracter in sorted(actual.hijos):
                if len(encontrados) >= k:
                    break
                recorrer(actual.hijos[caracter])

        recorrer(nodo)
        return encontrados