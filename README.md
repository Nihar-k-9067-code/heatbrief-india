<div align="center">

# 🌡️ HeatBrief India

### Ward-Level Urban Heat Vulnerability Mapping & Automated Municipal Decision Briefs

[![Built with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Pandas](https://img.shields.io/badge/Data-Pandas-150458?style=flat-square&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![Live Data](https://img.shields.io/badge/Live%20Data-Open--Meteo-22c55e?style=flat-square)](https://open-meteo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

*Turning open heat, census and live weather data into **actionable municipal decisions** — not just dashboards.*

**🔗 Live Demo:** *(deploy on Streamlit Community Cloud and paste your link here)*
**📦 Repo:** [github.com/Nihar-k-9067-code/heatbrief-india](https://github.com/Nihar-k-9067-code/heatbrief-india)

</div>

---

## 🚨 The Problem

Indian cities face increasingly lethal urban heatwaves, yet:

- Heat warnings are **city-wide averages** that hide dangerous ward-level variation.
- **4,800+ Urban Local Bodies** have no in-house GIS teams to interpret satellite data.
- Heat Action Plans stall because officers receive **temperature maps**, not answers to *"which ward, what action, at what cost?"*

## 💡 The Solution

**HeatBrief India** is a pure-software decision-support platform that:

1. Computes a **ward-level Heat Vulnerability Index (HVI, 0–100)** from heat, infrastructure and social indicators.
2. Optionally syncs **live weather** from the free Open-Meteo API and re-estimates surface heat per ward.
3. Auto-generates **plain-language decision briefs**: priority wards, top risk drivers, recommended interventions and **estimated costs based on 2026 municipal schedule rates**.
4. Exports everything as **HTML briefs** and **CSV priority lists** ready for municipal workflows.

> 🎯 **One-line pitch:** *"HeatBrief India tells city officers which ward to act on, what to do, and what it will cost — before summer arrives."*

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗺️ **Ward Heat Map** | Color-coded interactive map of ward risk |
| 📊 **Priority Ranking** | Sorted table with color-coded risk & score cells |
| 📈 **Risk Comparison** | Custom per-ward risk bar visualization |
| 📡 **Live Weather Sync** | Real-time temperature via Open-Meteo (free, no API key) |
| 📄 **Decision Briefs** | Auto-generated: risk drivers + interventions + costs |
| 💰 **2026 Cost Engine** | Parameterized municipal price basis (editable in one place) |
| ⬇️ **Exports** | Download briefs (HTML) and priority lists (CSV) |
| 📥 **CSV Upload** | Plug in your own city's ward data instantly |
|  **Theme-Safe UI** | Fully readable in Streamlit light & dark modes |

---

## 🧮 Methodology

Every indicator is min–max normalized to 0–1, then combined with policy-style weights:

```text
HVI Score = Σ (normalized indicator × weight) × 100
```

| Indicator | Weight | Direction |
|---|---:|---|
| Land Surface Temperature | 30% | higher = riskier |
| Built-up Density | 20% | higher = riskier |
| Vulnerable Population (elderly + slum) | 20% | higher = riskier |
| Green Cover | 10% | higher = **safer** (inverted) |
| Distance to Healthcare | 10% | farther = riskier |
| Distance to Water Bodies | 10% | farther = riskier |

**Risk bands:** 🟢 Low < 45 • 🟡 Medium 45–60 • 🟠 High 60–75 • 🔴 Critical > 75

**Live LST estimation (when sync is ON):**

```text
Estimated LST = live air temp + 4 + (built-up% × 0.10) − (green% × 0.08)
```

---

## 💰 Cost Basis (2026 Municipal Rates)

| Intervention | Unit Rate |
|---|---:|
| Cool roof retrofit (lime-based coating) | ₹3,000 / household |
| Street tree (sapling + pit + 3-yr maintenance) | ₹9,000 / tree |
| Shaded hydration / cooling point | ₹25,000 / point |
| Mobile health response unit | ₹2,00,000 / season |
| Temporary water standpost + tanker support | ₹85,000 / point |
| Monitoring & awareness campaign | ₹75,000 / ward |

All rates live in a single `PRICES_2026` dictionary — swap in local Schedule-of-Rates or GeM prices in one line.

---

## 🚀 Quick Start

```bash
git clone https://github.com/Nihar-k-9067-code/heatbrief-india.git
cd heatbrief-india
pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501** 🎉

### Expected CSV format (for your own city)

```csv
ward_id,ward_name,city_name,latitude,longitude,population,elderly_population,slum_population,healthcare_distance_km,water_distance_km,green_cover_pct,built_up_pct,lst_c
W01,Golghar,Gorakhpur,26.7580,83.3720,18200,2300,4100,1.2,0.8,16.5,74.0,44.5
```

---

## 📁 Project Structure

```text
heatbrief-india/
├── app.py            # Entire app: data, HVI engine, brief generator, UI
├── requirements.txt  # streamlit, pandas, requests
└── README.md         # You are here
```

---

## 🏛️ Policy Alignment

Directly operationalizes the **NHRC (2026) recommendation** for ward-level heat vulnerability & resilience mapping using GIS, remote sensing, AI and social vulnerability indicators — and feeds ready-to-approve inputs into municipal **Heat Action Plans**.

## 🗺️ Production Roadmap

- [ ] Real satellite LST via **Google Earth Engine** (Landsat 8/9 thermal bands)
- [ ] Ward boundary polygons from **DataMeet India / OSM**
- [ ] Live vendor pricing via **GeM (Government e-Marketplace) API**
- [ ] LLM-polished brief narratives with rule-engine fallback

## 👤 Author

**Nihar K** — [@Nihar-k-9067-code](https://github.com/Nihar-k-9067-code)

## 📄 License

MIT — free to use for research, governance and hackathon purposes.