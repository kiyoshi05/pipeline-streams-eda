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

import random
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
from src.etapa5_multidimensional.knn import knn_exacto
from src.etapa6_probabilistico import Etapa6Fraude
from src.etapa7_similitud.ivf import IVFFlat
from src.etapa7_similitud.minhash_lsh import MinHashLSH
from src.etapa8_grafo import Etapa8Grafo, mayores_k
from src.etapa9_servicio.servicio import LSH_BANDAS, LSH_HASHES, ServicioRecomendaciones

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
        self.tiempos = Counter()  # segundos acumulados por etapa
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
        # Etapa 7: IVF sobre los vectores de la etapa 5 y MinHash + LSH sobre la
        # matriz de compras de la etapa 3. Se arman aquí para medirlas aparte.
        compradores = self.e3.compradores_por_producto()
        indice_ivf = IVFFlat(self._e5.vectores, n_clusters=self.n_clusters, nprobe=self.nprobe)             if self._e5.vectores else None
        indice_lsh = MinHashLSH(num_hashes=LSH_HASHES, bandas=LSH_BANDAS).ajustar(compradores)
        t = self._medir(7, t)
        # Etapa 9: el servicio recibe los índices ya hechos y las salidas de las etapas 6 y 8.
        self._servicio = ServicioRecomendaciones(
            self.eventos,
            n_clusters=self.n_clusters,
            nprobe=self.nprobe,
            vectores=self._e5.vectores,
            indice=indice_ivf,
            indice_lsh=indice_lsh,
            pagerank=self.e8.puntajes("pagerank"),
            comunidades=self.e8.comunidades("louvain"),
            alertas=[self._alerta(e) for e in self.alertas],
            conjuntos_compra=compradores,   # matriz de compras de la etapa 3
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
            3: {k: v for k, v in self.e3.metricas().items() if k in ("productos", "matriz_celdas", "compras_celdas")},
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

    # --- Consultas de productos (etapas 3 y 4) -------------------------------------------

    def consultar_producto(self, product_id):
        """Ficha del producto: pasa primero por la caché LRU y luego por la tabla hash (etapa 3)."""
        return self.e3.consultar(product_id)

    def productos_por_precio(self, minimo=None, maximo=None, limite=None):
        """[(precio, product_id)] en el rango, del más barato al más caro (B+Tree, etapa 4)."""
        return self.e4.productos_por_precio(minimo, maximo, limite)

    def eventos_entre(self, desde, hasta):
        """Eventos con desde <= event_time <= hasta, en orden de tiempo (B+Tree, etapa 4)."""
        return self.e4.eventos_entre(desde, hasta)

    def simular_consultas(self, n=1_000, semilla=42):
        """Simula n visitas a fichas de producto con la popularidad observada (vistas).

        Mide la caché como la usaría la tienda: los productos más vistos se
        consultan más y deberían quedarse en la caché. Devuelve la tasa de
        aciertos de esas n consultas.
        """
        fichas = list(self.e3.catalogo.valores())
        if not fichas:
            return 0.0
        azar = random.Random(semilla)
        pesos = [f["vistas"] + 1 for f in fichas]
        antes = (self.e3.cache.aciertos, self.e3.cache.fallos)
        for f in azar.choices(fichas, weights=pesos, k=n):
            self.e3.consultar(f["product_id"])
        aciertos = self.e3.cache.aciertos - antes[0]
        fallos = self.e3.cache.fallos - antes[1]
        return aciertos / (aciertos + fallos) if aciertos + fallos else 0.0

    # --- Prioridades y ventas (etapa 2 y panel del servicio) -------------------------------

    def lote_de_prioridades(self, por_nivel=2, semilla=42):
        """Un lote chico con eventos de cada nivel de urgencia, para ver el heap en acción.

        Toma hasta ``por_nivel`` eventos procesados de cada prioridad, los ordena
        por llegada (event_time) y los pasa por una cola nueva de la etapa 2.
        Devuelve (llegada, salida): el orden en que llegaron y el orden en que
        los saca el heap.
        """
        azar = random.Random(semilla)
        por_prioridad = {}
        for e in self.eventos:
            por_prioridad.setdefault(campo(e, "prioridad"), []).append(e)
        lote = []
        for p in sorted(por_prioridad, key=lambda x: (x is None, x)):
            grupo = por_prioridad[p]
            lote.extend(azar.sample(grupo, min(por_nivel, len(grupo))))
        llegada = sorted(lote, key=lambda e: campo(e, "event_time", 0))
        cola = Etapa2Prioridad()
        cola.recibir(llegada)
        return llegada, cola.extraer()

    def ventas(self, k=5):
        """Panel de ventas: compras confirmadas, ingresos, conversión y lo más vendido.

        Una compra que la etapa 6 marcó como fraude no cuenta como venta: queda
        retenida hasta verificarla. Lo más vendido sale de un Top-K con el heap
        (mayores_k), no de ordenar todo el catálogo.
        """
        compras = [e for e in self.eventos if campo(e, "event_type") == "purchase"]
        confirmadas = [e for e in compras if not campo(e, "fraude_predicho")]
        unidades, ingreso_producto, marca = Counter(), Counter(), {}
        por_categoria, por_tipo_orden = Counter(), Counter()
        for e in confirmadas:
            pid, precio = campo(e, "product_id"), float(campo(e, "price") or 0)
            unidades[pid] += 1
            ingreso_producto[pid] += precio
            marca[pid] = campo(e, "brand") or "-"
            categoria = str(campo(e, "category_code") or "sin categoría").split(".")[0]
            por_categoria[categoria] += precio
            por_tipo_orden[NOMBRES_PRIORIDAD.get(campo(e, "prioridad"), "?")] += 1
        ingresos = sum(ingreso_producto.values())
        sesiones = {campo(e, "user_session") for e in self.eventos if campo(e, "user_session")}
        con_compra = {campo(e, "user_session") for e in confirmadas if campo(e, "user_session")}
        return {
            "ventas": len(confirmadas),
            "retenidas_por_fraude": len(compras) - len(confirmadas),
            "ingresos": round(ingresos, 2),
            "ticket_promedio": round(ingresos / len(confirmadas), 2) if confirmadas else 0.0,
            "conversion": len(con_compra) / len(sesiones) if sesiones else 0.0,
            "mas_vendidos": [(pid, marca[pid], unidades[pid], round(total, 2))
                             for pid, total in mayores_k(ingreso_producto, k)],
            "por_categoria": {c: round(v, 2) for c, v in por_categoria.most_common()},
            "por_tipo_orden": dict(por_tipo_orden),
        }

    # --- Similitud frente al método exacto (etapas 5 y 7) ----------------------------------

    def comparar_similitud(self, k=5, muestras=30, semilla=42):
        """recall@k y tiempo de cada método contra su versión exacta.

        Vectores de producto (etapa 5): KD-Tree e IVF contra KNN exacto por
        fuerza bruta. Compradores (etapa 7): MinHash + LSH contra Jaccard exacto
        con todos los productos. Se promedia sobre ``muestras`` productos.
        """
        azar = random.Random(semilla)
        e5, servicio = self.indice_productos, self.servicio
        ids = sorted(e5.vector_por_id)
        elegidos = azar.sample(ids, min(muestras, len(ids)))
        tiempos, recall = Counter(), Counter()
        for pid in elegidos:
            v = e5.vector_por_id[pid]
            t = perf_counter()
            exactos = {p for p, _ in knn_exacto(e5.vectores, v, k, excluir_id=pid)}
            t = self._cronometrar(tiempos, "knn_exacto", t)
            kd = {p for p, _ in e5.kd_tree.buscar(v, k, excluir_id=pid)}
            t = self._cronometrar(tiempos, "kd_tree", t)
            ivf = {p for p, _ in servicio.indice.buscar(v, k, excluir_id=pid)} if servicio.indice else set()
            self._cronometrar(tiempos, "ivf", t)
            if exactos:
                recall["kd_tree"] += len(kd & exactos) / len(exactos)
                recall["ivf"] += len(ivf & exactos) / len(exactos)
        n_vec = len(elegidos)

        conjuntos = servicio.conjuntos_compra
        con_vecinos = []
        for pid in sorted(conjuntos):
            exactos = self._jaccard_exacto(conjuntos, pid, k)
            if exactos:
                con_vecinos.append((pid, exactos))
        elegidos_lsh = azar.sample(con_vecinos, min(muestras, len(con_vecinos)))
        for pid, exactos in elegidos_lsh:
            t = perf_counter()
            lsh = {p for p, _ in servicio.similares_por_compra(pid, k)}
            self._cronometrar(tiempos, "minhash_lsh", t)
            recall["minhash_lsh"] += len(lsh & exactos) / len(exactos)
        t = perf_counter()
        for pid, _ in elegidos_lsh:
            self._jaccard_exacto(conjuntos, pid, k)
        self._cronometrar(tiempos, "jaccard_exacto", t)
        n_lsh = len(elegidos_lsh)

        def fila(metodo, base, n):
            return {"recall": recall[metodo] / n if n and metodo in recall else (1.0 if n else None),
                    "ms_por_consulta": 1000 * tiempos[metodo] / n if n else None, "contra": base, "consultas": n}

        return {
            "knn_exacto": fila("knn_exacto", "es la referencia", n_vec),
            "kd_tree": fila("kd_tree", "knn_exacto", n_vec),
            "ivf": fila("ivf", "knn_exacto", n_vec),
            "jaccard_exacto": fila("jaccard_exacto", "es la referencia", n_lsh),
            "minhash_lsh": fila("minhash_lsh", "jaccard_exacto", n_lsh),
        }

    @staticmethod
    def _jaccard_exacto(conjuntos, pid, k):
        """Los k productos con mayor Jaccard (> 0) contra pid, por fuerza bruta."""
        a = conjuntos[pid]
        puntajes = []
        for otro, b in conjuntos.items():
            if otro != pid:
                comunes = len(a & b)
                if comunes:
                    puntajes.append((comunes / len(a | b), otro))
        puntajes.sort(key=lambda x: (-x[0], str(x[1])))
        return {p for _, p in puntajes[:k]}

    @staticmethod
    def _cronometrar(tiempos, metodo, desde):
        ahora = perf_counter()
        tiempos[metodo] += ahora - desde
        return ahora

    def influyentes(self, k=5):
        return mayores_k(self.servicio.pagerank, k)
