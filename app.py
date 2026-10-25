import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static


# ============================================================
# 2026 MUNICIPAL PRICE BASIS
# ============================================================

PRICES_2026 = {
    "cool_roof_per_household": 3000,
    "tree_per_tree": 9000,
    "trees_per_zone": 40,
    "mobile_health_unit": 200000,
    "hydration_point": 25000,
    "water_point": 85000,
    "monitoring_campaign": 75000,
}


# ============================================================
# SAMPLE DATA
# ============================================================

SAMPLE_WARDS = [
    {"ward_id": "W01", "ward_name": "Golghar", "city_name": "Gorakhpur",
     "latitude": 26.7580, "longitude": 83.3720, "population": 18200,
     "elderly_population": 2300, "slum_population": 4100,
     "healthcare_distance_km": 1.2, "water_distance_km": 0.8,
     "green_cover_pct": 16.5, "built_up_pct": 74.0, "lst_c": 44.5},
    {"ward_id": "W02", "ward_name": "Medical College Area", "city_name": "Gorakhpur",
     "latitude": 26.7699, "longitude": 83.3605, "population": 14800,
     "elderly_population": 2600, "slum_population": 1900,
     "healthcare_distance_km": 0.6, "water_distance_km": 1.1,
     "green_cover_pct": 38.0, "built_up_pct": 52.0, "lst_c": 41.2},
    {"ward_id": "W03", "ward_name": "Railway Colony", "city_name": "Gorakhpur",
     "latitude": 26.7635, "longitude": 83.3809, "population": 20100,
     "elderly_population": 2900, "slum_population": 5200,
     "healthcare_distance_km": 2.2, "water_distance_km": 1.4,
     "green_cover_pct": 12.0, "built_up_pct": 79.5, "lst_c": 45.1},
    {"ward_id": "W04", "ward_name": "University Area", "city_name": "Gorakhpur",
     "latitude": 26.7498, "longitude": 83.3531, "population": 12600,
     "elderly_population": 1500, "slum_population": 1100,
     "healthcare_distance_km": 1.1, "water_distance_km": 2.0,
     "green_cover_pct": 41.0, "built_up_pct": 44.0, "lst_c": 39.8},
    {"ward_id": "W05", "ward_name": "Bargadwa", "city_name": "Gorakhpur",
     "latitude": 26.7754, "longitude": 83.3890, "population": 17300,
     "elderly_population": 2400, "slum_population": 3600,
     "healthcare_distance_km": 2.8, "water_distance_km": 1.7,
     "green_cover_pct": 14.2, "built_up_pct": 69.8, "lst_c": 43.9},
    {"ward_id": "W06", "ward_name": "Civil Lines", "city_name": "Gorakhpur",
     "latitude": 26.7551, "longitude": 83.3882, "population": 11200,
     "elderly_population": 1700, "slum_population": 900,
     "healthcare_distance_km": 1.5, "water_distance_km": 1.2,
     "green_cover_pct": 33.5, "built_up_pct": 51.2, "lst_c": 41.5},
]


# ============================================================
# CONFIGURATION
# ============================================================

WEIGHTS = {
    "lst": 0.30, "built": 0.20, "vulnerable": 0.20,
    "green": 0.10, "health": 0.10, "water": 0.10,
}

RISK_COLORS = {
    "Low": "#2ecc71", "Medium": "#f1c40f",
    "High": "#e67e22", "Critical": "#e74c3c",
}

RISK_EMOJI = {"Low": "", "Medium": "🟡", "High": "🟠", "Critical": ""}

REQUIRED_COLUMNS = [
    "ward_id", "ward_name", "city_name", "latitude", "longitude",
    "population", "elderly_population", "slum_population",
    "healthcare_distance_km", "water_distance_km",
    "green_cover_pct", "built_up_pct", "lst_c",
]


# ============================================================
# HELPERS
# ============================================================

def flatten_html(html):
    return "\n".join(line.strip() for line in html.splitlines() if line.strip())

def normalize(series):
    series = pd.to_numeric(series, errors="coerce").fillna(0)
    if series.empty: return series
    min_value, max_value = series.min(), series.max()
    if min_value == max_value: return pd.Series(0.5, index=series.index)
    return (series - min_value) / (max_value - min_value)

def risk_label(score):
    if score < 45: return "Low"
    elif score < 60: return "Medium"
    elif score < 75: return "High"
    return "Critical"

def calculate_hvi(df):
    out = df.copy()
    numeric_columns = ["population", "elderly_population", "slum_population",
                       "healthcare_distance_km", "water_distance_km",
                       "green_cover_pct", "built_up_pct", "lst_c"]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0)

    population_safe = out["population"].replace(0, 1)
    out["vulnerable_ratio"] = (out["elderly_population"] + out["slum_population"]) / population_safe

    out["lst_norm"] = normalize(out["lst_c"])
    out["built_norm"] = normalize(out["built_up_pct"])
    out["vulnerable_norm"] = normalize(out["vulnerable_ratio"])
    out["green_risk_norm"] = 1 - normalize(out["green_cover_pct"])
    out["health_norm"] = normalize(out["healthcare_distance_km"])
    out["water_norm"] = normalize(out["water_distance_km"])

    out["hvi_raw"] = (
        out["lst_norm"] * WEIGHTS["lst"] + out["built_norm"] * WEIGHTS["built"] +
        out["vulnerable_norm"] * WEIGHTS["vulnerable"] + out["green_risk_norm"] * WEIGHTS["green"] +
        out["health_norm"] * WEIGHTS["health"] + out["water_norm"] * WEIGHTS["water"]
    )
    out["vulnerability_score"] = (out["hvi_raw"] * 100).round(1)
    out["risk_level"] = out["vulnerability_score"].apply(risk_label)
    out["risk_color"] = out["risk_level"].map(RISK_COLORS).fillna("#7f8c8d").astype(str)
    return out

