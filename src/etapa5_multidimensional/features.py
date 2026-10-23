from collections import Counter
from math import log1p
from statistics import median


PESO_EVENTO = {
    "view": 1.0,
    "cart": 2.0,
    "purchase": 3.0,
    "remove_from_cart": 0.0,
}


def _normalizar(valores):
    minimo = min(valores)
    maximo = max(valores)

    if maximo == minimo:
        return [0.0 for _ in valores]

    return [(valor - minimo) / (maximo - minimo) for valor in valores]


def construir_vectores_productos(eventos):
    """Construye un vector por producto a partir de eventos REES46.

    Devuelve:
      - lista de pares (product_id, vector)
      - diccionario categoría -> posición de su columna one-hot
    """
    productos = {}

    for evento in eventos:
        product_id = evento.get("product_id")
        if product_id is None:
            continue

        producto = productos.setdefault(
            product_id,
            {"precios": [], "categorias": Counter(), "popularidad": 0.0},
        )

        try:
            producto["precios"].append(float(evento["price"]))
        except (KeyError, TypeError, ValueError):
            pass

        categoria = str(evento.get("category_code") or "desconocido").strip().lower()
        producto["categorias"][categoria] += 1

        tipo = str(evento.get("event_type") or "view").lower()
        producto["popularidad"] += PESO_EVENTO.get(tipo, 1.0)

    if not productos:
        return [], {}

    ids = list(productos)
    precios = [
        median(productos[id_]["precios"]) if productos[id_]["precios"] else 0.0
        for id_ in ids
    ]
    popularidades = [
        log1p(productos[id_]["popularidad"])
        for id_ in ids
    ]

    precios_norm = _normalizar(precios)
    popularidades_norm = _normalizar(popularidades)

    categorias = sorted({
        max(
            productos[id_]["categorias"].items(),
            key=lambda par: (par[1], par[0]),
        )[0]
        for id_ in ids
    })
    categoria_a_posicion = {categoria: i for i, categoria in enumerate(categorias)}

    vectores = []
    for i, id_ in enumerate(ids):
        categoria = max(
            productos[id_]["categorias"].items(),
            key=lambda par: (par[1], par[0]),
        )[0]

        one_hot = [0.0] * len(categorias)
        one_hot[categoria_a_posicion[categoria]] = 1.0

        vector = (precios_norm[i], popularidades_norm[i], *one_hot)
        vectores.append((id_, vector))

    return vectores, categoria_a_posicion