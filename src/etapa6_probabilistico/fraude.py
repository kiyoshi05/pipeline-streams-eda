"""Etapa 6: detección de fraude con estructuras probabilísticas.

Recibe el stream ya limpio (salida de las etapas 1 y 2) y marca cada evento con
una decisión de fraude, sin frenar el flujo. Combina dos señales, cada una
apoyada en una estructura probabilística:

    1. Lista negra  (filtro de Bloom)
       ¿la IP o el dispositivo del evento figura entre los identificadores ya
       conocidos por fraude? El Bloom responde en O(1) y sin falsos negativos,
       así que un actor conocido nunca se escapa.

    2. Velocidad    (Count-Min Sketch)
       ¿cuántos eventos llegaron de esa IP o dispositivo en la ventana de tiempo
       actual? Si supera un umbral, es un patrón de ráfaga típico del fraude
       (muchas compras en segundos). El sketch cuenta con memoria fija y nunca
       subestima, así que no deja pasar una ráfaga por contar de menos.

Un evento se marca como fraude si cae en la lista negra **o** supera el umbral
de velocidad. Esto detecta tanto al defraudador ya fichado como al nuevo que aún
no está en ninguna lista pero se delata por su ritmo.

Además, cuando un identificador dispara la alarma de velocidad se guarda en una
lista de sospechosos en caliente, así sus eventos siguientes (incluso en otras
ventanas) quedan marcados de inmediato, como hace un sistema real al fichar a un
actor. Esto sube el recall para quien reincide, sin tocar la precisión.

La ventana es de tipo *tumbling*: se agrupa por ``event_time // ventana_seg`` y,
al entrar a una ventana nueva, el sketch de velocidad se reinicia. Así el conteo
mide ráfagas recientes y no acumula todo el histórico. Limitación conocida: un
evento muy atrasado (que llega después de haber cambiado de ventana) se cuenta
en la ventana vigente, no en la suya.

Las etiquetas ``es_fraude`` del generador sintético solo sirven para medir
precisión y recall; el detector nunca las mira para decidir.
"""

from collections import Counter

from src.etapa1_preprocesamiento.preprocesamiento import a_epoch, campo, con_cambios
from src.etapa6_probabilistico.bloom import FiltroBloom
from src.etapa6_probabilistico.count_min import CountMinSketch

_VERDADEROS = frozenset({"1", "true", "t", "si", "sí", "yes", "y"})


def _es_verdadero(valor):
    if isinstance(valor, str):
        return valor.strip().lower() in _VERDADEROS
    return bool(valor)


def _tiempo(evento):
    """event_time como epoch entero, acepte el evento crudo o ya normalizado."""
    try:
        return a_epoch(campo(evento, "event_time"))
    except (ValueError, TypeError, OverflowError):
        return None


def claves_identidad(evento):
    """Identificadores del evento que se vigilan: IP y dispositivo (con prefijo)."""
    claves = []
    ip = campo(evento, "ip")
    disp = campo(evento, "dispositivo_id")
    if ip not in (None, ""):
        claves.append(f"ip:{ip}")
    if disp not in (None, ""):
        claves.append(f"disp:{disp}")
    return claves


