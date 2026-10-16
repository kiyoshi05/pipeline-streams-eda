"""Etapa 0: recibe el stream de eventos, lo guarda en un buffer FIFO y lo
entrega por lotes a la etapa 1.

La etapa no limpia ni transforma eventos: solo garantiza que salen en el mismo
orden en que llegaron y en lotes de tamaño fijo (el último puede ser menor).
"""

import csv

from src.etapa0_ingesta.cola_fifo import BufferCircular, ColaFIFO

# Campos de REES46 que forman parte del contrato del Evento.
CAMPOS_EVENTO = (
    "event_time",
    "event_type",
    "product_id",
    "category_code",
    "brand",
    "price",
    "user_id",
    "user_session",
)


def leer_csv(ruta, limite=None, campos=CAMPOS_EVENTO, a_evento=None, codificacion="utf-8"):
    """Lee un CSV fila por fila, sin cargarlo entero en memoria.

    Cada fila se reduce a ``campos`` (REES46 trae además ``category_id``, que
    no está en el contrato). Si se pasa ``a_evento`` se aplica a cada fila,
    por ejemplo ``lambda d: Evento(**d)`` con la clase de src/comun/evento.py.
    """
    with open(ruta, newline="", encoding=codificacion) as archivo:
        lector = csv.DictReader(archivo)
        faltan = [c for c in campos if c not in (lector.fieldnames or ())]
        if faltan:
            raise ValueError(f"al CSV le faltan las columnas {faltan}")
        for i, fila in enumerate(lector):
            if limite is not None and i >= limite:
                break
            registro = {c: fila[c] for c in campos}
            yield a_evento(registro) if a_evento is not None else registro


class Etapa0Ingesta:
    """Buffer de entrada del pipeline.

    - ``capacidad``: máximo de eventos que el buffer retiene a la vez.
    - ``tam_lote``: cantidad de eventos que se entregan a la etapa 1 por lote.
    - ``estructura``: "lista" (ColaFIFO, la implementación principal) o
      "circular" (BufferCircular, la alternativa).

    Política de buffer lleno: ``recibir`` devuelve False y no pierde nada;
    ``procesar_stream`` responde entregando un lote para liberar espacio
    (contrapresión) y cuenta cuántas veces ocurrió.
    """

    def __init__(self, capacidad=10_000, tam_lote=1_000, estructura="lista"):
        if tam_lote <= 0:
            raise ValueError("tam_lote debe ser positivo")
        if tam_lote > capacidad:
            raise ValueError("tam_lote no puede ser mayor que la capacidad del buffer")
        if estructura == "lista":
            self.cola = ColaFIFO(capacidad)
        elif estructura == "circular":
            self.cola = BufferCircular(capacidad)
        else:
            raise ValueError("estructura debe ser 'lista' o 'circular'")
        self.tam_lote = tam_lote
        self.recibidos = 0
        self.entregados = 0
        self.lotes = 0
        self.contrapresion = 0

    def recibir(self, evento):
        """Encola un evento. Devuelve False si el buffer está lleno."""
        if not self.cola.encolar(evento):
            return False
        self.recibidos += 1
        return True

    def entregar_lote(self):
        """Saca hasta ``tam_lote`` eventos en orden de llegada."""
        lote = self.cola.desencolar_lote(self.tam_lote)
        if lote:
            self.lotes += 1
            self.entregados += len(lote)
        return lote

    def procesar_stream(self, fuente):
        """Consume un iterable de eventos y genera los lotes para la etapa 1.

        Entrega un lote en cuanto hay ``tam_lote`` eventos en el buffer y, al
        terminar la fuente, vacía lo que quede.
        """
        for evento in fuente:
            if not self.recibir(evento):
                self.contrapresion += 1
                yield self.entregar_lote()
                self.recibir(evento)
            if len(self.cola) >= self.tam_lote:
                yield self.entregar_lote()
        while not self.cola.esta_vacia():
            yield self.entregar_lote()

    def metricas(self):
        return {
            "recibidos": self.recibidos,
            "entregados": self.entregados,
            "lotes": self.lotes,
            "en_buffer": len(self.cola),
            "contrapresion": self.contrapresion,
        }
