from pathlib import Path

import streamlit as st

from src.etapa0_ingesta.ingesta import leer_csv
from src.etapa6_probabilistico import Etapa6Fraude
from src.etapa9_servicio.servicio import ServicioRecomendaciones
from experimentos.datos_sinteticos import generar_eventos_fraude


st.set_page_config(
    page_title="Recomendaciones",
    page_icon="🛍️",
    layout="wide",
)


@st.cache_resource
def cargar_servicio(ruta_csv, fecha_modificacion):
    ruta = Path(ruta_csv)

    if ruta.is_file():
        eventos = list(leer_csv(ruta, limite=10_000))
        origen = f"Muestra CSV: {ruta.name}"
    else:
        # user_session permite que la etapa 8 detecte productos comprados juntos.
        eventos = [
            {
                "product_id": 101, "user_id": 1, "price": 25,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "view", "user_session": "ropa-1",
            },
            {
                "product_id": 101, "user_id": 2, "price": 25,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "purchase", "user_session": "ropa-2",
            },
            {
                "product_id": 101, "user_id": 3, "price": 25,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "purchase", "user_session": "ropa-3",
            },
            {
                "product_id": 102, "user_id": 1, "price": 28,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "cart", "user_session": "ropa-1",
            },
            {
                "product_id": 102, "user_id": 2, "price": 28,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "purchase", "user_session": "ropa-2",
            },
            {
                "product_id": 102, "user_id": 3, "price": 28,
                "brand": "Acme", "category_code": "ropa.camisas",
                "event_type": "purchase", "user_session": "ropa-3",
            },
            {
                "product_id": 103, "user_id": 4, "price": 450,
                "brand": "Nova", "category_code": "electronica.telefonos",
                "event_type": "view", "user_session": "electronica-1",
            },
            {
                "product_id": 103, "user_id": 5, "price": 450,
                "brand": "Nova", "category_code": "electronica.telefonos",
                "event_type": "purchase", "user_session": "electronica-2",
            },
            {
                "product_id": 104, "user_id": 2, "price": 470,
                "brand": "Nova", "category_code": "electronica.telefonos",
                "event_type": "cart", "user_session": "electronica-1",
            },
            {
                "product_id": 104, "user_id": 6, "price": 470,
                "brand": "Nova", "category_code": "electronica.telefonos",
                "event_type": "purchase", "user_session": "electronica-2",
            },
        ]
        origen = "Datos de demostración"

    servicio = ServicioRecomendaciones(
        eventos,
        n_clusters=4,
        nprobe=4,
    )
    return servicio, origen


@st.cache_resource
def analizar_fraude(n, semilla):
    """Etapa 6 sobre eventos sintéticos con fraude: devuelve métricas y marcados."""
    eventos, lista_negra = generar_eventos_fraude(n, semilla=semilla)
    e6 = Etapa6Fraude(lista_negra=lista_negra, ventana_seg=10, umbral_velocidad=8)
    anotados = e6.procesar(eventos)
    marcados = [e for e in anotados if e["fraude_predicho"]]
    return e6.metricas(), marcados


ruta_csv = st.sidebar.text_input(
    "Ruta de la muestra CSV",
    "data/sample/eventos.csv",
)

ruta = Path(ruta_csv)
fecha_modificacion = ruta.stat().st_mtime_ns if ruta.is_file() else 0

servicio, origen = cargar_servicio(ruta_csv, fecha_modificacion)
metricas = servicio.metricas()

st.title("Recomendaciones de productos")
st.caption(f"Fuente: {origen}")

col1, col2, col3 = st.columns(3)
col1.metric("Eventos procesados", metricas["total_eventos"])
col2.metric("Productos", metricas["productos"])
col3.metric("Usuarios", metricas["usuarios"])

st.subheader("Productos similares")
productos = sorted(servicio.vector_por_id)

if productos:
    producto = st.selectbox("Elige un producto", productos)
    k = st.slider("Cantidad de recomendaciones", min_value=1, max_value=3, value=2)

    recomendaciones = servicio.recomendar(producto, k=k)
    if recomendaciones:
        st.dataframe(
            [
                {"Producto recomendado": id_, "Relevancia": round(puntaje, 3)}
                for id_, puntaje in recomendaciones
            ],
            hide_index=True,
        )
    else:
        st.info("No se encontraron recomendaciones por atributos.")

    st.subheader("Productos con compradores similares")
    similares_compra = servicio.similares_por_compra(producto, k=k)

    if similares_compra:
        st.dataframe(
            [
                {"Producto": id_, "Similitud Jaccard": round(similitud, 3)}
                for id_, similitud in similares_compra
            ],
            hide_index=True,
        )
    else:
        st.info("No hay suficientes compras compartidas para este producto.")
else:
    st.info("No hay productos disponibles para recomendar.")

st.subheader("Ranking de influencia y comunidades")
st.caption("El ranking PageRank y las comunidades se calculan con la etapa 8.")

influyentes = servicio.productos_influyentes(k=10)

if influyentes:
    filas_ranking = []
    for product_id, puntaje in influyentes:
        comunidad = servicio.comunidad_de(product_id)
        filas_ranking.append(
            {
                "Producto": product_id,
                "PageRank": round(puntaje, 6),
                "Comunidad": comunidad if comunidad is not None else "Sin comunidad",
            }
        )

    st.dataframe(filas_ranking, hide_index=True)
else:
    st.info(
        "No hay productos para el ranking. Verifica que los eventos incluyan "
        "compras y el campo user_session."
    )

st.subheader("Alertas de fraude")
if servicio.alertas:
    st.dataframe(servicio.alertas, hide_index=True)
else:
    st.info(
        "No hay alertas cargadas. La etapa 6 todavía no está conectada en esta versión."
    )

st.subheader("Autocompletado")
prefijo = st.text_input("Escribe el inicio de una marca o categoría")

if prefijo:
    sugerencias = servicio.autocompletar(prefijo, k=10)
    st.write(sugerencias or "Sin coincidencias")

st.subheader("Eventos por tipo")
st.dataframe(
    [
        {"Tipo de evento": tipo, "Cantidad": cantidad}
        for tipo, cantidad in metricas["tipos_evento"].items()
    ],
    hide_index=True,
)

st.subheader("Detección de fraude (Etapa 6)")
st.caption(
    "Demo con eventos sintéticos: filtro de Bloom (lista negra de IP/dispositivos) "
    "+ Count-Min Sketch (velocidad por ventana). La muestra REES46 no trae campos "
    "de fraude, así que esta sección usa el generador sintético."
)
n_fraude = st.slider("Eventos sintéticos a analizar", 1_000, 50_000, 10_000, step=1_000)
metricas_fraude, marcados = analizar_fraude(n_fraude, 42)

f1, f2, f3 = st.columns(3)
f1.metric("Eventos marcados", metricas_fraude["marcados"])
f2.metric("Precisión", f"{metricas_fraude['precision']:.1%}" if metricas_fraude["precision"] is not None else "—")
f3.metric("Recall", f"{metricas_fraude['recall']:.1%}" if metricas_fraude["recall"] is not None else "—")

if marcados:
    st.dataframe(
        [
            {
                "IP": e.get("ip"),
                "Dispositivo": e.get("dispositivo_id"),
                "Tipo": e["event_type"],
                "Score": e["fraude_score"],
                "Motivos": ", ".join(e["fraude_motivos"]),
            }
            for e in marcados[:20]
        ],
        hide_index=True,
    )
else:
    st.info("No se detectaron eventos sospechosos.")