class Etapa6Fraude:
    """Marca cada evento con una decisión de fraude usando Bloom + Count-Min."""

    def __init__(self, lista_negra=(), ventana_seg=10, umbral_velocidad=8,
                 n_esperado_lista=100_000, prob_fp=0.01,
                 epsilon=0.001, delta=0.01, semilla=42):
        self.ventana_seg = max(1, ventana_seg)
        self.umbral_velocidad = umbral_velocidad
        self._cm_params = dict(epsilon=epsilon, delta=delta, semilla=semilla)

        # Lista negra en un Bloom: se siembra una vez con los identificadores conocidos.
        lista_negra = list(lista_negra)
        self.lista_negra = FiltroBloom(
            n_esperado=max(1, len(lista_negra), n_esperado_lista if lista_negra else 1),
            prob_fp=prob_fp,
        )
        self.lista_negra.actualizar(lista_negra)

        # Sketch de velocidad de la ventana vigente (se reinicia al cambiar de ventana).
        self._ventana_actual = None
        self._velocidad = CountMinSketch(**self._cm_params)

        # Identificadores que ya dispararon la velocidad: se quedan fichados.
        self._sospechosos = set()

        self.totales = Counter()

    # --- Ventana -------------------------------------------------------------

    def _sketch_de(self, t):
        """Devuelve el sketch de la ventana de ``t``, reiniciándolo si es nueva."""
        ventana = t // self.ventana_seg if t is not None else self._ventana_actual
        if ventana != self._ventana_actual and (self._ventana_actual is None or
                                                 (ventana is not None and ventana > self._ventana_actual)):
            self._ventana_actual = ventana
            self._velocidad = CountMinSketch(**self._cm_params)
        return self._velocidad

    # --- Decisión por evento -------------------------------------------------

    def _revisar(self, evento):
        """Devuelve (es_fraude_predicho, score, motivos) para un evento."""
        claves = claves_identidad(evento)
        en_lista = any(self.lista_negra.contiene(c) for c in claves)
        ya_sospechoso = any(c in self._sospechosos for c in claves)

        sketch = self._sketch_de(_tiempo(evento))
        velocidad_max = 0
        for c in claves:
            sketch.sumar(c)
            velocidad_max = max(velocidad_max, sketch.estimar(c))
        por_velocidad = velocidad_max >= self.umbral_velocidad
        if por_velocidad:                       # queda fichado para sus próximos eventos
            self._sospechosos.update(claves)

        motivos = []
        if en_lista:
            motivos.append("lista_negra")
        if por_velocidad:
            motivos.append("velocidad")
        if ya_sospechoso and not por_velocidad:
            motivos.append("sospechoso_previo")
        # Score simple en [0, 1]: la lista negra pesa más que la velocidad.
        base = 0.6 if (en_lista or ya_sospechoso) else 0.0
        score = min(1.0, base + 0.4 * min(1.0, velocidad_max / (2 * self.umbral_velocidad)))
        return (en_lista or por_velocidad or ya_sospechoso), round(score, 4), motivos

    def procesar(self, lote):
        """Anota cada evento con fraude_predicho/fraude_score/fraude_motivos.

        Devuelve la lista de eventos anotados (no muta la entrada) y acumula
        métricas, incluidas precisión y recall contra ``es_fraude`` si existe.
        """
        salida = []
        for evento in lote:
            predicho, score, motivos = self._revisar(evento)
            salida.append(con_cambios(evento, {
                "fraude_predicho": predicho,
                "fraude_score": score,
                "fraude_motivos": motivos,
            }))
            etiqueta = campo(evento, "es_fraude")
            real = _es_verdadero(etiqueta) if etiqueta is not None else None
            self.totales["recibidos"] += 1
            self.totales["marcados"] += int(predicho)
            if real is not None:
                self.totales["con_etiqueta"] += 1
                if predicho and real:
                    self.totales["vp"] += 1
                elif predicho and not real:
                    self.totales["fp"] += 1
                elif not predicho and real:
                    self.totales["fn"] += 1
                else:
                    self.totales["vn"] += 1
        return salida

    def metricas(self):
        t = self.totales
        hay_etiqueta = t["con_etiqueta"] > 0
        pred_pos = t["vp"] + t["fp"]
        reales_pos = t["vp"] + t["fn"]
        return {
            "recibidos": t["recibidos"],
            "marcados": t["marcados"],
            "vp": t["vp"], "fp": t["fp"], "fn": t["fn"], "vn": t["vn"],
            "precision": t["vp"] / pred_pos if hay_etiqueta and pred_pos else None,
            "recall": t["vp"] / reales_pos if hay_etiqueta and reales_pos else None,
            "con_etiqueta": hay_etiqueta,
            "memoria_lista_negra_bytes": self.lista_negra.memoria_bytes,
            "memoria_velocidad_bytes": self._velocidad.memoria_bytes,
        }
