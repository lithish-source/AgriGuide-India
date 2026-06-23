# 🌾 AgriGuide India

> **AI-Powered Agricultural Suitability Assessment & Crop Recommendation Portal for India**

A citizen-facing web application that helps Indian farmers and citizens discover the best crops for their district, understand agricultural risks, and get personalized farming advice — powered by 26 years of crop production data, soil nutrient analysis, and water quality monitoring across 740 districts.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![Plotly](https://img.shields.io/badge/Plotly-Interactive-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Sources](#data-sources)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Test Suite](#test-suite)
- [Module Breakdown](#module-breakdown)
- [Visualizations](#visualizations)
- [Screenshots](#screenshots)

---

## 🎯 Overview

AgriGuide India is a **Data Handling & Visualization (DHV)** mini-project that combines three real-world Indian agricultural datasets into a unified decision-support platform. Users can:

- **Search any district** in India (740 districts across 34 states/UTs)
- **View agricultural suitability scores** (0-100) with 7 weighted factors
- **Get crop recommendations** ranked by soil-adjusted suitability
- **See risk factors** — drought, flood, salinity, soil deficiencies, water quality
- **Compare two districts** side-by-side with radar charts
- **Chat with an AI advisor** about crops, irrigation, fertilizer, and risks
- **Download PDF reports** with full district analysis
- **Explore an interactive India map** with color-coded suitability

---

## ✨ Features

### 1. District Agricultural Suitability Assessment
- Weighted suitability score (0-100) using 7 factors: yield, efficiency, scale, soil nutrients, water quality, consistency, diversity
- 4 categories: Poor (0-25), Moderate (26-50), Good (51-75), Excellent (76-100)
- Indicator cards: Rainfall, Soil Quality, Temperature, Irrigation Dependency

### 2. Crop Recommendation Engine
- Top-5 crop recommendations per district with confidence scores
- Soil-adjusted rankings using per-crop nutrient sensitivity profiles
- 24 crops with curated growing advice (irrigation, fertilizer, season, risk)
- Performance ratings: Excellent / Very Good / Good / Moderate / Limited

### 3. Risk Assessment & AI Advisory
- 6 risk categories: Drought, Flood, Soil Deficiency, Temperature, Irrigation, Water Quality
- Specific micronutrient deficiency alerts (Zn, Fe, Cu, Mn, B, S)
- Water quality risks based on FAO irrigation guidelines (EC, SAR, Na, Cl, F, pH)
- AI Farming Advisor with 10 intent categories (hybrid LLM + rule-based)

### 4. Visualization & Comparative Analytics
- Interactive India choropleth map (740 districts, 4 color categories)
- District comparison with radar charts and grouped bar charts
- 10 interactive Plotly visualizations (hover, zoom, responsive)
- Agricultural productivity trend line chart (1997-2023, 26 years)
- PDF report generation with full district analysis

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask 3.x (Python 3.10+) |
| **Data Processing** | Pandas, NumPy |
| **Visualizations** | Plotly.js (interactive, in-browser) |
| **Frontend** | HTML5, CSS3 (custom dark theme), Bootstrap 5, Vanilla JS |
| **PDF Reports** | ReportLab |
| **AI Advisor** | OpenAI-compatible LLM API (optional) + rule-based fallback |
| **Server** | Gunicorn (production) / Flask dev server |

---

## 📁 Project Structure

```
AgriGuideIndia/
├── app.py                          # Flask application + 16 API endpoints
├── .env.example                    # Environment variable template (no real keys)
├── .gitignore
├── run.sh                          # Run script (Mac/Linux)
├── run.bat                         # Run script (Windows)
├── README.md
│
├── data/
│   ├── agriculture datast.csv.zip # 455k rows, 740 districts, 1997-2023 (8.9MB)
│   ├── soil.csv                   # 673 districts, 6 micronutrients (28KB)
│   └── ground_water_quality_dataset.xlsx  # 16,776 samples, 640 districts (1.9MB)
│
├── src/
│   ├── __init__.py
│   ├── data_processor.py           # ETL pipeline: load, clean, score, cache
│   ├── recommendation_engine.py    # Top-N crop ranking + soil adjustment
│   ├── map_engine.py               # Plotly choropleth + scattergeo specs
│   ├── ai_advisor.py               # Hybrid LLM + rule-based advisor
│   └── report_generator.py         # PDF report (ReportLab)
│
├── templates/
│   ├── index.html                  # Home: hero, search, map, profile, charts
│   ├── compare.html                # District A vs District B comparison
│   └── advisor.html                # Full-screen AI advisor
│
├── static/
│   ├── css/
│   │   └── style.css               # Modern dark theme (24KB)
│   ├── js/
│   │   └── app.js                  # Search, profile, charts, advisor (51KB)
│   └── images/
│
├── tests/
│   ├── test_modules.py             # 40 automated test cases (4 modules)
│   └── TEST_DOCUMENTATION.md       # Test case documentation
│
└── cache/                          # Auto-generated on first run (gitignored)
    ├── district_profiles.json      # 740 district profiles
    ├── crop_rankings.json          # Top-10 crops per district
    ├── map_data.json               # Map scatter data
    ├── states.json                 # State → districts index
    ├── crop_yield_stats.json       # National per-crop stats
    └── yearly_trends.json          # 26-year trend per district
```

---

## 📊 Data Sources

### 1. Agriculture Crop Production Data (1997-2023)
- **Source:** Government of India — Directorate of Economics & Statistics
- **Size:** 455,359 records across 740 districts, 34 states, 115 crops
- **Fields:** state, district, crop, year, season, area (ha), production (t), yield (t/ha)
- **Used for:** Suitability scoring, crop recommendations, trend analysis

### 2. Soil Micronutrient Data
- **Size:** 673 districts, 6 micronutrients
- **Fields:** Zn %, Fe %, Cu %, Mn %, B %, S % (sufficiency percentages 0-100)
- **Used for:** Soil quality scoring, crop-specific nutrient adjustment, deficiency risk alerts

### 3. Ground Water Quality Data
- **Source:** Central Ground Water Board (CGWB)
- **Size:** 16,776 location-level samples across 640 districts
- **Fields:** pH, EC (salinity), Na, Cl, F, SO₄, NO₃, hardness, Ca, Mg, K, Fe, As, U
- **Used for:** Irrigation water quality scoring, salinity/sodicity risk detection, SAR computation

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

### Step 1: Clone the Repository
```bash
git clone https://github.com/lithish-source/AgriGuide-India.git
cd AgriGuide-India
```

### Step 2: Install Dependencies
```bash
pip install flask pandas numpy scikit-learn plotly reportlab openpyxl gunicorn requests
```

### Step 3: (Optional) Configure AI Advisor
The app works fully offline with a rule-based advisor. To enable LLM-powered responses:

```bash
cp .env.example .env
# Edit .env and add your API key:
# LLM_API_KEY=your-key-here
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

Supports any OpenAI-compatible API: OpenAI, Groq, OpenRouter, Together, NVIDIA, ZAI, or local Ollama.

### Step 4: Run the Application
```bash
# Mac/Linux
bash run.sh

# Windows
run.bat
```

The script will:
1. Auto-load `.env` if present
2. Install missing dependencies
3. Build the data cache on first run (~30 seconds)
4. Start the Flask server

### Step 5: Open the App
Open your browser to: **http://localhost:5000**

---

## ⚙️ Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | No | — | API key for LLM advisor (omit for offline rule-based mode) |
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | Base URL for OpenAI-compatible API |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name |
| `PORT` | No | `5000` | Server port |
| `FLASK_DEBUG` | No | `0` | Set to `1` for auto-reload during development |

### Supported LLM Providers

| Provider | `LLM_BASE_URL` | Example Model |
|----------|----------------|---------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| NVIDIA | `https://integrate.api.nvidia.com/v1` | `meta/llama-3.3-70b-instruct` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-3.5-sonnet` |
| Together | `https://api.together.xyz/v1` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` |
| ZAI | `https://api.z.ai/api/paas/v4` | `glm-4-flash` |

---

## 📡 API Reference

### Pages
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page (hero, search, map, profile) |
| GET | `/compare` | District comparison page |
| GET | `/advisor` | Full-screen AI advisor |

### Data APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Service health + dataset stats |
| GET | `/api/states` | State → districts index |
| GET | `/api/search?q=` | Fuzzy district search |
| GET | `/api/profile/<state>/<district>` | Full district profile |
| GET | `/api/crops/<state>/<district>?n=5` | Top-N crops with soil adjustment |
| GET | `/api/crops-all/<state>/<district>` | Full crop distribution |
| GET | `/api/trend/<state>/<district>` | 26-year productivity trend |
| GET | `/api/risks/<state>/<district>` | Risk factor list |
| GET | `/api/alternatives/<state>/<district>?n=5` | Nearby better districts |
| GET | `/api/nearest-district?lat=&lon=&n=1` | Nearest district by GPS |

### Map APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/map/state` | State choropleth Plotly spec |
| GET | `/api/map/district` | District scatter Plotly spec |

### Advisor APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/advisor` | AI advisor `{message, state, district}` |
| GET | `/api/advisor/questions` | Suggested questions |
| GET | `/api/advisor/status` | LLM configuration status |

### Compare & Report APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/compare?state_a=&district_a=&state_b=&district_b=` | Two-district comparison |
| GET | `/api/report/<state>/<district>` | Download PDF report |

---

## 🧪 Test Suite

The project includes **40 automated test cases** across 4 DHV modules:

```bash
# Make sure the app is running first
python tests/test_modules.py
```

### Test Results

| Module | Tests | Pass Rate |
|--------|-------|-----------|
| M1: Suitability Assessment | 10 | 100% |
| M2: Crop Recommendation | 10 | 100% |
| M3: Risk Assessment & AI Advisor | 10 | 100% |
| M4: Visualization & Comparative Analytics | 10 | 100% |
| **Total** | **40** | **100%** |

See `tests/TEST_DOCUMENTATION.md` for detailed test case mapping.

---

## 📦 Module Breakdown

### Module 1 — Agricultural Suitability Assessment System (25%)
**Algorithm:** Weighted Suitability Score (7 factors)

| Factor | Weight |
|--------|--------|
| Yield Score | 25% |
| Efficiency Score | 20% |
| Scale Score | 15% |
| Soil Nutrient Score | 13% |
| Water Quality Score | 12% |
| Consistency Score | 10% |
| Diversity Score | 5% |

**Outputs:** Suitability gauge, rainfall/soil/temperature/irrigation indicators, full district profile

### Module 2 — Crop Intelligence & Recommendation Engine (25%)
**Algorithm:** Top-N Crop Ranking with Soil Adjustment

Base score = District yield (35%) + National yield (25%) + Scale (20%) + Consistency (20%)
Soil adjustment = 0.70-1.05 multiplier based on crop-specific nutrient sensitivities

**Outputs:** Top-5 crop recommendations, confidence scores, soil match labels, crop radar/bar/pie charts

### Module 3 — Risk Assessment & AI Advisory System (25%)
**Algorithm:** Rule-Based Risk Detection + Hybrid AI Advisor

6 risk categories: Drought, Flood, Soil Deficiency, Temperature, Irrigation, Water Quality
AI Advisor: 10 intents (crop, irrigation, fertilizer, risks, yield, soil, rainfall, compare, season, general)

**Outputs:** Risk cards with mitigation, alternative districts, AI chatbot (floating + full-page)

### Module 4 — Visualization & Comparative Analytics (25%)
**Algorithms:** Comparative Analytics, Geospatial Mapping, Trend Analysis

**Outputs:** India map, comparison radar/bar charts, scatter plot, trend line chart, PDF reports

---

## 📈 Visualizations

10 interactive Plotly visualizations:

1. **India Agricultural Suitability Map** — 740 districts, 4 color categories
2. **Crop Suitability Bar Chart** — Top-5 crops horizontal bars
3. **Crop Distribution Pie Chart** — Full distribution
4. **Crop Suitability Radar Chart** — Top-5 crops across 4 metrics
5. **Suitability vs Yield Scatter Plot** — Bubble size = cultivation scale
6. **Agricultural Productivity Trend Line Chart** — 26 years, dual y-axis
7. **Soil Micronutrient Radar Chart** — 6 nutrients (Zn, Fe, Cu, Mn, B, S)
8. **Water Quality Radar Chart** — 6 parameters (EC, SAR, Na, Cl, F, pH)
9. **District Comparison Radar Chart** — 2 districts across 7 metrics
10. **Grouped Bar Chart** — Top-8 crops side-by-side comparison

---

## 🖥 Screenshots

The app features a modern dark theme with:
- Gradient hero section with "Detect My Location" and district search
- Color-coded suitability categories (green/yellow/orange/red)
- Interactive map with click-to-load profiles
- Floating AI advisor chatbot on every page
- Responsive design (mobile-friendly)
- Professional animations (fade-in, slide-up, pulse)

---

## 🔒 Security

- **No API keys in the repository** — `.env` is gitignored
- `.env.example` provides the template without real credentials
- All LLM calls are server-side (keys never exposed to the browser)
- No user data collection or tracking

---

## 🤝 Contributing

This is a college mini-project. For questions or suggestions, please open an issue.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👥 Team

| Module | Owner | Contribution |
|--------|-------|-------------|
| Module 1: Suitability Assessment | — | 25% |
| Module 2: Crop Recommendation | — | 25% |
| Module 3: Risk Assessment & AI Advisor | — | 25% |
| Module 4: Visualization & Comparative Analytics | — | 25% |

---

## 🙏 Acknowledgments

- **Directorate of Economics & Statistics, Government of India** — Agriculture crop production data
- **Central Ground Water Board (CGWB)** — Water quality monitoring data
- **Indian Council of Agricultural Research (ICAR)** — Soil nutrient guidelines
- **FAO** — Irrigation water quality standards
# AgriGuide-India
