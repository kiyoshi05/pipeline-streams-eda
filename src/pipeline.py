"""Pipeline completo: las 10 etapas conectadas de punta a punta.

Por cada lote del stream (etapas de flujo):

    0  cola FIFO               recibe el stream y lo entrega en lotes
    1  limpieza                valida, ordena por tiempo y deduplica el lote
    6  fraude                  Bloom + Count-Min; anota fraude_predicho. Va antes
                               de la prioridad porque su ventana de velocidad
                               necesita los eventos en orden de tiempo, y porque
                               la etapa 2 prioriza con su decisión
    2  prioridad               heap: lo marcado como fraude sale primero
    3  lookup y caché          catálogo en tabla hash, caché LRU y matriz usuario x producto
    4  índice                  B+Tree por tiempo y por precio
    8  grafo de co-compra      se arma de forma incremental con las compras

Al cerrar el stream (etapas sobre el catálogo acumulado):

    5  índice multidimensional vectores de producto y KD-Tree (KNN exacto como base)
    7  similitud aproximada    IVF sobre los mismos vectores y MinHash + LSH sobre compras
    9  servicio                recomendaciones, autocompletado, ranking de influencia,
                               comunidades y alertas de fraude

Las etapas 5, 7 y 9 construyen índices sobre todo el catálogo, así que se
arman una vez, al cerrar o la primera vez que se pide el servicio; cerrar de
nuevo después de más lotes los reconstruye.

Uso típico:

    from src.pipeline import Pipeline
    p = Pipeline(lista_negra=lista_negra)
    p.procesar(stream)                 # cualquier iterable de eventos
    p.servicio.recomendar(product_id)  # salidas de la etapa 9
    p.recorrido(p.evento_para_demo())  # qué le pasó a un evento en cada etapa
"""

from collections import Counter
from time import perf_counter

from src.etapa0_ingesta import Etapa0Ingesta
from src.etapa1_preprocesamiento import Etapa1Preprocesamiento
from src.etapa1_preprocesamiento.preprocesamiento import campo
from src.etapa2_prioridad.prioridad import NOMBRES as NOMBRES_PRIORIDAD
from src.etapa2_prioridad.prioridad import Etapa2Prioridad
from src.etapa3_lookup import Etapa3Lookup
from src.etapa4_indice import Etapa4Indice
from src.etapa5_multidimensional.indice_productos import IndiceProductos
from src.etapa6_probabilistico import Etapa6Fraude
from src.etapa8_grafo import Etapa8Grafo, mayores_k
from src.etapa9_servicio.servicio import ServicioRecomendaciones

ETAPAS = {
    0: "Ingesta y buffer",
    1: "Preprocesamiento por lotes",
    2: "Cola con prioridades",
    3: "Lookup y caché",
    4: "Índice principal (B+Tree)",
    5: "Índice multidimensional (KD-Tree)",
    6: "Filtrado probabilístico (fraude)",
    7: "Similitud aproximada (IVF y MinHash + LSH)",
    8: "Grafo de co-compra",
    9: "Servicio",
}
ORDEN_FLUJO = (0, 1, 6, 2, 3, 4, 8)
ORDEN_CIERRE = (5, 7, 9)