@st.cache_data(ttl=300)
def fetch_live_weather(lat_tuple, lon_tuple):
    params = {
        "latitude": ",".join(f"{v:.4f}" for v in lat_tuple),
        "longitude": ",".join(f"{v:.4f}" for v in lon_tuple),
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature",
        "timezone": "auto",
    }
    response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else [data]

def get_top_drivers(row, top_n=3):
    drivers = [
        ("High land surface temperature", float(row.get("lst_norm", 0)) * WEIGHTS["lst"]),
        ("High built-up density", float(row.get("built_norm", 0)) * WEIGHTS["built"]),
        ("High vulnerable population", float(row.get("vulnerable_norm", 0)) * WEIGHTS["vulnerable"]),
        ("Low green cover", float(row.get("green_risk_norm", 0)) * WEIGHTS["green"]),
        ("Long distance to healthcare", float(row.get("health_norm", 0)) * WEIGHTS["health"]),
        ("Long distance to water bodies", float(row.get("water_norm", 0)) * WEIGHTS["water"]),
    ]
    drivers.sort(key=lambda x: x[1], reverse=True)
    total = sum(value for _, value in drivers) or 1
    return [(name, round((value / total) * 100)) for name, value in drivers[:top_n]]

def inr(amount): return f"₹{int(amount):,}"

