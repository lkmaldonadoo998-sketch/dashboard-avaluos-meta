
from pathlib import Path
import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from branca.colormap import linear

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

st.set_page_config(
    page_title="Dashboard de Avalúos Rurales | Meta",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# ESTILO INSTITUCIONAL
# =====================================================

st.markdown("""
<style>
    .stApp {
        background-color: #F3F6F9;
    }

    h1, h2, h3 {
        color: #173D5B;
    }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1600px;
    }

    div[data-testid="stMetric"] {
        background-color: white;
        padding: 18px;
        border: 1px solid #DFE6EC;
        border-left: 4px solid #286D91;
        border-radius: 7px;
    }

    div[data-testid="stMetricValue"] {
        color: #173D5B;
    }

    [data-testid="stSidebar"] {
        background-color: #EAF0F5;
    }

    .encabezado {
        background: #173D5B;
        color: white;
        padding: 22px 28px;
        border-radius: 8px;
        margin-bottom: 22px;
    }

    .encabezado h1 {
        color: white;
        font-size: 28px;
        margin: 0;
    }

    .encabezado p {
        color: #DDEAF2;
        margin: 8px 0 0;
        font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# CARGA DE INFORMACIÓN
# =====================================================

@st.cache_data(show_spinner="Cargando información geográfica...")
def cargar_datos():

    ruta = Path(__file__).parent / "datos" / "AVALUOS_FINALES.zip"

    gdf = gpd.read_file(
        f"zip://{ruta.resolve().as_posix()}"
    )

    if gdf.crs is None:
        raise ValueError(
            "El archivo no tiene sistema de coordenadas definido."
        )

    gdf = gdf.to_crs(epsg=4326)

    gdf = gdf[
        gdf.geometry.notna() & ~gdf.geometry.is_empty
    ].copy()

    gdf["VALOR_HECT"] = pd.to_numeric(
        gdf["VALOR_HECT"], errors="coerce"
    )

    for campo in [
        "MUNICIPI_1", "Vocacion", "COBERTURA", "FUENTE"
    ]:
        gdf[campo] = gdf[campo].fillna(
            "Sin información"
        ).astype(str)

    return gdf


try:
    gdf = cargar_datos()
except Exception as error:
    st.error(f"Error cargando la información: {error}")
    st.stop()

# =====================================================
# ENCABEZADO
# =====================================================

st.markdown("""
<div class="encabezado">
    <h1>OBSERVATORIO DE TIERRAS RURALES</h1>
    <p>
        Dashboard de Avalúos Rurales |
        Departamento del Meta
    </p>
</div>
""", unsafe_allow_html=True)

# =====================================================
# FILTROS EN LA BARRA LATERAL
# =====================================================

st.sidebar.title("Filtros territoriales")
st.sidebar.caption("Consulta y análisis de avalúos rurales")

def opciones(campo):
    return sorted(gdf[campo].unique().tolist())

municipio = st.sidebar.multiselect(
    "Municipio",
    opciones("MUNICIPI_1")
)

vocacion = st.sidebar.multiselect(
    "Vocación del suelo",
    opciones("Vocacion")
)

cobertura = st.sidebar.multiselect(
    "Cobertura del suelo",
    opciones("COBERTURA")
)

fuente = st.sidebar.multiselect(
    "Fuente de información",
    opciones("FUENTE")
)

datos = gdf.copy()

if municipio:
    datos = datos[datos["MUNICIPI_1"].isin(municipio)]

if vocacion:
    datos = datos[datos["Vocacion"].isin(vocacion)]

if cobertura:
    datos = datos[datos["COBERTURA"].isin(cobertura)]

if fuente:
    datos = datos[datos["FUENTE"].isin(fuente)]

st.sidebar.divider()
st.sidebar.caption(
    f"Registros encontrados: {len(datos):,}"
)

# =====================================================
# INDICADORES DINÁMICOS
# =====================================================

st.subheader("Indicadores generales")

valores_validos = datos.loc[
    datos["VALOR_HECT"] > 0, "VALOR_HECT"
].dropna()

mediana = (
    valores_validos.median()
    if not valores_validos.empty
    else None
)

promedio = (
    valores_validos.mean()
    if not valores_validos.empty
    else None
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Registros", f"{len(datos):,}")

with c2:
    st.metric(
        "Municipios",
        datos["MUNICIPI_1"].nunique()
    )

with c3:
    st.metric(
        "Mediana por hectárea",
        f"${mediana / 1_000_000:,.2f} M"
        if mediana is not None else "Sin datos"
    )

with c4:
    st.metric(
        "Promedio por hectárea",
        f"${promedio / 1_000_000:,.2f} M"
        if promedio is not None else "Sin datos"
    )

st.caption(
    "Valores expresados en millones de COP por hectárea, "
    "sujetos a la validación de la unidad del campo VALOR_HECT. "
    "Se excluyen valores nulos, negativos y cero de los cálculos."
)

st.divider()

if datos.empty:
    st.warning(
        "No se encontraron registros con los filtros seleccionados."
    )
    st.stop()

# =====================================================
# MAPA INTERACTIVO
# =====================================================

st.subheader("Distribución espacial de avalúos")

valores_mapa = datos.loc[
    datos["VALOR_HECT"] > 0, "VALOR_HECT"
].dropna()

if not valores_mapa.empty:

    minimo = float(valores_mapa.quantile(0.05))
    maximo = float(valores_mapa.quantile(0.95))

    if maximo <= minimo:
        maximo = minimo + 1

    escala = linear.YlOrRd_09.scale(
        minimo / 1_000_000,
        maximo / 1_000_000
    ).to_step(n=5)

    escala.caption = "Millones de COP por hectárea"

else:
    escala = None

centro = datos.geometry.union_all().centroid

mapa = folium.Map(
    location=[centro.y, centro.x],
    zoom_start=8,
    tiles="OpenStreetMap",
    prefer_canvas=True
)

for _, fila in datos.iterrows():

    punto = fila.geometry
    valor = fila["VALOR_HECT"]

    if (
        escala is not None
        and pd.notna(valor)
        and valor > 0
    ):
        valor_escala = (
            min(max(float(valor), minimo), maximo)
            / 1_000_000
        )
        color = escala(valor_escala)
    else:
        color = "#949CA5"

    texto_valor = (
        f"${valor:,.0f}"
        if pd.notna(valor) and valor > 0
        else "Sin dato"
    )

    contenido = f"""
    <b>Municipio:</b> {fila["MUNICIPI_1"]}<br>
    <b>Valor por hectárea:</b> {texto_valor}<br>
    <b>Vocación:</b> {fila["Vocacion"]}<br>
    <b>Cobertura:</b> {fila["COBERTURA"]}
    """

    folium.CircleMarker(
        location=[punto.y, punto.x],
        radius=5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.8,
        weight=1,
        tooltip=folium.Tooltip(contenido)
    ).add_to(mapa)

if escala is not None:
    escala.add_to(mapa)

# Ajustar el encuadre a los registros filtrados
limites = datos.total_bounds

if (
    pd.notna(limites).all()
    and limites[0] != limites[2]
    and limites[1] != limites[3]
):
    mapa.fit_bounds([
        [limites[1], limites[0]],
        [limites[3], limites[2]]
    ])

st_folium(
    mapa,
    height=530,
    use_container_width=True,
    returned_objects=[],
    key="mapa_avaluos"
)

# =====================================================
# GRÁFICOS ESTADÍSTICOS
# =====================================================

st.divider()
st.subheader("Análisis estadístico")

datos_graficos = datos[
    datos["VALOR_HECT"].notna()
    & (datos["VALOR_HECT"] > 0)
].copy()

datos_graficos["Valor_Millones"] = (
    datos_graficos["VALOR_HECT"] / 1_000_000
)

izquierda, derecha = st.columns(2)

with izquierda:

    st.markdown("#### Valor mediano por municipio")

    resumen_municipal = (
        datos_graficos
        .groupby("MUNICIPI_1", as_index=False)
        ["Valor_Millones"]
        .median()
        .sort_values("Valor_Millones")
    )

    if not resumen_municipal.empty:

        fig = px.bar(
            resumen_municipal,
            x="Valor_Millones",
            y="MUNICIPI_1",
            orientation="h",
            color_discrete_sequence=["#286D91"],
            labels={
                "Valor_Millones": "Millones de COP/ha",
                "MUNICIPI_1": "Municipio"
            }
        )

        fig.update_layout(
            template="plotly_white",
            height=450,
            margin=dict(l=10, r=10, t=15, b=15)
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No hay valores válidos para el gráfico.")

with derecha:

    st.markdown("#### Valor mediano según vocación")

    resumen_vocacion = (
        datos_graficos
        .groupby("Vocacion", as_index=False)
        ["Valor_Millones"]
        .median()
        .sort_values("Valor_Millones")
    )

    if not resumen_vocacion.empty:

        fig2 = px.bar(
            resumen_vocacion,
            x="Valor_Millones",
            y="Vocacion",
            orientation="h",
            color_discrete_sequence=["#5B8C79"],
            labels={
                "Valor_Millones": "Millones de COP/ha",
                "Vocacion": "Vocación"
            }
        )

        fig2.update_layout(
            template="plotly_white",
            height=450,
            margin=dict(l=10, r=10, t=15, b=15)
        )

        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("No hay valores válidos para el gráfico.")

# =====================================================
# TABLA DE CONSULTA
# =====================================================

st.divider()
st.subheader("Consulta de registros")

columnas_tabla = [
    "MUNICIPI_1",
    "VALOR_HECT",
    "Avaluo_Ter",
    "Area_Terre",
    "Vocacion",
    "COBERTURA",
    "clase_ufh",
    "TIEMPO_DES",
    "FUENTE"
]

tabla = datos[columnas_tabla].copy()

st.dataframe(
    tabla,
    use_container_width=True,
    hide_index=True,
    height=350
)

csv = tabla.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Descargar registros filtrados (CSV)",
    data=csv,
    file_name="avaluos_meta_filtrados.csv",
    mime="text/csv"
)

st.divider()

st.caption(
    "Dashboard de consulta y análisis territorial. "
    "Fuente: base de avalúos rurales proporcionada para el ejercicio. "
    "Los resultados dependen de la calidad y cobertura de los registros."
)
