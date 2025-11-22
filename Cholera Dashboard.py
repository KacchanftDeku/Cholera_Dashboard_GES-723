# cholera_dashboard.py
# FULL UPDATED VERSION USING PYOGRIO INSTEAD OF GEOPANDAS
# ALL ORIGINAL FEATURES INCLUDED

import streamlit as st
import pandas as pd
import numpy as np
import os
import pydeck as pdk

import pyogrio
from shapely.geometry import shape
from shapely.ops import transform
import pyproj

# ================================
# 1. LOAD SHAPEFILES (NO GEOPANDAS)
# ================================

@st.cache_data
def load_shapefile(path):
    df = pyogrio.read_dataframe(path)
    df["geometry"] = df["geometry"].apply(shape)
    return df

@st.cache_data
def load_data():

    deaths = load_shapefile("Cholera_Deaths.shp")
    pumps  = load_shapefile("Pumps.shp")

    # Convert EPSG:27700 → EPSG:4326
    transformer = pyproj.Transformer.from_crs(
        "EPSG:27700", "EPSG:4326", always_xy=True
    ).transform

    deaths["geometry"] = deaths["geometry"].apply(lambda g: transform(transformer, g))
    pumps["geometry"]  = pumps["geometry"].apply(lambda g: transform(transformer, g))

    # Extract coordinates
    deaths["lon"] = deaths.geometry.x
    deaths["lat"] = deaths.geometry.y
    pumps["lon"]  = pumps.geometry.x
    pumps["lat"]  = pumps.geometry.y

    # Required column names
    death_count_col = "Count"
    pump_id_col = "Id"

    # Validate columns
    if death_count_col not in deaths.columns:
        st.error(f"Column '{death_count_col}' missing in Cholera_Deaths.shp")
        st.stop()
    if pump_id_col not in pumps.columns:
        st.error(f"Column '{pump_id_col}' missing in Pumps.shp")
        st.stop()

    # Total deaths
    total_deaths = int(deaths[death_count_col].sum())

    # Distance to nearest pump
    def nearest(row):
        dists = pumps.geometry.distance(row.geometry)
        idx = dists.idxmin()
        return pd.Series({
            "dist_m": round(dists.min(), 1),
            "pump_id": pumps.loc[idx, pump_id_col]
        })

    deaths[["dist_m", "pump_id"]] = deaths.apply(nearest, axis=1)

    return deaths, pumps, death_count_col, pump_id_col, total_deaths


deaths_gdf, pumps_gdf, count_col, pump_col, total_deaths = load_data()


# ================================
# 2. PAGE STYLE
# ================================

st.set_page_config(page_title="John Snow Cholera Map – GES723", layout="wide")

