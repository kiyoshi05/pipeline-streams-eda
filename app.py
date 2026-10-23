import streamlit as st
from pathlib import Path
from src.etapa0_ingesta.ingesta import leer_csv

from src.etapa9_servicio.servicio import ServicioRecomendaciones


st.set_page_config(page_title="Recomendaciones", page_icon="🛍️", layout="wide")

@st.cache_resource
def cargar_servicio(ruta_csv, fecha_modificacion):
    ruta = Path(ruta_csv)

    if ruta.is_file():
        eventos = list(leer_csv(ruta, limite=10_000))
        origen = f"Muestra CSV: {ruta.name}"
    else:
        eventos = [
                {"product_id": 101, "user_id": 1, "price": 25, "brand": "Acme", "category_code": "ropa.camisas", "event_type": "view"},
                {"product_id": 101, "user_id": 2, "price": 25, "brand": "Acme", "category_code": "ropa.camisas", "event_type": "purchase"},
                {"product_id": 102, "user_id": 1, "price": 28, "brand": "Acme", "category_code": "ropa.camisas", "event_type": "cart"},
                {"product_id": 102, "user_id": 3, "price": 28, "brand": "Acme", "category_code": "ropa.camisas", "event_type": "purchase"},
                {"product_id": 103, "user_id": 4, "price": 450, "brand": "Nova", "category_code": "electronica.telefonos", "event_type": "view"},
                {"product_id": 103, "user_id": 5, "price": 450, "brand": "Nova", "category_code": "electronica.telefonos", "event_type": "purchase"},
                {"product_id": 104, "user_id": 2, "price": 470, "brand": "Nova", "category_code": "electronica.telefonos", "event_type": "cart"},
                {"product_id": 104, "user_id": 6, "price": 470, "brand": "Nova", "category_code": "electronica.telefonos", "event_type": "purchase"},
            ]
        origen = "Datos de demostración"

    servicio = ServicioRecomendaciones(eventos, n_clusters=4, nprobe=4)
    return servicio, origen



ruta_csv = st.sidebar.text_input(
    "Ruta de la muestra CSV",
    "data/sample/eventos.csv",
)

ruta = Path(ruta_csv)
fecha_modificacion = (
    ruta.stat().st_mtime_ns if ruta.is_file() else 0
)

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
    st.info("No se encontraron recomendaciones para este producto.")

st.subheader("Autocompletado")
prefijo = st.text_input("Escribe el inicio de una marca o categoría")
if prefijo:
    st.write(servicio.autocompletar(prefijo, k=10) or "Sin coincidencias")

st.subheader("Eventos por tipo")
st.dataframe(
    [
        {"Tipo de evento": tipo, "Cantidad": cantidad}
        for tipo, cantidad in metricas["tipos_evento"].items()
    ],
    hide_index=True,
)