class Pipeline:
    """Orquestador de las 10 etapas."""

    def __init__(self, lista_negra=(), capacidad=10_000, tam_lote=1_000, capacidad_cache=1_000,
                 orden_bplus=64, ventana_fraude_seg=10, umbral_velocidad=8,
                 n_clusters=16, nprobe=4, semilla=42):
        self.e0 = Etapa0Ingesta(capacidad=capacidad, tam_lote=tam_lote)
        self.e1 = Etapa1Preprocesamiento()
        self.e6 = Etapa6Fraude(lista_negra=lista_negra, ventana_seg=ventana_fraude_seg,
                               umbral_velocidad=umbral_velocidad, semilla=semilla)
        self.e2 = Etapa2Prioridad()
        self.e3 = Etapa3Lookup(capacidad_cache=capacidad_cache)
        self.e4 = Etapa4Indice(orden=orden_bplus)
        self.e8 = Etapa8Grafo(semilla=semilla)
        self.n_clusters = n_clusters
        self.nprobe = nprobe

        self.eventos = []        # todo lo que salió de la etapa 8: entrada de las etapas 5, 7 y 9
        self.alertas = []        # eventos marcados como fraude por la etapa 6, en orden de urgencia
        self.lotes = 0
        self.tiempos = Counter()  # segundos acumulados por etapa (la 7 va sumada en la 9)
        self._e5 = None
        self._servicio = None

    # --- Flujo por lotes ---------------------------------------------------------

    def procesar_lote(self, lote):
        """Pasa un lote por las etapas 1, 6, 2, 3, 4 y 8. Devuelve los eventos en orden de urgencia."""
        t = perf_counter()
        limpio = self.e1.procesar(lote).eventos
        t = self._medir(1, t)
        revisado = self.e6.procesar(limpio)
        t = self._medir(6, t)
        self.e2.recibir(revisado)
        urgentes = self.e2.extraer()
        t = self._medir(2, t)
        con_ficha = self.e3.procesar(urgentes)
        t = self._medir(3, t)
        indexados = self.e4.procesar(con_ficha)
        t = self._medir(4, t)
        salida = self.e8.procesar(indexados)
        self._medir(8, t)

        self.alertas.extend(e for e in salida if campo(e, "fraude_predicho"))
        self.eventos.extend(salida)
        self.lotes += 1
        self._e5 = self._servicio = None   # el catálogo cambió: las etapas 5, 7 y 9 se rearman al pedirlas
        return salida

    def procesar(self, stream):
        """Pasa un stream completo por la etapa 0 y luego cada lote por el resto. Devuelve self."""
        lotes = self.e0.procesar_stream(stream)
        while True:
            t = perf_counter()
            lote = next(lotes, None)
            self._medir(0, t)
            if lote is None:
                break
            self.procesar_lote(lote)
        return self

    def _medir(self, etapa, desde):
        ahora = perf_counter()
        self.tiempos[etapa] += ahora - desde
        return ahora

    # --- Etapas sobre el catálogo (5, 7 y 9) -----------------------------------------

    def cerrar(self):
        """Arma las etapas 5, 7 y 9 sobre los eventos procesados. Devuelve self."""
        if not self.eventos:
            raise ValueError("todavía no se procesó ningún evento")
        t = perf_counter()
        self._e5 = IndiceProductos(self.eventos)
        t = self._medir(5, t)
        # El servicio arma la etapa 7 (IVF y MinHash + LSH) y recibe las salidas de las etapas 6 y 8.
        # Por eso el tiempo de la etapa 7 queda sumado en el de la 9 (no hay una medición aparte).
        self._servicio = ServicioRecomendaciones(
            self.eventos,
            n_clusters=self.n_clusters,
            nprobe=self.nprobe,
            pagerank=self.e8.puntajes("pagerank"),
            comunidades=self.e8.comunidades("louvain"),
            alertas=[self._alerta(e) for e in self.alertas],
        )
        self._medir(9, t)
        return self

    @property
    def indice_productos(self):
        if self._e5 is None:
            self.cerrar()
        return self._e5

    @property
    def servicio(self):
        if self._servicio is None:
            self.cerrar()
        return self._servicio

    @staticmethod
    def _alerta(e):
        return {
            "event_time": campo(e, "event_time"),
            "product_id": campo(e, "product_id"),
            "user_id": campo(e, "user_id"),
            "event_type": campo(e, "event_type"),
            "ip": campo(e, "ip"),
            "dispositivo_id": campo(e, "dispositivo_id"),
            "score": campo(e, "fraude_score"),
            "motivos": ", ".join(campo(e, "fraude_motivos") or []),
        }

    # --- Salidas observables ------------------------------------------------------------

    def resumen(self):
        """Métricas de cada etapa, en el orden del pipeline."""
        servicio = self.servicio
        m1, m6 = self.e1.metricas(), self.e6.metricas()
        return {
            0: {"lotes": self.lotes, "eventos_recibidos": m1["recibidos"]},
            1: {"validos": m1["entregados"], "descartados": m1["descartados"], "duplicados": m1["duplicados"]},
            6: {"marcados": m6["marcados"], "precision": m6["precision"], "recall": m6["recall"]},
            2: self.e2.metricas()["por_prioridad"],
            3: {k: v for k, v in self.e3.metricas().items() if k in ("productos", "matriz_celdas", "cache_tasa_aciertos")},
            4: {k: v for k, v in self.e4.metricas().items() if k in ("eventos_indexados", "altura_tiempo", "altura_precio")},
            8: {k: v for k, v in self.e8.metricas().items() if k in ("compras", "productos", "aristas")},
            5: {"productos_indexados": len(self.indice_productos.vector_por_id)},
            7: {"clusters_ivf": servicio.indice.n_clusters if servicio.indice else 0,
                "productos_con_compras": len(servicio.conjuntos_compra)},
            9: {"eventos": servicio.metricas()["total_eventos"], "alertas": len(servicio.alertas)},
        }

    def evento_para_demo(self):
        """Un evento interesante para mostrar: una compra marcada como fraude, o una compra, o el primero."""
        compras_fraude = [e for e in self.alertas if campo(e, "event_type") == "purchase"]
        if compras_fraude:
            return compras_fraude[0]
        if self.alertas:
            return self.alertas[0]
        compras = [e for e in self.eventos if campo(e, "event_type") == "purchase"]
        return compras[0] if compras else self.eventos[0]

    def recorrido(self, evento, k=3):
        """Qué le pasó a un evento en cada una de las 10 etapas: [(etapa, nombre, resultado)]."""
        pid = campo(evento, "product_id")
        servicio = self.servicio
        prioridad = campo(evento, "prioridad")
        puesto = sorted(servicio.pagerank, key=servicio.pagerank.get, reverse=True).index(pid) + 1 \
            if pid in servicio.pagerank else None
        marca = str(campo(evento, "brand") or "")
        try:
            similares_kd = [p for p, _ in self.indice_productos.buscar_similares(pid, k)]
        except KeyError:
            similares_kd = []
        try:
            recomendados = [p for p, _ in servicio.recomendar(pid, k)]
        except KeyError:
            recomendados = []
        pasos = {
            0: f"entró por la cola FIFO en uno de los {self.lotes} lotes",
            1: f"válido y sin duplicar; event_time normalizado a {campo(evento, 'event_time')}",
            6: (f"marcado como fraude (score {campo(evento, 'fraude_score')}, motivos: "
                f"{', '.join(campo(evento, 'fraude_motivos') or []) or '-'})"
                if campo(evento, "fraude_predicho") else "no marcado como fraude"),
            2: f"prioridad {prioridad} ({NOMBRES_PRIORIDAD.get(prioridad, '?')})",
            3: f"ficha del producto {pid}: {self._resumen_ficha(self.e3.consultar(pid))}",
            4: (f"precio vigente {self.e4.precio(pid)}; "
                f"{len(self.e4.eventos_en(campo(evento, 'event_time')))} eventos en el mismo segundo"),
            8: (f"puesto {puesto} de {len(servicio.pagerank)} en PageRank; comprado junto con "
                f"{[p for p, _ in self.e8.relacionados(pid, k)] or 'ningún otro todavía'}"
                if puesto else "no está en el grafo (nunca se compró)"),
            5: f"vecinos más cercanos en el KD-Tree: {similares_kd}",
            7: (f"recomendados por IVF: {recomendados}; similares por compradores (LSH): "
                f"{[p for p, _ in servicio.similares_por_compra(pid, k)] or 'ninguno'}"),
            9: (f"comunidad {servicio.comunidad_de(pid)}; autocompletar '{marca[:2]}' -> "
                f"{servicio.autocompletar(marca[:2], k) if marca[:2] else []}"),
        }
        orden = ORDEN_FLUJO + ORDEN_CIERRE
        return [(e, ETAPAS[e], pasos[e]) for e in orden]

    @staticmethod
    def _resumen_ficha(ficha):
        if not ficha:
            return "sin ficha"
        return (f"{ficha['vistas']} vistas, {ficha['carritos']} carritos, {ficha['compras']} compras, "
                f"categoría {ficha['category_code']}")

    def influyentes(self, k=5):
        return mayores_k(self.servicio.pagerank, k)
