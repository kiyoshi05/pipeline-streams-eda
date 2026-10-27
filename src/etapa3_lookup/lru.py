"""Etapa 3: caché LRU (least recently used).

Guarda como máximo ``capacidad`` elementos. Cuando se llena, expulsa el que
lleva más tiempo sin usarse. Se combina:

    TablaHash                    clave -> nodo, para encontrarlo en O(1)
    lista doblemente enlazada    nodos del más reciente (adelante) al más
                                 antiguo (atrás), para moverlo o expulsarlo en O(1)

La lista usa dos centinelas (cabeza y cola) para no tratar casos especiales
cuando está vacía o tiene un solo nodo.

Operaciones:
    obtener (y marcar como reciente)   O(1)
    poner                              O(1), expulsa como mucho un elemento
    eliminar                           O(1)
"""

from src.etapa3_lookup.tabla_hash import TablaHash


class _Nodo:
    __slots__ = ("clave", "valor", "anterior", "siguiente")

    def __init__(self, clave=None, valor=None):
        self.clave = clave
        self.valor = valor
        self.anterior = None
        self.siguiente = None


class CacheLRU:
    """Caché de tamaño fijo que expulsa el elemento usado hace más tiempo."""

    def __init__(self, capacidad):
        if capacidad < 1:
            raise ValueError("la capacidad debe ser al menos 1")
        self.capacidad = capacidad
        self._mapa = TablaHash(capacidad=capacidad * 2)
        self._cabeza = _Nodo()   # centinela: su siguiente es el más reciente
        self._cola = _Nodo()     # centinela: su anterior es el más antiguo
        self._cabeza.siguiente = self._cola
        self._cola.anterior = self._cabeza
        self.aciertos = 0
        self.fallos = 0
        self.expulsiones = 0

    def __len__(self):
        return len(self._mapa)

    def __contains__(self, clave):
        """Consulta si está, sin marcarlo como usado."""
        return clave in self._mapa

    # --- Lista doblemente enlazada ----------------------------------------------

    def _desenganchar(self, nodo):
        nodo.anterior.siguiente = nodo.siguiente
        nodo.siguiente.anterior = nodo.anterior

    def _poner_adelante(self, nodo):
        nodo.anterior = self._cabeza
        nodo.siguiente = self._cabeza.siguiente
        self._cabeza.siguiente.anterior = nodo
        self._cabeza.siguiente = nodo

    # --- Operaciones -----------------------------------------------------------

    def obtener(self, clave, defecto=None):
        """Devuelve el valor y lo marca como el más reciente. Cuenta acierto o fallo."""
        nodo = self._mapa.obtener(clave)
        if nodo is None:
            self.fallos += 1
            return defecto
        self.aciertos += 1
        self._desenganchar(nodo)
        self._poner_adelante(nodo)
        return nodo.valor

    def poner(self, clave, valor):
        """Guarda o actualiza el valor y lo marca como el más reciente.

        Devuelve el par (clave, valor) expulsado si la caché estaba llena, o None.
        """
        nodo = self._mapa.obtener(clave)
        if nodo is not None:
            nodo.valor = valor
            self._desenganchar(nodo)
            self._poner_adelante(nodo)
            return None
        nodo = _Nodo(clave, valor)
        self._mapa.insertar(clave, nodo)
        self._poner_adelante(nodo)
        if len(self._mapa) > self.capacidad:
            viejo = self._cola.anterior
            self._desenganchar(viejo)
            self._mapa.eliminar(viejo.clave)
            self.expulsiones += 1
            return viejo.clave, viejo.valor
        return None

    def eliminar(self, clave):
        """Quita la clave si está (por ejemplo, para invalidar un dato que cambió)."""
        nodo = self._mapa.obtener(clave)
        if nodo is None:
            return False
        self._desenganchar(nodo)
        self._mapa.eliminar(clave)
        return True

    def claves_por_uso(self):
        """Claves del más reciente al más antiguo. O(n); útil para pruebas y el panel."""
        nodo = self._cabeza.siguiente
        while nodo is not self._cola:
            yield nodo.clave
            nodo = nodo.siguiente

    @property
    def tasa_aciertos(self):
        total = self.aciertos + self.fallos
        return self.aciertos / total if total else 0.0
