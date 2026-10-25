import streamlit as st
import pandas as pd
import requests
from datetime import datetime


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

RISK_EMOJI = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}

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

@st.cache_data(ttl=600)
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
            <b style='color:#0f172a;'>📄 WARD HEAT ACTION BRIEF</b>
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
# SESSION STATE FOR OPENING PAGE
# ============================================================

if 'show_dashboard' not in st.session_state:
    st.session_state.show_dashboard = False


# ============================================================
# OPENING PAGE (SPLASH SCREEN)
# ============================================================

if not st.session_state.show_dashboard:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#7a2e2e 60%,#b33939 100%); border-radius:20px; padding:60px 40px; color:#ffffff; margin-bottom:40px; box-shadow:0 10px 30px rgba(0,0,0,0.3); text-align:center;'>
        <div style='font-size:60px; margin-bottom:10px;'>🌡️</div>
        <h1 style='font-size:48px; font-weight:800; margin:0; letter-spacing:1px;'>HeatBrief India</h1>
        <p style='font-size:20px; opacity:0.9; margin-top:15px; max-width:800px; margin-left:auto; margin-right:auto;'>
            Ward-Level Urban Heat Vulnerability Mapping & Automated Municipal Decision Briefs
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); height:100%;'>
            <div style='font-size:36px; margin-bottom:10px;'>📡</div>
            <h3 style='color:#1e3a5f; margin-bottom:10px;'>Live Data Sync</h3>
            <p style='color:#64748b; font-size:14px;'>Fetches real-time temperature via Open-Meteo API and estimates ward-level surface heat instantly.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); height:100%;'>
            <div style='font-size:36px; margin-bottom:10px;'>🧮</div>
            <h3 style='color:#1e3a5f; margin-bottom:10px;'>HVI Scoring Engine</h3>
            <p style='color:#64748b; font-size:14px;'>Calculates a 0-100 Heat Vulnerability Index using 6 weighted indicators (Heat, Concrete, Vulnerable Pop, etc.).</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:24px 20px; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.05); height:100%;'>
            <div style='font-size:36px; margin-bottom:10px;'>📄</div>
            <h3 style='color:#1e3a5f; margin-bottom:10px;'>Actionable Briefs</h3>
            <p style='color:#64748b; font-size:14px;'>Generates ready-to-approve municipal briefs with specific interventions and 2026 cost estimates.</p>
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
    if st.button("🏠 Back to Home", use_container_width=True):
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
    <div style='font-size:28px; font-weight:800;'>🌡️ HeatBrief India {live_chip}</div>
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
with k4: st.markdown(kpi_card("📈", "Avg Risk Score", f"{avg_score:.1f}", "out of 100", "#f1c40f"), unsafe_allow_html=True)

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
    st.download_button("⬇️ Download Priority List (CSV)", data=csv_data, file_name="priority_wards.csv", mime="text/csv")

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
