"""Etapa 8: grafo de dominio para la Opción B (co-compra).

Recibe los eventos que ya pasaron por las etapas anteriores y, con las
compras, arma el grafo de forma incremental: cuando una sesión compra un
producto nuevo, se une con cada producto que esa misma sesión ya había
comprado. Así el grafo crece con el stream, sin esperar al final.

Ventana temporal: con ``ventana_seg`` se olvidan las sesiones cuya última
compra quedó más atrás que esa ventana respecto del evento más reciente.
Las aristas ya creadas se conservan; solo se libera la memoria de las
sesiones viejas, que ya no pueden sumar pares nuevos.

Salidas para la etapa 9 (servicio):
    influyentes(k)           productos más influyentes (PageRank o grado)
    comunidades()            agrupaciones de consumo (Louvain o Label Propagation)
    relacionados(p, k)       productos comprados junto con p (cross-selling)

PageRank y las comunidades se guardan y solo se recalculan si el grafo cambió.
"""

from src.etapa1_preprocesamiento.preprocesamiento import campo
from src.etapa8_grafo.comunidades import label_propagation, louvain, modularidad, resumen
from src.etapa8_grafo.grafo import GrafoCoCompra
from src.etapa8_grafo.ranking import mayores_k, pagerank, ranking_por_grado

METODOS_COMUNIDADES = {"louvain": louvain, "label_propagation": label_propagation}


class Etapa8Grafo:
    """Grafo de co-compra con ranking de influencia y comunidades."""

    def __init__(self, tipos=("purchase",), clave_orden="user_session", ventana_seg=None,
                 amortiguacion=0.85, semilla=42):
        self.grafo = GrafoCoCompra()
        self.tipos = frozenset(tipos)
        self.clave_orden = clave_orden
        self.ventana_seg = ventana_seg
        self.amortiguacion = amortiguacion
        self.semilla = semilla
        self._ordenes = {}          # orden -> [productos comprados, última compra]
        self._t_max = None
        self._recibidos = 0
        self._compras = 0
        self._guardados = {}        # (nombre, parámetros) -> (versión del grafo, resultado)

    # --- Construcción ---------------------------------------------------------------

    def procesar(self, eventos):
        """Agrega las compras del lote al grafo. Devuelve los eventos sin cambios."""
        salida = []
        for evento in eventos:
            salida.append(evento)
            if campo(evento, "event_type") not in self.tipos:
                continue
            orden = campo(evento, self.clave_orden)
            producto = campo(evento, "product_id")
            if orden is None or producto is None:
                continue
            self._compras += 1
            t = campo(evento, "event_time")
            registro = self._ordenes.get(orden)
            if registro is None:
                registro = [[], t]
                self._ordenes[orden] = registro
            elif t is not None and (registro[1] is None or t > registro[1]):
                registro[1] = t
            productos = registro[0]
            self.grafo.agregar_nodo(producto)
            if producto not in productos:
                for otro in productos:
                    self.grafo.agregar_arista(producto, otro)
                productos.append(producto)
            if t is not None and (self._t_max is None or t > self._t_max):
                self._t_max = t
        self._recibidos += len(salida)
        self._olvidar_sesiones_viejas()
        return salida

    def _olvidar_sesiones_viejas(self):
        if self.ventana_seg is None or self._t_max is None:
            return
        limite = self._t_max - self.ventana_seg
        viejas = [o for o, (_, t) in self._ordenes.items() if t is not None and t < limite]
        for o in viejas:
            del self._ordenes[o]

    # --- Resultados guardados --------------------------------------------------------

    def _guardado(self, nombre, calcular):
        version, resultado = self._guardados.get(nombre, (None, None))
        if version != self.grafo.version:
            resultado = calcular()
            self._guardados[nombre] = (self.grafo.version, resultado)
        return resultado

    # --- Consultas para la etapa 9 ------------------------------------------------------

    def puntajes(self, metodo="pagerank"):
        """{producto: puntaje} con PageRank o con el grado ponderado (línea base)."""
        if metodo == "pagerank":
            return self._guardado(("pagerank", self.amortiguacion),
                                  lambda: pagerank(self.grafo, self.amortiguacion))
        if metodo == "grado":
            return self._guardado(("grado",), lambda: ranking_por_grado(self.grafo))
        raise ValueError(f"método de ranking desconocido: {metodo}")

    def influyentes(self, k=10, metodo="pagerank"):
        """[(producto, puntaje)] de los k más influyentes."""
        return mayores_k(self.puntajes(metodo), k)

    def comunidades(self, metodo="louvain"):
        """{producto: comunidad}, con la comunidad 0 como la más grande."""
        if metodo not in METODOS_COMUNIDADES:
            raise ValueError(f"método de comunidades desconocido: {metodo}")
        algoritmo = METODOS_COMUNIDADES[metodo]
        return self._guardado(("comunidades", metodo, self.semilla),
                              lambda: algoritmo(self.grafo, semilla=self.semilla))

    def comunidad_de(self, producto, metodo="louvain"):
        """Productos de la misma comunidad que ``producto`` (sin incluirlo)."""
        particion = self.comunidades(metodo)
        if producto not in particion:
            return []
        c = particion[producto]
        return sorted(u for u, cu in particion.items() if cu == c and u != producto)

    def relacionados(self, producto, k=5):
        """[(producto, veces comprados juntos)] para cross-selling."""
        return mayores_k(dict(self.grafo.vecinos(producto)), k)

    def metricas(self, con_comunidades=False):
        datos = {
            "recibidos": self._recibidos,
            "compras": self._compras,
            "ordenes_activas": len(self._ordenes),
            "productos": self.grafo.n_nodos,
            "aristas": self.grafo.n_aristas,
            "peso_total": self.grafo.peso_total,
        }
        if con_comunidades:
            for metodo in METODOS_COMUNIDADES:
                particion = self.comunidades(metodo)
                datos[metodo] = dict(resumen(particion), modularidad=modularidad(self.grafo, particion))
        return datos