st.markdown("""
<style>
    .kpi-card {
        background: linear-gradient(90deg, #7f1d1d, #991b1b);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
        font-size: 3rem;
        font-weight: bold;
        box-shadow: 0 8px 30px rgba(220,38,38,0.5);
        margin: 2rem 0;
    }
    .death-tooltip {
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
        padding: 12px;
        border-radius: 8px;
        border: 2px solid #ff0000;
        font-family: Arial, sans-serif;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .pump-tooltip {
        background: linear-gradient(135deg, #4444ff, #0000cc);
        color: white;
        padding: 12px;
        border-radius: 8px;
        border: 2px solid #0000ff;
        font-family: Arial, sans-serif;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .section-header {
        background: linear-gradient(90deg, #1e3a8a, #3730a3);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🗺️ John Snow's Cholera Map (1854) - Advanced 3D Visualization")
st.markdown(f'<div class="kpi-card">Cumulative Deaths<br>{total_deaths:,}</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🎯 2D Interactive Map", "🏗️ 3D Extruded Map", "📊 Data Analysis"])



# ================================
# 3. 2D MAP
# ================================

with tab1:
    st.markdown('<div class="section-header">🎯 2D Interactive Map – Deaths and Pumps Combined</div>', unsafe_allow_html=True)

    combined_tooltip_2d = {
        "html": """
        {% if feature.properties.type == 'death' %}
        <div class="death-tooltip">
            <b>💀 CHOLERA DEATH</b><br>
            <b>Deaths at this location:</b> {Count}<br>
            <b>Nearest Pump ID:</b> {pump_id}<br>
            <b>Distance to Pump:</b> {dist_m} meters
        </div>
        {% elif feature.properties.type == 'pump' %}
        <div class="pump-tooltip">
            <b>🚰 WATER PUMP</b><br>
            <b>Pump ID:</b> {Id}<br>
        </div>
        {% endif %}
        """,
        "style": {"fontSize": "14px"}
    }

    deaths_gdf["type"] = "death"
    pumps_gdf["type"] = "pump"

    deaths_layer_2d = pdk.Layer(
        "ScatterplotLayer",
        data=deaths_gdf,
        get_position=["lon", "lat"],
        get_radius=4,
        get_fill_color=[220, 38, 38, 255],
        pickable=True
    )

    pumps_layer_2d = pdk.Layer(
        "ScatterplotLayer",
        data=pumps_gdf,
        get_position=["lon", "lat"],
        get_radius=10,
        get_fill_color=[30, 100, 255, 255],
        pickable=True
    )

    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=deaths_gdf,
        get_position=["lon", "lat"],
        get_weight=count_col,
        radius_pixels=80
    )

    st.pydeck_chart(pdk.Deck(
        layers=[heatmap_layer, deaths_layer_2d, pumps_layer_2d],
        initial_view_state=pdk.ViewState(
            latitude=51.5134,
            longitude=-0.1368,
            zoom=16.8
        ),
        map_style="light",
        tooltip=combined_tooltip_2d
    ))


# ================================
# 4. 3D MAP
# ================================

with tab2:
    st.markdown('<div class="section-header">🏗️ 3D Map – Enhanced Visualization</div>', unsafe_allow_html=True)

    min_lon, max_lon = deaths_gdf.lon.min(), deaths_gdf.lon.max()
    min_lat, max_lat = deaths_gdf.lat.min(), deaths_gdf.lat.max()

    base_poly = [{
        "polygon": [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat]
        ]
    }]

    base_layer = pdk.Layer(
        "PolygonLayer",
        data=base_poly,
        get_polygon="polygon",
        get_fill_color=[245, 245, 245, 200]
    )

    deaths_layer_3d = pdk.Layer(
        "ColumnLayer",
        data=deaths_gdf,
        get_position=["lon", "lat"],
        disk_resolution=10,
        radius=5,
        get_elevation=count_col,
        elevation_scale=1.5,
        get_fill_color=[220, 38, 38, 240],
        extruded=True,
        pickable=True
    )

    pumps_layer_3d = pdk.Layer(
        "ColumnLayer",
        data=pumps_gdf,
        get_position=["lon", "lat"],
        disk_resolution=16,
        radius=8,
        get_elevation=10,
        get_fill_color=[30, 100, 255, 250],
        extruded=True,
        pickable=True
    )

    combined_tooltip_3d = {
        "html": """
        {% if layer.id == 'deaths-layer' %}
        <div class="death-tooltip">
            <b>💀 3D DEATH COLUMN</b><br>
            <b>Deaths:</b> {Count}<br>
            <b>Nearest Pump:</b> {pump_id}<br>
            <b>Distance:</b> {dist_m} meters<br>
        </div>
        {% elif layer.id == 'pumps-layer' %}
        <div class="pump-tooltip">
            <b>🚰 3D PUMP TOWER</b><br>
            <b>Pump ID:</b> {Id}<br>
        </div>
        {% endif %}
        """,
    }

    pitch = st.slider("Camera Pitch", 0, 80, 45)
    bearing = st.slider("Bearing", -180, 180, 0)
    zoom = st.slider("Zoom", 15, 20, 17)

    st.pydeck_chart(pdk.Deck(
        layers=[base_layer, deaths_layer_3d, pumps_layer_3d],
        initial_view_state=pdk.ViewState(
            latitude=51.5134,
            longitude=-0.1368,
            zoom=zoom,
            pitch=pitch,
            bearing=bearing
        ),
        map_style="light",
        tooltip=combined_tooltip_3d
    ))


# ================================
# 5. ANALYSIS TAB
# ================================

with tab3:
    st.markdown('<div class="section-header">📊 Data Analysis & Insights</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💀 Deaths Statistics")
        st.metric("Total Deaths", f"{total_deaths:,}")
        st.metric("Unique Death Locations", len(deaths_gdf))
        st.metric("Avg Deaths per Location", f"{deaths_gdf[count_col].mean():.1f}")
        st.metric("Max Deaths at a Location", int(deaths_gdf[count_col].max()))

        st.subheader("Deaths Distribution")
        st.bar_chart(deaths_gdf[count_col].value_counts().sort_index())

    with col2:
        st.subheader("🚰 Pump Statistics")
        st.metric("Total Pumps", len(pumps_gdf))
        st.metric("Avg Distance to Nearest Pump", f"{deaths_gdf['dist_m'].mean():.1f} m")
        st.metric("Max Distance to Pump", f"{deaths_gdf['dist_m'].max():.1f} m")

        st.subheader("Distance to Nearest Pump")
        st.write(f"Closest: {deaths_gdf['dist_m'].min():.1f} m")
        st.write(f"75% within: {deaths_gdf['dist_m'].quantile(0.75):.1f} m")

    st.subheader("🔗 Deaths by Nearest Pump")
    deaths_by_pump = deaths_gdf.groupby("pump_id").agg({
        count_col: "sum",
        "dist_m": "mean"
    }).round(1).sort_values(count_col, ascending=False)

    st.dataframe(deaths_by_pump)


# ================================
# SIDEBAR
# ================================

st.sidebar.title("🎯 GES723 Final Project")
st.sidebar.subheader("📊 Data Summary")

st.sidebar.markdown("**💀 Deaths Analysis**")
st.sidebar.write(f"Total Deaths: **{total_deaths:,}**")
st.sidebar.write(f"Death Locations: **{len(deaths_gdf)}**")
st.sidebar.write(f"Avg Deaths per Location: **{deaths_gdf[count_col].mean():.1f}**")

st.sidebar.markdown("**🚰 Pumps Analysis**")
st.sidebar.write(f"Total Pumps: **{len(pumps_gdf)}**")
st.sidebar.write(f"Avg Distance to Pump: **{deaths_gdf['dist_m'].mean():.1f} m**")

st.sidebar.markdown("**🎨 Visualization Guide**")
st.sidebar.markdown("""
- 💀 **Red Points/Columns**: Deaths  
- 🚰 **Blue Points/Towers**: Pumps  
- 🔥 **Heatmap**: Density of deaths  
- 🏗️ **3D Height**: Number of deaths  
""")

st.sidebar.markdown("🖱️ **Interaction Guide**")
st.sidebar.markdown("""
- Hover for info  
- Scroll to zoom  
- Drag to rotate  
""")