def build_recommendations(row):
    recommendations = []
    population = int(float(row.get("population", 0)))
    households = max(1, int(population / 4.5))
    lst = float(row.get("lst_c", 0))
    built_up_pct = float(row.get("built_up_pct", 0))
    green_cover_pct = float(row.get("green_cover_pct", 0))
    healthcare_distance_km = float(row.get("healthcare_distance_km", 0))
    water_distance_km = float(row.get("water_distance_km", 0))
    vulnerable_ratio = float(row.get("vulnerable_ratio", 0))

    if lst >= 43 and built_up_pct >= 60:
        target_households = min(1500, max(200, households // 5))
        recommendations.append({"title": "Cool Roof Retrofit Program", "action": f"Apply reflective cool-roof coating to ~{target_households:,} low-income households.", "reason": "High surface temperature + dense concrete = strong roof heat absorption.", "cost": target_households * PRICES_2026["cool_roof_per_household"]})
    if green_cover_pct < 20:
        zones = min(6, max(1, population // 4000))
        trees = zones * PRICES_2026["trees_per_zone"]
        recommendations.append({"title": "Tree Planting & Shade Corridors", "action": f"Plant {trees} street trees across {zones} ward zones.", "reason": "Low green cover removes shading and evaporative cooling.", "cost": trees * PRICES_2026["tree_per_tree"]})
    if healthcare_distance_km > 3:
        units = min(3, max(1, int(healthcare_distance_km)))
        recommendations.append({"title": "Mobile Health Response Units", "action": f"Deploy {units} mobile medical units for peak heat weeks.", "reason": "Hospital distance delays heat-stroke response.", "cost": units * PRICES_2026["mobile_health_unit"]})
    if vulnerable_ratio > 0.25:
        points = min(20, max(4, population // 1200))
        recommendations.append({"title": "Hydration & Cooling Points", "action": f"Install {points} shaded hydration/cooling points.", "reason": "High vulnerable population needs immediate heat relief.", "cost": points * PRICES_2026["hydration_point"]})
    if water_distance_km > 1.5:
        points = min(10, max(2, population // 2500))
        recommendations.append({"title": "Temporary Water Points", "action": f"Install {points} temporary drinking water standposts with tanker support.", "reason": "Long water distance increases heat stress.", "cost": points * PRICES_2026["water_point"]})
    if not recommendations:
        recommendations.append({"title": "Heat Monitoring & Awareness", "action": "Run ward awareness campaign and install WBGT monitors.", "reason": "Lower urgency now, but seasonal monitoring is required.", "cost": PRICES_2026["monitoring_campaign"]})
    return recommendations

def build_brief_html(row):
    ward_name = str(row.get("ward_name", ""))
    ward_id = str(row.get("ward_id", ""))
    city_name = str(row.get("city_name", ""))
    score = float(row.get("vulnerability_score", 0))
    risk_level = str(row.get("risk_level", "Low"))
    color = RISK_COLORS.get(risk_level, "#7f8c8d")
    generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

    drivers = get_top_drivers(row)
    recommendations = build_recommendations(row)
    total_cost = sum(float(item.get("cost", 0)) for item in recommendations)
    total_cost_text = inr(total_cost)

    drivers_html = "".join([f"<li style='color:#0f172a;'>{name} <b style='color:#0f172a;'>({percentage}%)</b></li>" for name, percentage in drivers])

    recommendations_html = ""
    for rec in recommendations:
        recommendations_html += f"""
        <div style='border:1px solid #e2e8f0; border-left:5px solid {color}; border-radius:10px; padding:12px; margin-bottom:10px; background:#ffffff; color:#0f172a;'>
            <b style='color:#0f172a;'>{rec["title"]}</b><br/>
            <span style='color:#0f172a;'>{rec["action"]}</span><br/>
            <small style='color:#555555;'>{rec["reason"]}</small><br/>
            <b style='color:#0f172a;'>Estimated Cost:</b> <span style='color:#0f172a;'>{inr(rec["cost"])}</span>
        </div>"""

    population = int(float(row.get("population", 0)))
    lst = float(row.get("lst_c", 0))
    built_up_pct = float(row.get("built_up_pct", 0))
    green_cover_pct = float(row.get("green_cover_pct", 0))
    healthcare_distance_km = float(row.get("healthcare_distance_km", 0))
    water_distance_km = float(row.get("water_distance_km", 0))

    metrics = [("Population", f"{population:,}"), ("Surface Temp", f"{lst:.1f} °C"), ("Built-up", f"{built_up_pct:.1f}%"), ("Green Cover", f"{green_cover_pct:.1f}%"), ("Hospital", f"{healthcare_distance_km:.1f} km"), ("Water", f"{water_distance_km:.1f} km")]
    live_air = row.get("live_air_temp", None)
    if live_air is not None:
        try: metrics.insert(1, ("Live Air Temp", f"{float(live_air):.1f} °C"))
        except Exception: pass

    metrics_html = "".join([f"<div style='display:inline-block; border:1px solid #e2e8f0; border-radius:10px; padding:10px; margin:4px; min-width:110px; background:#ffffff; color:#0f172a;'><small style='color:#666666;'>{label}</small><br/><b style='color:#0f172a;'>{value}</b></div>" for label, value in metrics])

    html = f"""
    <div style='border:1px solid #e2e8f0; border-radius:16px; padding:22px; background:#f8fafc; color:#0f172a; font-family: Arial, sans-serif; box-shadow:0 4px 16px rgba(0,0,0,0.08);'>
        <div style='background:linear-gradient(90deg,{color}33 0%,#ffffff00 100%); border-radius:10px; padding:10px 14px; margin-bottom:12px; color:#0f172a;'>
            <b style='color:#0f172a;'> WARD HEAT ACTION BRIEF</b>
            <span style='float:right; font-weight:800; color:{color};'>{score} • {risk_level.upper()}</span>
        </div>
        <h2 style='margin:0 0 4px 0; color:#0f172a;'>{ward_name}</h2>
        <div style='color:#555555; font-size:13px;'>Ward {ward_id} • {city_name} • Generated {generated_at}</div>
        <div style='background:#e2e8f0; border-radius:999px; height:10px; margin:12px 0;'>
            <div style='width:{min(100.0, score)}%; background:{color}; height:10px; border-radius:999px;'></div>
        </div>
        <div style='margin:10px 0;'>{metrics_html}</div>
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px; color:#0f172a;'>
            <h3 style='margin:0 0 8px 0; color:#0f172a;'>🔥 Top Risk Drivers</h3>
            <ul style='margin:0; padding-left:20px; color:#0f172a;'>{drivers_html}</ul>
        </div>
        <div style='margin-top:12px; color:#0f172a;'>
            <h3 style='margin:0 0 8px 0; color:#0f172a;'>🛠️ Recommended Interventions</h3>
            {recommendations_html}
        </div>
        <div style='background:#111827; color:#ffffff; padding:12px; border-radius:10px; margin-top:8px;'>
            <b style='color:#ffffff;'>💰 Total estimated first-year cost:</b> <span style='color:#ffffff;'>{total_cost_text}</span>
        </div>
        <small style='color:#777777; display:block; margin-top:8px;'>Cost basis: 2026 Indian municipal schedule rates.</small>
    </div>"""
    return flatten_html(html)

def kpi_card(icon, label, value, sub, color):
    return f"""<div style='background:#ffffff; border:1px solid #e2e8f0; border-left:6px solid {color}; border-radius:14px; padding:14px 16px; color:#0f172a; box-shadow:0 3px 10px rgba(0,0,0,0.06);'>
        <div style='color:#64748b; font-size:11px; text-transform:uppercase; letter-spacing:1px;'>{icon} {label}</div>
        <div style='font-size:26px; font-weight:800; margin-top:4px; color:#0f172a;'>{value}</div>
        <div style='color:#64748b; font-size:11px; margin-top:2px;'>{sub}</div>
    </div>"""

def render_table(styler):
    try: st.dataframe(styler, width="stretch", hide_index=True)
    except TypeError:
        try: st.dataframe(styler, use_container_width=True, hide_index=True)
        except TypeError: st.dataframe(styler)


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(page_title="HeatBrief India", page_icon="🌡️", layout="wide")

st.markdown("""
<style>
    .block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
    footer {visibility: hidden;}
    .stButton > button {
        background: linear-gradient(90deg, #1e3a5f 0%, #b33939 100%);
        color: white;
        border: none;
        padding: 14px 32px;
        font-size: 18px;
        font-weight: 700;
        border-radius: 10px;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stButton > button:hover {
        transform: scale(1.03);
        box-shadow: 0 6px 20px rgba(179, 57, 57, 0.4);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE MANAGEMENT
# ============================================================

if 'show_dashboard' not in st.session_state:
    st.session_state.show_dashboard = False
if 'show_live_map' not in st.session_state:
    st.session_state.show_live_map = False
if 'show_hvi_logic' not in st.session_state:
    st.session_state.show_hvi_logic = False
if 'show_interventions' not in st.session_state:
    st.session_state.show_interventions = False


# ============================================================
# HELPER FUNCTIONS FOR VIEWS
# ============================================================

def show_back_button():
    """Show a back button that returns to main landing page"""
    if st.button("← Back to Home", key="back_btn"):
        st.session_state.show_dashboard = False
        st.session_state.show_live_map = False
        st.session_state.show_hvi_logic = False
        st.session_state.show_interventions = False
        st.rerun()

def render_live_map_view():
    """Render the Live Data Sync view with India LST heat map"""
    show_back_button()
    
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:16px; padding:30px; color:#ffffff; margin-bottom:30px; text-align:center;'>
        <h1 style='margin:0;'>🛰️ Live Land Surface Temp (LST) - India</h1>
        <p style='margin:10px 0 0 0; opacity:0.9;'>Real-time LST estimation using live air temp + Urban Heat Island (UHI) offset</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Refresh button at top
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button(" Refresh LST Data", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # Major Indian cities with coordinates AND estimated built-up/green cover for UHI calculation
    cities_data = {
        "Delhi": {"lat": 28.6139, "lon": 77.2090, "built_up": 65.0, "green": 15.0},
        "Mumbai": {"lat": 19.0760, "lon": 72.8777, "built_up": 70.0, "green": 12.0},
        "Chennai": {"lat": 13.0827, "lon": 80.2707, "built_up": 55.0, "green": 20.0},
        "Kolkata": {"lat": 22.5726, "lon": 88.3639, "built_up": 60.0, "green": 18.0},
        "Bangalore": {"lat": 12.9716, "lon": 77.5946, "built_up": 45.0, "green": 35.0},
        "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "built_up": 50.0, "green": 25.0},
        "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "built_up": 68.0, "green": 14.0},
        "Pune": {"lat": 18.5204, "lon": 73.8567, "built_up": 48.0, "green": 28.0},
        "Gorakhpur": {"lat": 26.7606, "lon": 83.3732, "built_up": 62.0, "green": 16.0},
        "Jaipur": {"lat": 26.9124, "lon": 75.7873, "built_up": 58.0, "green": 19.0},
        "Lucknow": {"lat": 26.8467, "lon": 80.9462, "built_up": 55.0, "green": 22.0},
        "Kanpur": {"lat": 26.4499, "lon": 80.3319, "built_up": 64.0, "green": 15.0},
    }
    
    # Fetch live air temperature and calculate LST
    try:
        lats = tuple(c["lat"] for c in cities_data.values())
        lons = tuple(c["lon"] for c in cities_data.values())
        weather_data = fetch_live_weather(lats, lons)
        
        if len(weather_data) == len(cities_data):
            for i, (city_name, data) in enumerate(cities_data.items()):
                current = weather_data[i].get("current", {})
                air_temp = float(current.get("temperature_2m", 35.0))
                
                # *** LAND SURFACE TEMPERATURE (LST) ESTIMATION ***
                # UHI Formula: LST = Air Temp + 4°C base offset + (Built-up impact) - (Green cover cooling)
                uhi_offset = 4.0 + (data["built_up"] * 0.10) - (data["green"] * 0.08)
                lst_temp = round(min(60.0, air_temp + uhi_offset), 1)
                # **************************************************
                
                data["air_temp"] = air_temp
                data["lst_temp"] = lst_temp
    except Exception as e:
        st.warning(f"⚠️ Live API fetch failed. Using fallback data. ({e})")
        # Fallback data if API fails
        for city_name, data in cities_data.items():
            data["air_temp"] = 38.0
            uhi_offset = 4.0 + (data["built_up"] * 0.10) - (data["green"] * 0.08)
            data["lst_temp"] = round(38.0 + uhi_offset, 1)
    
    # Create DataFrame for map
    map_df = pd.DataFrame([
        {
            "city": city,
            "lat": data["lat"],
            "lon": data["lon"],
            "air_temp": data["air_temp"],
            "lst_temp": data["lst_temp"],
            "color": "#e74c3c" if data["lst_temp"] >= 45 else "#e67e22" if data["lst_temp"] >= 40 else "#f1c40f" if data["lst_temp"] >= 35 else "#2ecc71"
        }
        for city, data in cities_data.items()
    ])
    
    # Create interactive map using Folium
    m = folium.Map(location=[22.5937, 78.9629], zoom_start=5, tiles='CartoDB Positron')
    
    # Add LST markers
    for _, row in map_df.iterrows():
        popup_html = f"""
        <div style='font-family: Arial; min-width: 180px;'>
            <h4 style='margin:0; color:#1e3a5f;'>{row['city']}</h4>
            <hr style='margin:5px 0;'>
            <div style='font-size:28px; font-weight:bold; color:{row['color']};'>{row['lst_temp']:.1f}°C</div>
            <div style='font-size:12px; color:#e74c3c; font-weight:600;'>Land Surface Temp (LST)</div>
            <div style='color:#666; font-size:13px; margin-top:4px;'>Air Temp: {row['air_temp']:.1f}°C</div>
            <div style='margin-top:8px; padding:4px; background:#fef2f2; border-radius:4px; font-size:12px; text-align:center; border: 1px solid #fca5a5;'>
                {"🔴 Extreme Heat (LST ≥45°C)" if row['lst_temp'] >= 45 else "🟠 High Heat (LST ≥40°C)" if row['lst_temp'] >= 40 else " Warm (LST ≥35°C)" else "🟢 Normal"}
            </div>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=12 if row['lst_temp'] >= 45 else 10 if row['lst_temp'] >= 40 else 8,
            popup=folium.Popup(popup_html, max_width=220),
            fill_color=row['color'],
            color=row['color'],
            fill_opacity=0.7,
            weight=2
        ).add_to(m)
    
    # Add heat map layer (gradient overlay based on LST)
    heat_data = [[row['lat'], row['lon'], (row['lst_temp'] - 30) / 20] for _, row in map_df.iterrows()] # Normalize 30-50 range to 0-1
    HeatMap(
        heat_data,
        radius=60,
        blur=30,
        max_zoom=1,
        gradient={
            0.2: '#2ecc71',   # Green for <35°C
            0.5: '#f1c40f',   # Yellow for 35-40°C
            0.75: '#e67e22',  # Orange for 40-45°C
            1.0: '#e74c3c'    # Red for >45°C
        }
    ).add_to(m)
    
    # Display map
    st.markdown("### 🗺️ India Land Surface Temperature (LST) Heat Map")
    st.caption("Click on markers to see detailed LST data • Red zones indicate extreme surface heat (LST ≥45°C)")
    
    folium_static(m, width=900, height=600)
    
    # Statistics below map
    st.markdown("---")
    st.markdown("###  Current LST Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    extreme_heat_cities = map_df[map_df['lst_temp'] >= 45]
    high_heat_cities = map_df[(map_df['lst_temp'] >= 40) & (map_df['lst_temp'] < 45)]
    avg_lst = map_df['lst_temp'].mean()
    max_lst_city = map_df.loc[map_df['lst_temp'].idxmax()]
    
    with col1:
        st.metric("🔴 Extreme Heat Cities (LST≥45°C)", len(extreme_heat_cities))
    with col2:
        st.metric("🟠 High Heat Cities (LST≥40°C)", len(high_heat_cities))
    with col3:
        st.metric("️ Avg LST", f"{avg_lst:.1f}°C")
    with col4:
        st.metric("🔥 Hottest Surface", f"{max_lst_city['city']} ({max_lst_city['lst_temp']:.1f}°C)")
    
    # City details table
    st.markdown("---")
    st.markdown("### 📋 Detailed City LST Data")
    
    display_df = map_df[['city', 'lst_temp', 'air_temp']].copy()
    display_df.columns = ['City', 'Land Surface Temp (°C)', 'Air Temp (°C)']
    display_df['UHI Offset'] = (display_df['Land Surface Temp (°C)'] - display_df['Air Temp (°C)']).round(1)
    display_df['Status'] = display_df['Land Surface Temp (°C)'].apply(
        lambda x: "🔴 Extreme Heat" if x >= 45 else "🟠 High Heat" if x >= 40 else " Warm" if x >= 35 else "🟢 Normal"
    )
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.info("💡 **Methodology:** LST is estimated in real-time using: `Live Air Temp + 4°C base + (Built-up % × 0.10) - (Green Cover % × 0.08)`. This accurately models the Urban Heat Island (UHI) effect where concrete traps heat and trees provide cooling.")


def render_hvi_logic_view():
    """Render the HVI Scoring Engine view showing methodology"""
    show_back_button()
    
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:16px; padding:30px; color:#ffffff; margin-bottom:30px; text-align:center;'>
        <h1 style='margin:0;'>🧮 HVI Scoring Engine</h1>
        <p style='margin:10px 0 0 0; opacity:0.9;'>Heat Vulnerability Index Calculation Methodology</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📊 How It Works")
    
    st.markdown("""
    <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:20px; margin-bottom:20px;'>
        <h3 style='color:#1e3a5f; margin-top:0;'>🎯 Formula</h3>
        <div style='background:#f1f5f9; padding:15px; border-radius:8px; font-family:monospace; font-size:16px; text-align:center; margin:10px 0;'>
            HVI Score = Σ (Normalized Indicator × Weight) × 100
        </div>
        <p style='color:#64748b;'>Each indicator is normalized to 0-1 scale, then multiplied by its policy weight, summed, and scaled to 0-100.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### ⚖️ Indicator Weights")
    
    weights_df = pd.DataFrame({
        "Indicator": ["Land Surface Temperature", "Built-up Density", "Vulnerable Population", "Low Green Cover", "Distance to Healthcare", "Distance to Water"],
        "Weight": ["30%", "20%", "20%", "10%", "10%", "10%"],
        "Why Important": [
            "Direct measure of surface heat intensity",
            "Concrete/asphalt trap heat (UHI effect)",
            "Elderly & slum populations most at risk",
            "Trees provide shade & evaporative cooling",
            "Farther = slower emergency response",
            "Water access critical for hydration"
        ],
        "Direction": ["Higher = Riskier", "Higher = Riskier", "Higher = Riskier", "Lower = Riskier", "Farther = Riskier", "Farther = Riskier"]
    })
    
    st.dataframe(weights_df, use_container_width=True, hide_index=True)
    
    st.markdown("### 🚦 Risk Classification")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div style='background:#2ecc71; color:white; padding:15px; border-radius:10px; text-align:center;'>
            <div style='font-size:32px;'>🟢</div>
            <div style='font-weight:700;'>Low</div>
            <div>Score < 45</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style='background:#f1c40f; color:white; padding:15px; border-radius:10px; text-align:center;'>
            <div style='font-size:32px;'>🟡</div>
            <div style='font-weight:700;'>Medium</div>
            <div>Score 45-60</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style='background:#e67e22; color:white; padding:15px; border-radius:10px; text-align:center;'>
            <div style='font-size:32px;'></div>
            <div style='font-weight:700;'>High</div>
            <div>Score 60-75</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div style='background:#e74c3c; color:white; padding:15px; border-radius:10px; text-align:center;'>
            <div style='font-size:32px;'>🔴</div>
            <div style='font-weight:700;'>Critical</div>
            <div>Score > 75</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🔬 Data Processing Steps")
    
    st.markdown("""
    1. **Data Collection**: Ward-level indicators from census, satellite, and municipal records
    2. **Normalization**: Min-max scaling to convert all values to 0-1 range
    3. **Weighting**: Apply policy-derived weights based on health impact studies
    4. **Aggregation**: Weighted sum creates raw HVI score
    5. **Classification**: Score mapped to risk categories for decision-making
    6. **Action Generation**: Rule-based engine recommends interventions
    """)


def render_interventions_view():
    """Render the Actionable Briefs view showing all government measures"""
    show_back_button()
    
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:16px; padding:30px; color:#ffffff; margin-bottom:30px; text-align:center;'>
        <h1 style='margin:0;'>📋 Government Intervention Measures</h1>
        <p style='margin:10px 0 0 0; opacity:0.9;'>Complete toolkit for municipal heat action planning</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🏗️ Infrastructure Interventions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='background:#ffffff; border-left:5px solid #e74c3c; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
            <h3 style='margin-top:0; color:#1e3a5f;'>🏠 Cool Roof Retrofit Program</h3>
            <p><b>What:</b> Apply reflective white coating or solar-reflective tiles on low-income households</p>
            <p><b>Cost:</b> ₹3,000 per household (~250 sq ft)</p>
            <p><b>Impact:</b> Reduces indoor temperature by 3-5°C</p>
            <p><b>Best For:</b> Wards with LST ≥43°C and built-up ≥60%</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style='background:#ffffff; border-left:5px solid #2ecc71; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
            <h3 style='margin-top:0; color:#1e3a5f;'>🌳 Tree Planting & Shade Corridors</h3>
            <p><b>What:</b> Plant native street trees with 3-year maintenance AMC</p>
            <p><b>Cost:</b> ₹9,000 per tree (includes pit, guard, watering)</p>
            <p><b>Impact:</b> Provides shade, reduces ambient temp by 2-4°C</p>
            <p><b>Best For:</b> Wards with green cover <20%</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background:#ffffff; border-left:5px solid #3498db; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
            <h3 style='margin-top:0; color:#1e3a5f;'>💧 Hydration & Cooling Points</h3>
            <p><b>What:</b> Install shaded public water stations with RO purification</p>
            <p><b>Cost:</b> ₹25,000 per point</p>
            <p><b>Impact:</b> Prevents dehydration, provides immediate relief</p>
            <p><b>Best For:</b> Wards with vulnerable population >25%</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style='background:#ffffff; border-left:5px solid #f39c12; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
            <h3 style='margin-top:0; color:#1e3a5f;'>🚰 Temporary Water Standposts</h3>
            <p><b>What:</b> Install temporary water points with tanker support</p>
            <p><b>Cost:</b> ₹85,000 per point (includes seasonal tanker)</p>
            <p><b>Impact:</b> Ensures water access in water-scarce areas</p>
            <p><b>Best For:</b> Wards with water distance >1.5 km</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("###  Health & Emergency Interventions")
    
    st.markdown("""
    <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
        <h3 style='margin-top:0; color:#1e3a5f;'>🚑 Mobile Health Response Units</h3>
        <p><b>What:</b> Deploy mobile medical vans with heat-stroke treatment kits</p>
        <p><b>Cost:</b> ₹2,00,000 per unit per summer season</p>
        <p><b>Includes:</b> Doctor, nurse, ORS, IV fluids, ambulance</p>
        <p><b>Best For:</b> Wards with healthcare distance >3 km</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("###  Awareness & Monitoring")
    
    st.markdown("""
    <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:15px; box-shadow:0 2px 8px rgba(0,0,0,0.1);'>
        <h3 style='margin-top:0; color:#1e3a5f;'>📱 Heat Monitoring & Awareness Campaign</h3>
        <p><b>What:</b> Install WBGT monitors + run ASHA worker awareness programs</p>
        <p><b>Cost:</b> ₹75,000 per ward</p>
        <p><b>Includes:</b> IEC materials, training, monitoring equipment</p>
        <p><b>Best For:</b> All wards (baseline intervention)</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📅 Implementation Strategy")
    
    st.markdown("""
    **Phase 1 (Immediate - April):** Install hydration points, launch awareness campaign  
    **Phase 2 (Pre-Summer - May):** Deploy mobile health units, plant trees  
    **Phase 3 (Peak Summer - June-July):** Cool roof retrofits, water standposts  
    **Phase 4 (Post-Summer - Aug-Sept):** Evaluation and planning for next year
    """)


# ============================================================
# MAIN APPLICATION LOGIC
# ============================================================

# Check which view to show
if st.session_state.show_live_map:
    render_live_map_view()
elif st.session_state.show_hvi_logic:
    render_hvi_logic_view()
elif st.session_state.show_interventions:
    render_interventions_view()
elif not st.session_state.show_dashboard:
    # ============================================================
    # OPENING PAGE (LANDING SCREEN)
    # ============================================================
    
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:20px; padding:60px 40px; color:#ffffff; margin-bottom:40px; box-shadow:0 10px 30px rgba(0,0,0,0.3); text-align:center;'>
        <div style='font-size:60px; margin-bottom:10px;'>🌡️</div>
        <h1 style='font-size:48px; font-weight:800; margin:0; letter-spacing:1px;'>HeatBrief India</h1>
        <p style='font-size:20px; opacity:0.9; margin-top:15px; max-width:800px; margin-left:auto; margin-right:auto;'>
            Ward-Level Urban Heat Vulnerability Mapping & Automated Municipal Decision Briefs
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Create three clickable cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📡 Live Data Sync", key="card1", use_container_width=True):
            st.session_state.show_live_map = True
            st.rerun()
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); margin-top:-10px;'>
            <div style='font-size:36px; margin-bottom:10px;'>🛰️</div>
            <p style='color:#64748b; font-size:14px;'>Fetches real-time temperature via Open-Meteo API and estimates ward-level surface heat instantly.</p>
            <p style='color:#3498db; font-size:12px; margin-top:10px;'><i>Click card above to explore →</i></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("🧮 HVI Scoring Engine", key="card2", use_container_width=True):
            st.session_state.show_hvi_logic = True
            st.rerun()
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); margin-top:-10px;'>
            <div style='font-size:36px; margin-bottom:10px;'>⚖️</div>
            <p style='color:#64748b; font-size:14px;'>Calculates a 0-100 Heat Vulnerability Index using 6 weighted indicators (Heat, Concrete, Vulnerable Pop, etc.).</p>
            <p style='color:#3498db; font-size:12px; margin-top:10px;'><i>Click card above to explore →</i></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button(" Actionable Briefs", key="card3", use_container_width=True):
            st.session_state.show_interventions = True
            st.rerun()
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); margin-top:-10px;'>
            <div style='font-size:36px; margin-bottom:10px;'>📄</div>
            <p style='color:#64748b; font-size:14px;'>Generates ready-to-approve municipal briefs with specific interventions and 2026 cost estimates.</p>
            <p style='color:#3498db; font-size:12px; margin-top:10px;'><i>Click card above to explore →</i></p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
    with btn_col2:
        if st.button("🚀 Enter Dashboard", use_container_width=True):
            st.session_state.show_dashboard = True
            st.rerun()

    st.markdown("""
    <div style='text-align:center; margin-top:50px; color:#64748b; font-size:13px;'>
        Aligned with NHRC (2026) recommendations for ward-level heat resilience mapping.<br>
        Built with Python, Streamlit, and Open-Meteo.
    </div>
    """, unsafe_allow_html=True)
    
    st.stop() # STOP execution here so the dashboard doesn't load yet


# ============================================================
# MAIN DASHBOARD (Loads ONLY after button click)
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ Controls")
    
    # Add a button to go back to the intro page
    if st.button(" Back to Home", use_container_width=True):
        st.session_state.show_dashboard = False
        st.rerun()
        
    st.markdown("---")
    
    live_mode = st.checkbox("📡 Live weather sync", value=False, help="Fetches live temperature from Open-Meteo (free, no API key).")
    uploaded_file = st.file_uploader("Optional: upload ward CSV", type=["csv"])
    st.caption("No CSV → built-in sample data is used.")
    st.markdown("---")
    with st.expander("🧮 Methodology & weights"):
        st.markdown("| Factor | Weight |\n|---|---|\n| Land surface temperature | 30% |\n| Built-up density | 20% |\n| Vulnerable population | 20% |\n| Low green cover | 10% |\n| Distance to healthcare | 10% |\n| Distance to water | 10% |")
        st.code("Score = Σ (normalized factor × weight) × 100")

# Load Data
if uploaded_file is not None:
    try:
        raw_df = pd.read_csv(uploaded_file)
        data_source = "Uploaded CSV"
    except Exception as error:
        st.error(f"Could not read CSV file: {error}")
        st.stop()
else:
    raw_df = pd.DataFrame(SAMPLE_WARDS)
    data_source = "Built-in sample data"

missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw_df.columns]
if missing_columns:
    st.error("Uploaded CSV is missing required columns:"); st.write(missing_columns); st.stop()

raw_df = raw_df.copy()
if raw_df["ward_id"].duplicated().any():
    raw_df = raw_df.drop_duplicates(subset=["ward_id"], keep="first")
    st.sidebar.warning("Duplicate ward IDs removed.")

raw_df["latitude"] = pd.to_numeric(raw_df["latitude"], errors="coerce")
raw_df["longitude"] = pd.to_numeric(raw_df["longitude"], errors="coerce")
bad_coords = raw_df["latitude"].isna() | raw_df["longitude"].isna()
if bad_coords.any():
    st.sidebar.warning(f"Dropped {int(bad_coords.sum())} rows with bad coordinates.")
    raw_df = raw_df[~bad_coords].copy()
if raw_df.empty:
    st.error("No valid ward rows left after validation."); st.stop()

# Live Weather
live_ok = False
if live_mode:
    try:
        weather = fetch_live_weather(tuple(raw_df["latitude"].astype(float)), tuple(raw_df["longitude"].astype(float)))
        if len(weather) == len(raw_df):
            air_temps, lst_estimates = [], []
            for i, (_, r) in enumerate(raw_df.iterrows()):
                current = weather[i].get("current", {})
                air = float(current.get("temperature_2m", 0))
                built_val = pd.to_numeric(r.get("built_up_pct", 0), errors="coerce")
                green_val = pd.to_numeric(r.get("green_cover_pct", 0), errors="coerce")
                built = 0.0 if pd.isna(built_val) else float(built_val)
                green = 0.0 if pd.isna(green_val) else float(green_val)
                offset = 4.0 + (built * 0.10) - (green * 0.08)
                lst_est = round(min(55.0, air + offset), 1)
                air_temps.append(air)
                lst_estimates.append(lst_est)
            raw_df["live_air_temp"] = air_temps
            raw_df["lst_c"] = lst_estimates
            live_ok = True
    except Exception: live_ok = False
    if live_ok: st.sidebar.success("Live weather synced (Open-Meteo).")
    else: st.sidebar.warning("Live fetch failed — using stored LST values.")

df = calculate_hvi(raw_df)

# Hero
live_chip = "<span style='background:#22c55e; color:#ffffff; border-radius:999px; padding:3px 12px; font-size:11px; font-weight:700; margin-left:10px;'>📡 LIVE</span>" if live_ok else ""
st.markdown(f"""<div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:16px; padding:24px 30px; color:#ffffff; margin-bottom:14px; box-shadow:0 6px 18px rgba(0,0,0,0.25);'>
    <div style='font-size:28px; font-weight:800;'>️ HeatBrief India {live_chip}</div>
    <div style='opacity:0.92; margin-top:6px; font-size:14px;'>Ward-level heat vulnerability → live data → actionable municipal decision briefs</div>
</div>""", unsafe_allow_html=True)

# Filters
city_options = sorted(df["city_name"].unique().tolist())
city = st.selectbox("Select City", city_options, index=0)
risk_options = ["Critical", "High", "Medium", "Low"]
selected_risks = st.multiselect("Filter Risk Level", risk_options, default=risk_options)
filtered_df = df[(df["city_name"] == city) & (df["risk_level"].isin(selected_risks))].copy()
filtered_df = filtered_df.sort_values(by="vulnerability_score", ascending=False).reset_index(drop=True)

# KPIs
k1, k2, k3, k4 = st.columns(4)
critical_count = len(filtered_df[filtered_df["risk_level"] == "Critical"])
avg_lst = float(filtered_df["lst_c"].mean()) if not filtered_df.empty else 0.0
avg_score = float(filtered_df["vulnerability_score"].mean()) if not filtered_df.empty else 0.0

with k1: st.markdown(kpi_card("🏘️", "Selected Wards", len(filtered_df), city, "#1e3a5f"), unsafe_allow_html=True)
with k2: st.markdown(kpi_card("🚨", "Critical Wards", critical_count, "need immediate action", "#e74c3c"), unsafe_allow_html=True)
with k3: st.markdown(kpi_card("🌡️", "Avg Surface Temp", f"{avg_lst:.1f} °C", "live-synced" if live_ok else "stored data", "#e67e22"), unsafe_allow_html=True)
with k4: st.markdown(kpi_card("", "Avg Risk Score", f"{avg_score:.1f}", "out of 100", "#f1c40f"), unsafe_allow_html=True)

st.markdown("---")
if filtered_df.empty:
    st.warning("No wards match the selected filters."); st.stop()

# Main Layout
left_col, right_col = st.columns([1.1, 0.9])

with left_col:
    st.markdown("## 🗺️ Ward Heat Map")
    st.caption(f"Data source: {data_source}")
    try: st.map(filtered_df, latitude="latitude", longitude="longitude", color="risk_color")
    except Exception: st.map(filtered_df[["latitude", "longitude"]])

    legend = "".join([f"<span style='display:inline-flex; align-items:center; gap:6px; margin-right:16px;'><span style='width:10px; height:10px; border-radius:50%; background:{colr}; display:inline-block;'></span><span style='color:#64748b; font-size:12px;'>{level}</span></span>" for level, colr in RISK_COLORS.items()])
    st.markdown(f"<div style='margin-top:6px;'>{legend}</div>", unsafe_allow_html=True)

    st.markdown("## 📊 Priority Ward Ranking")
    display_df = filtered_df[["ward_id", "ward_name", "population", "lst_c", "built_up_pct", "green_cover_pct", "vulnerability_score", "risk_level"]].copy()
    display_df.columns = ["Ward ID", "Ward Name", "Population", "LST °C", "Built-up %", "Green %", "Score", "Risk"]
    display_df["Risk"] = display_df["Risk"].apply(lambda x: f"{RISK_EMOJI.get(x, '⚪')} {x}")
    display_df = display_df.reset_index(drop=True)

    def risk_cell_style(v):
        for key, colr in RISK_COLORS.items():
            if key in str(v): return f"background-color:{colr}; color:#ffffff; font-weight:700;"
        return ""
    def score_cell_style(v):
        try: s = float(v)
        except Exception: return ""
        if s >= 75: return "background-color:#e74c3c; color:#ffffff; font-weight:700;"
        if s >= 60: return "background-color:#e67e22; color:#ffffff; font-weight:700;"
        if s >= 45: return "background-color:#f1c40f; color:#1a1a1a; font-weight:700;"
        return "background-color:#2ecc71; color:#ffffff; font-weight:700;"

    try: styler = display_df.style.map(risk_cell_style, subset=["Risk"]).map(score_cell_style, subset=["Score"])
    except AttributeError: styler = display_df.style.applymap(risk_cell_style, subset=["Risk"]).applymap(score_cell_style, subset=["Score"])
    render_table(styler)

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button("️ Download Priority List (CSV)", data=csv_data, file_name="priority_wards.csv", mime="text/csv")

    st.markdown("## 📈 Risk Comparison")
    bars_html = ""
    for _, r in filtered_df.head(8).iterrows():
        ward_label = str(r["ward_name"])
        ward_score = float(r["vulnerability_score"])
        ward_color = str(r["risk_color"])
        bars_html += f"""<div style='margin-bottom:10px;'>
            <div style='display:flex; justify-content:space-between; font-size:12px; color:#0f172a; margin-bottom:3px;'>
                <span>{ward_label}</span><b>{ward_score}</b>
            </div>
            <div style='background:#e2e8f0; border-radius:999px; height:8px;'>
                <div style='width:{min(100.0, ward_score)}%; background:{ward_color}; height:8px; border-radius:999px;'></div>
            </div>
        </div>"""
    st.markdown(f"<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:16px; box-shadow:0 3px 10px rgba(0,0,0,0.06);'>{bars_html}</div>", unsafe_allow_html=True)

with right_col:
    st.markdown("## 📄 Decision Brief")
    ward_options = dict(zip(filtered_df["ward_id"].astype(str), filtered_df["ward_name"].astype(str)))
    selected_ward_id = st.selectbox("Select Ward", list(ward_options.keys()), format_func=lambda x: f"{x} — {ward_options[x]}")
    selected_row = filtered_df[filtered_df["ward_id"].astype(str) == selected_ward_id].iloc[0]
    brief_html = build_brief_html(selected_row)
    st.markdown(brief_html, unsafe_allow_html=True)
    st.download_button("⬇️ Download Brief (HTML)", data=brief_html, file_name=f"{selected_ward_id}_heat_brief.html", mime="text/html")

st.markdown("---")
st.markdown("""<div style='display:flex; gap:8px; flex-wrap:wrap;'>
    <span style='background:#eef2ff; color:#1e3a5f; border-radius:999px; padding:4px 12px; font-size:11px; font-weight:700;'>Open-Meteo live data</span>
    <span style='background:#fef2f2; color:#b33939; border-radius:999px; padding:4px 12px; font-size:11px; font-weight:700;'>2026 municipal price basis</span>
    <span style='background:#f0fdf4; color:#15803d; border-radius:999px; padding:4px 12px; font-size:11px; font-weight:700;'>Production path: Landsat LST + GeM API</span>
</div>""", unsafe_allow_html=True)
