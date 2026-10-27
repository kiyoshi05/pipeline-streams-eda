"""Etapa 3: almacenamiento, lookup y caché de productos.

Recibe los eventos de la etapa 2 (en orden de urgencia) y mantiene:

    catalogo        TablaHash  product_id -> ficha del producto
                    (categoría, marca, último precio y contadores por tipo)
    cache           CacheLRU   fichas consultadas hace poco
    interacciones   MatrizDispersa usuario x producto con un peso por tipo de
                    evento; la usa la etapa 7 para la similitud

Consultar un producto pasa primero por la caché y, si no está, por el
catálogo. Cuando un evento actualiza una ficha, se quita de la caché
(invalidación al escribir), así una consulta nunca devuelve una ficha vieja.

Los eventos salen sin cambios, en el mismo orden, hacia la etapa 4.

Operaciones:
    procesar(eventos)    O(n) promedio para n eventos
    consultar(product)   O(1) promedio
"""

from src.etapa1_preprocesamiento.preprocesamiento import campo
from src.etapa3_lookup.lru import CacheLRU
from src.etapa3_lookup.matriz_dispersa import MatrizDispersa
from src.etapa3_lookup.tabla_hash import TablaHash

# Peso de cada tipo de evento en la matriz usuario x producto (feedback implícito).
# Quitar del carrito no suma interés, así que no se guarda.
PESOS_INTERACCION = {
    "view": 1.0,
    "cart": 2.0,
    "remove_from_cart": 0.0,
    "purchase": 4.0,
}
_CONTADORES = {
    "view": "vistas",
    "cart": "carritos",
    "remove_from_cart": "quitados",
    "purchase": "compras",
}


def _ficha_nueva(product_id):
    return {
        "product_id": product_id,
        "category_code": None,
        "brand": None,
        "price": None,
        "ultima_vez": None,
        "vistas": 0,
        "carritos": 0,
        "quitados": 0,
        "compras": 0,
    }


class Etapa3Lookup:
    """Catálogo de productos con caché LRU y matriz de interacciones."""

    def __init__(self, capacidad_cache=1_000, pesos=None):
        self.catalogo = TablaHash()
        self.cache = CacheLRU(capacidad_cache)
        self.interacciones = MatrizDispersa()
        self.pesos = dict(PESOS_INTERACCION if pesos is None else pesos)
        self._recibidos = 0
        self._consultas = 0

    def procesar(self, eventos):
        """Actualiza catálogo, caché y matriz con un lote. Devuelve los eventos para la etapa 4."""
        salida = []
        for evento in eventos:
            self._registrar(evento)
            salida.append(evento)
        self._recibidos += len(salida)
        return salida

    def _registrar(self, evento):
        product_id = campo(evento, "product_id")
        if product_id is None:
            return
        ficha = self.catalogo.obtener(product_id)
        if ficha is None:
            ficha = _ficha_nueva(product_id)
            self.catalogo.insertar(product_id, ficha)

        # Los atributos se toman del evento más reciente: la etapa 2 entrega por
        # urgencia, no por tiempo, así que se compara event_time.
        t = campo(evento, "event_time")
        if ficha["ultima_vez"] is None or (t is not None and t >= ficha["ultima_vez"]):
            ficha["ultima_vez"] = t
            for nombre in ("category_code", "brand", "price"):
                valor = campo(evento, nombre)
                if valor is not None:
                    ficha[nombre] = valor

        tipo = campo(evento, "event_type")
        if tipo in _CONTADORES:
            ficha[_CONTADORES[tipo]] += 1

        self.cache.eliminar(product_id)   # la ficha cambió: la copia en caché ya no sirve

        user_id = campo(evento, "user_id")
        peso = self.pesos.get(tipo, 0.0)
        if user_id is not None and peso:
            self.interacciones.sumar(user_id, product_id, peso)

    def consultar(self, product_id):
        """Ficha del producto (copia), o None si nunca se vio. Pasa primero por la caché."""
        self._consultas += 1
        ficha = self.cache.obtener(product_id)
        if ficha is not None:
            return dict(ficha)
        ficha = self.catalogo.obtener(product_id)
        if ficha is None:
            return None
        copia = dict(ficha)
        self.cache.poner(product_id, copia)
        return dict(copia)

    def productos_de_usuario(self, user_id):
        """{product_id: peso} de las interacciones de un usuario."""
        return self.interacciones.fila(user_id)

    def usuarios_por_producto(self, minimo=None):
        """{product_id: conjunto de user_id}: entrada para MinHash + LSH de la etapa 7."""
        return self.interacciones.conjuntos_por_columna(minimo)

    def metricas(self):
        n_usuarios, n_productos = self.interacciones.forma
        return {
            "recibidos": self._recibidos,
            "productos": len(self.catalogo),
            "consultas": self._consultas,
            "cache_aciertos": self.cache.aciertos,
            "cache_fallos": self.cache.fallos,
            "cache_tasa_aciertos": self.cache.tasa_aciertos,
            "cache_expulsiones": self.cache.expulsiones,
            "matriz_usuarios": n_usuarios,
            "matriz_productos": n_productos,
            "matriz_celdas": self.interacciones.nnz,
            "matriz_densidad": self.interacciones.densidad,
        }
