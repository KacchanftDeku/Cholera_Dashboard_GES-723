# cholera_dashboard.py
# Fully deployment-ready for Streamlit Cloud

import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
import numpy as np

# ================================
# 1. LOAD DATA
# ================================
@st.cache_data
def load_data():
    try:
        deaths = gpd.read_file("Cholera_Deaths.shp").to_crs(epsg=4326)
        pumps  = gpd.read_file("Pumps.shp").to_crs(epsg=4326)
    except Exception as e:
        st.error(f"Error loading shapefiles: {e}")
        st.stop()

    death_count_col = "Count"
    pump_id_col     = "Id"

    if death_count_col not in deaths.columns:
        st.error(f"'{death_count_col}' column not found in Cholera_Deaths.shp")
        st.stop()
    if pump_id_col not in pumps.columns:
        st.error(f"'{pump_id_col}' column not found in Pumps.shp")
        st.stop()

    total_deaths = int(deaths[death_count_col].sum())

    deaths["lon"] = deaths.geometry.x
    deaths["lat"] = deaths.geometry.y
    pumps["lon"]  = pumps.geometry.x
    pumps["lat"]  = pumps.geometry.y

    def nearest(row):
        dists = pumps.geometry.distance(row.geometry)
        idx = dists.idxmin()
        return pd.Series({
            "dist_m": round(dists.min() * 111320, 1),
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
.kpi-card { background: linear-gradient(90deg, #7f1d1d, #991b1b); color: white; padding: 2rem; border-radius: 16px; text-align: center; font-size: 3rem; font-weight: bold; box-shadow: 0 8px 30px rgba(220,38,38,0.5); margin: 2rem 0; }
.death-tooltip { background: linear-gradient(135deg, #ff4444, #cc0000); color: white; padding: 12px; border-radius: 8px; border: 2px solid #ff0000; font-family: Arial, sans-serif; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.pump-tooltip { background: linear-gradient(135deg, #4444ff, #0000cc); color: white; padding: 12px; border-radius: 8px; border: 2px solid #0000ff; font-family: Arial, sans-serif; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.section-header { background: linear-gradient(90deg, #1e3a8a, #3730a3); color: white; padding: 1rem; border-radius: 10px; margin: 1rem 0; text-align: center; }
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

    deaths_layer_2d = pdk.Layer(
        "ScatterplotLayer", data=deaths_gdf,
        get_position=["lon", "lat"], get_radius=4,
        get_fill_color=[220, 38, 38, 255],
        pickable=True, auto_highlight=True, id="deaths-layer"
    )

    pumps_layer_2d = pdk.Layer(
        "ScatterplotLayer", data=pumps_gdf,
        get_position=["lon", "lat"], get_radius=10,
        get_fill_color=[30, 100, 255, 255],
        pickable=True, auto_highlight=True, id="pumps-layer"
    )

    heatmap_layer = pdk.Layer(
        "HeatmapLayer", data=deaths_gdf, get_position=["lon", "lat"],
        get_weight=count_col, radius_pixels=80, intensity=1.5, opacity=0.7, threshold=0.1, id="heatmap-layer"
    )

    st.pydeck_chart(pdk.Deck(
        layers=[heatmap_layer, deaths_layer_2d, pumps_layer_2d],
        initial_view_state=pdk.ViewState(latitude=51.5134, longitude=-0.1368, zoom=16.8, pitch=0, bearing=0),
        map_style="light", tooltip=combined_tooltip_2d
    ), use_container_width=True)

# ================================
# 4. 3D MAP
# ================================
with tab2:
    st.markdown('<div class="section-header">🏗️ 3D Map – Enhanced Visualization</div>', unsafe_allow_html=True)

    min_lon, max_lon = deaths_gdf.lon.min(), deaths_gdf.lon.max()
    min_lat, max_lat = deaths_gdf.lat.min(), deaths_gdf.lat.max()
    lon_padding = (max_lon - min_lon) * 0.1
    lat_padding = (max_lat - min_lat) * 0.1

    base_polygon = [{"polygon": [
        [min_lon - lon_padding, min_lat - lat_padding],
        [max_lon + lon_padding, min_lat - lat_padding],
        [max_lon + lon_padding, max_lat + lat_padding],
        [min_lon - lon_padding, max_lat + lat_padding]
    ]}]

    base_layer = pdk.Layer(
        "PolygonLayer", data=base_polygon, get_polygon="polygon",
        get_fill_color=[245,245,245,200], get_line_color=[200,200,200,100],
        stroked=True, filled=True, extruded=False, pickable=False, id="base-layer"
    )

    deaths_layer_3d = pdk.Layer(
        "ColumnLayer", data=deaths_gdf, get_position=["lon","lat"], disk_resolution=10, radius=5,
        get_elevation=count_col, elevation_scale=1.5,
        get_fill_color=[220,38,38,240], get_line_color=[255,200,200,255],
        pickable=True, auto_highlight=True, extruded=True, id="deaths-3d-layer", coverage=1.0
    )

    pumps_layer_3d = pdk.Layer(
        "ColumnLayer", data=pumps_gdf, get_position=["lon","lat"], disk_resolution=16, radius=8,
        get_elevation=10, elevation_scale=1,
        get_fill_color=[30,100,255,250], get_line_color=[200,200,255,255],
        pickable=True, auto_highlight=True, extruded=True, id="pumps-3d-layer", coverage=1.0
    )

    combined_tooltip_3d = {
        "html": """
        {% if layer.id == 'deaths-3d-layer' %}
        <div class="death-tooltip">
            <b>💀 3D DEATH COLUMN</b><br>
            <b>Deaths at this location:</b> {Count}<br>
            <b>Nearest Pump ID:</b> {pump_id}<br>
            <b>Distance to Pump:</b> {dist_m} meters
        </div>
        {% elif layer.id == 'pumps-3d-layer' %}
        <div class="pump-tooltip">
            <b>🚰 3D PUMP TOWER</b><br>
            <b>Pump ID:</b> {Id}<br>
        </div>
        {% endif %}
        """,
        "style": {"fontSize": "14px"}
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        pitch = st.slider("Camera Angle", 0, 80, 45, key="pitch_3d")
    with col2:
        bearing = st.slider("Rotation", -180, 180, 0, key="bearing_3d")
    with col3:
        zoom = st.slider("Zoom Level", 15, 20, 17, key="zoom_3d")

    st.pydeck_chart(pdk.Deck(
        layers=[base_layer, deaths_layer_3d, pumps_layer_3d],
        initial_view_state=pdk.ViewState(latitude=51.5134, longitude=-0.1368, zoom=zoom, pitch=pitch, bearing=bearing),
        map_style="light", tooltip=combined_tooltip_3d
    ), use_container_width=True)

# ================================
# 5. DATA ANALYSIS
# ================================
with tab3:
    st.markdown('<div class="section-header">📊 Data Analysis & Insights</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💀 Deaths Statistics")
        st.metric("Total Deaths", f"{total_deaths:,}")
        st.metric("Unique Death Locations", len(deaths_gdf))
        st.metric("Average Deaths per Location", f"{deaths_gdf[count_col].mean():.1f}")
        st.metric("Maximum Deaths at Single Location", int(deaths_gdf[count_col].max()))
        st.subheader("Deaths Distribution")
        st.bar_chart(deaths_gdf[count_col].value_counts().sort_index())

        st.subheader("🔗 Deaths by Nearest Pump")
        deaths_by_pump = deaths_gdf.groupby('pump_id').agg({
            count_col: 'sum',
            'dist_m': 'mean'
        }).round(1).sort_values(count_col, ascending=False)
        st.dataframe(deaths_by_pump.head(10), use_container_width=True)

    with col2:
        st.subheader("🚰 Pumps Statistics")
        st.metric("Total Pumps", len(pumps_gdf))
        st.metric("Average Distance to Nearest Pump", f"{deaths_gdf['dist_m'].mean():.1f} meters")
        st.metric("Maximum Distance to Pump", f"{deaths_gdf['dist_m'].max():.1f} meters")
        st.subheader("Distance Analysis")
        st.write(f"**Closest death to any pump:** {deaths_gdf['dist_m'].min():.1f} meters")
        st.write(f"**75% of deaths within:** {deaths_gdf['dist_m'].quantile(0.75):.1f} meters of a pump")

# ================================
# 6. SIDEBAR
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
- **💀 Red Points/Columns**: Cholera death locations
- **🚰 Blue Points/Towers**: Water pump locations
- **🔥 Heatmap**: Death density
- **🏗️ 3D Height**: Number of deaths
""")

st.sidebar.markdown("**🖱️ Interaction Guide**")
st.sidebar.markdown("""
- **Hover**: See detailed info
- **2D Map**: Basic spatial analysis
- **3D Map**: Enhanced depth perception
- **Click & Drag**: Navigate 3D view
""")

st.sidebar.success("💡 Pro Tip: Use 3D view to see the relationship between deaths and pumps!")
