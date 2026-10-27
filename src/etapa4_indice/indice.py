"""Etapa 4: indexación principal con B+Tree.

Recibe los eventos de la etapa 3 y mantiene dos índices ordenados:

    por_tiempo   event_time -> eventos     "¿qué pasó entre las 10:00 y las 10:05?"
    por_precio   price -> product_id       "productos entre S/ 100 y S/ 300"

El índice por precio guarda el precio vigente de cada producto (el del
evento más reciente). Si un producto cambia de precio, se quita de la clave
vieja y se agrega en la nueva, así nunca aparece dos veces.

Los eventos salen sin cambios hacia las etapas siguientes.

Operaciones (n claves, orden b):
    procesar(eventos)              O(m log_b n) para m eventos
    eventos_entre(t0, t1)          O(log_b n + k), k = eventos devueltos
    productos_por_precio(p0, p1)   O(log_b n + k)
    precio(product_id)             O(1) con el diccionario de precios vigentes
"""

from src.etapa1_preprocesamiento.preprocesamiento import campo
from src.etapa4_indice.bplus_tree import BPlusTree


class Etapa4Indice:
    """Índices B+Tree por tiempo y por precio."""

    def __init__(self, orden=64):
        self.por_tiempo = BPlusTree(orden)
        self.por_precio = BPlusTree(orden)
        self._precio_vigente = {}   # product_id -> (event_time, precio)
        self._recibidos = 0
        self._cambios_precio = 0

    def procesar(self, eventos):
        """Indexa un lote. Devuelve los eventos para la etapa siguiente."""
        salida = []
        for evento in eventos:
            t = campo(evento, "event_time")
            if t is not None:
                self.por_tiempo.insertar(t, evento)
            self._actualizar_precio(evento, t)
            salida.append(evento)
        self._recibidos += len(salida)
        return salida

    def _actualizar_precio(self, evento, t):
        product_id = campo(evento, "product_id")
        precio = campo(evento, "price")
        if product_id is None or precio is None:
            return
        vigente = self._precio_vigente.get(product_id)
        if vigente is not None:
            t_vigente, p_vigente = vigente
            # La etapa 2 entrega por urgencia: un evento más antiguo no pisa el precio actual.
            if t is not None and t_vigente is not None and t < t_vigente:
                return
            if p_vigente == precio:
                self._precio_vigente[product_id] = (t, precio)
                return
            self.por_precio.eliminar(p_vigente, product_id)
            self._cambios_precio += 1
        self.por_precio.insertar(precio, product_id)
        self._precio_vigente[product_id] = (t, precio)

    # --- Consultas ---------------------------------------------------------------

    def eventos_entre(self, desde, hasta, incluir_hasta=True):
        """Eventos con desde <= event_time <= hasta, en orden de tiempo."""
        return [e for _, e in self.por_tiempo.rango(desde, hasta, incluir_hasta)]

    def eventos_en(self, t):
        """Eventos con exactamente ese event_time."""
        return self.por_tiempo.buscar(t)

    def productos_por_precio(self, minimo=None, maximo=None, limite=None):
        """[(precio, product_id)] con minimo <= precio <= maximo, del más barato al más caro."""
        resultado = []
        for precio, product_id in self.por_precio.rango(minimo, maximo):
            resultado.append((precio, product_id))
            if limite is not None and len(resultado) >= limite:
                break
        return resultado

    def productos_con_precio(self, precio):
        return self.por_precio.buscar(precio)

    def precio(self, product_id):
        vigente = self._precio_vigente.get(product_id)
        return None if vigente is None else vigente[1]

    def metricas(self):
        return {
            "recibidos": self._recibidos,
            "eventos_indexados": len(self.por_tiempo),
            "tiempos_distintos": self.por_tiempo.n_claves,
            "altura_tiempo": self.por_tiempo.altura,
            "productos_con_precio": len(self.por_precio),
            "precios_distintos": self.por_precio.n_claves,
            "altura_precio": self.por_precio.altura,
            "cambios_de_precio": self._cambios_precio,
        }
