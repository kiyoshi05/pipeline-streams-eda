"""Etapa 2: cola con prioridades.

Recibe un lote limpio y ordenado por tiempo, ya revisado por el detector de
fraude de la etapa 6, y entrega a la etapa 3 los eventos en orden de urgencia.
Usa el MinHeap de heap.py con la clave (prioridad, event_time, contador, evento):

    prioridad    menor número = más urgente
    event_time   a igual prioridad, sale primero el más antiguo
    contador     a igual tiempo, se respeta el orden de llegada; además
                 evita que Python compare dos eventos (dict) entre sí

Operaciones:
    recibir(eventos)   O(n log n) para n eventos
    extraer(k)         O(k log n)
    siguiente()        O(log n)
"""

from src.etapa1_preprocesamiento.preprocesamiento import campo, con_cambios
from src.etapa2_prioridad.heap import MinHeap

FRAUDE_O_PAGO = 0
EXPRESS = 1
ESTANDAR = 2
BAJA = 3
NOMBRES = {
    FRAUDE_O_PAGO: "fraude_o_pago",
    EXPRESS: "express",
    ESTANDAR: "estandar",
    BAJA: "baja",
}
_VERDADEROS = frozenset({"1", "true", "t", "si", "sí", "yes", "y"})


def _es_verdadero(valor):
    if isinstance(valor, str):
        return valor.strip().lower() in _VERDADEROS
    return bool(valor)


def _prioridad_valida(valor):
    """Devuelve la prioridad como entero si está entre 0 y 3; si no, None."""
    try:
        p = int(valor)
    except (TypeError, ValueError):
        return None
    return p if p in NOMBRES else None


def asignar_prioridad(evento):
    """Prioridad de 0 (más urgente) a 3.

    1. Si el evento trae 'prioridad' válida (la pone el generador), se usa.
    2. Si la etapa 6 lo marcó como fraude (fraude_predicho): FRAUDE_O_PAGO.
    3. Si es una compra (purchase): ESTANDAR.
    4. Cualquier otro (view, cart, remove_from_cart): BAJA.

    Nunca se mira es_fraude: es la etiqueta de verdad del generador sintético
    y solo sirve para medir aciertos. Priorizar con ella sería usar la
    respuesta correcta, que en producción no existe.
    """
    p = _prioridad_valida(campo(evento, "prioridad"))
    if p is not None:
        return p
    if _es_verdadero(campo(evento, "fraude_predicho", False)):
        return FRAUDE_O_PAGO
    if campo(evento, "event_type") == "purchase":
        return ESTANDAR
    return BAJA


class Etapa2Prioridad:
    """Cola con prioridades entre la etapa 1 y la etapa 3."""

    def __init__(self):
        self._heap = MinHeap()
        self._contador = 0
        self._recibidos = 0
        self._entregados = 0
        self._por_prioridad = {p: 0 for p in NOMBRES}

    def __len__(self):
        """Eventos que esperan en la cola."""
        return len(self._heap)

    def esta_vacia(self):
        return len(self._heap) == 0

    def recibir(self, eventos):
        """Mete un lote de eventos al heap. Devuelve cuántos recibió.

        Si el evento no trae 'prioridad', se le agrega en una copia, así la
        etapa 3 sabe con qué urgencia llegó cada uno. La entrada no se modifica.
        """
        n = 0
        for evento in eventos:
            p = asignar_prioridad(evento)
            if _prioridad_valida(campo(evento, "prioridad")) != p:
                evento = con_cambios(evento, {"prioridad": p})
            self._heap.push((p, campo(evento, "event_time", 0), self._contador, evento))
            self._contador += 1
            self._por_prioridad[p] += 1
            n += 1
        self._recibidos += n
        return n

    def siguiente(self):
        """Saca el evento más urgente. Lanza IndexError si la cola está vacía."""
        if self.esta_vacia():
            raise IndexError("la cola de prioridades está vacía")
        self._entregados += 1
        return self._heap.pop()[3]

    def extraer(self, k=None):
        """Saca hasta k eventos, del más urgente al menos urgente.

        Con k=None saca todos. Si hay menos de k, devuelve los que haya.
        """
        if k is None or k > len(self._heap):
            k = len(self._heap)
        return [self.siguiente() for _ in range(k)]

    def metricas(self):
        return {
            "recibidos": self._recibidos,
            "entregados": self._entregados,
            "en_cola": len(self._heap),
            "por_prioridad": {NOMBRES[p]: c for p, c in self._por_prioridad.items()},
        }
