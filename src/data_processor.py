"""
AgriGuide India — Data Processor
================================
Loads, cleans and aggregates the district-level agriculture dataset
into a rich district profile + crop ranking structure used across the app.

Outputs (cached on disk):
  - cache/district_profiles.json   (one entry per district)
  - cache/crop_rankings.json       (top crops per district)
  - cache/map_data.json            (state-level rollup for choropleth)
  - cache/states.json              (state -> [districts] index)
  - cache/crop_yield_stats.json    (per-crop national yield stats)
"""

from __future__ import annotations
import os
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "agriculture_dataset.csv"
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Indian-state ISO-3166-2:IN mapping (for Plotly choropleth locationmode='IND-states')
# We map state_name -> ISO code used by Plotly built-in India state GeoJSON.
STATE_CODE_MAP = {
    "Andhra Pradesh": "IN-AP",
    "Arunachal Pradesh": "IN-AR",
    "Assam": "IN-AS",
    "Bihar": "IN-BR",
    "Chhattisgarh": "IN-CT",
    "Goa": "IN-GA",
    "Gujarat": "IN-GJ",
    "Haryana": "IN-HR",
    "Himachal Pradesh": "IN-HP",
    "Jharkhand": "IN-JH",
    "Karnataka": "IN-KA",
    "Kerala": "IN-KL",
    "Madhya Pradesh": "IN-MP",
    "Maharashtra": "IN-MH",
    "Manipur": "IN-MN",
    "Meghalaya": "IN-ML",
    "Mizoram": "IN-MZ",
    "Nagaland": "IN-NL",
    "Odisha": "IN-OR",
    "Punjab": "IN-PB",
    "Rajasthan": "IN-RJ",
    "Sikkim": "IN-SK",
    "Tamil Nadu": "IN-TN",
    "Telangana": "IN-TG",
    "Tripura": "IN-TR",
    "Uttar Pradesh": "IN-UP",
    "Uttarakhand": "IN-UT",
    "West Bengal": "IN-WB",
    "Andaman And Nicobar Islands": "IN-AN",
    "Chandigarh": "IN-CH",
    "Dadra And Nagar Haveli And Daman And Diu": "IN-DH",
    "The Dadra And Nagar Haveli And Daman And Diu": "IN-DH",
    "Jammu And Kashmir": "IN-JK",
    "Ladakh": "IN-LA",
    "Puducherry": "IN-PY",
}

# Coarse lat/long for states (centroid) — used for distance heuristic only.
STATE_CENTROIDS = {
    "Andhra Pradesh": (15.75, 80.85),
    "Arunachal Pradesh": (27.6, 93.4),
    "Assam": (26.2, 92.9),
    "Bihar": (25.5, 85.3),
    "Chhattisgarh": (21.3, 81.6),
    "Goa": (15.3, 74.1),
    "Gujarat": (22.4, 71.7),
    "Haryana": (29.0, 76.0),
    "Himachal Pradesh": (31.8, 77.3),
    "Jharkhand": (23.6, 85.3),
    "Karnataka": (15.0, 75.5),
    "Kerala": (10.0, 76.3),
    "Madhya Pradesh": (22.5, 78.0),
    "Maharashtra": (19.0, 75.5),
    "Manipur": (24.7, 93.9),
    "Meghalaya": (25.5, 91.4),
    "Mizoram": (23.3, 92.8),
    "Nagaland": (26.0, 94.6),
    "Odisha": (20.5, 84.5),
    "Punjab": (30.7, 76.0),
    "Rajasthan": (27.0, 74.0),
    "Sikkim": (27.5, 88.5),
    "Tamil Nadu": (10.8, 78.4),
    "Telangana": (17.5, 79.0),
    "Tripura": (23.7, 91.8),
    "Uttar Pradesh": (27.0, 80.0),
    "Uttarakhand": (30.0, 79.0),
    "West Bengal": (22.6, 88.3),
    "Andaman And Nicobar Islands": (11.7, 92.6),
    "Chandigarh": (30.7, 76.8),
    "Dadra And Nagar Haveli And Daman And Diu": (20.3, 73.0),
    "The Dadra And Nagar Haveli And Daman And Diu": (20.3, 73.0),
    "Jammu And Kashmir": (33.8, 76.0),
    "Ladakh": (34.2, 77.6),
    "Puducherry": (11.9, 79.8),
}

# District centroid approximation per state (we don't have real district coords).
# Used only for "nearby districts" distance heuristic — not claimed as accurate.
# Will use state centroid + deterministic offset based on district name hash.
def district_centroid(state: str, district: str) -> Tuple[float, float]:
    # Try real GPS coordinates from water quality dataset first
    real = _get_real_centroid(district)
    if real:
        return real
    # Fallback: state centroid + deterministic offset
    base = STATE_CENTROIDS.get(state, (22.0, 79.0))
    h = sum(ord(c) for c in district) % 360
    dlat = (h - 180) / 60.0  # +/-3 deg
    dlon = ((h * 7) % 360 - 180) / 60.0
    return (round(base[0] + dlat, 4), round(base[1] + dlon, 4))


# Real district centroids loaded from water quality dataset GPS coordinates
_REAL_CENTROIDS: Dict[str, Tuple[float, float]] | None = None


def _load_real_centroids() -> Dict[str, Tuple[float, float]]:
    """Load real district centroids from the water quality dataset's GPS coords."""
    global _REAL_CENTROIDS
    if _REAL_CENTROIDS is not None:
        return _REAL_CENTROIDS

    wq_path = BASE_DIR / "data" / "ground_water_quality_dataset.xlsx"
    if not wq_path.exists():
        _REAL_CENTROIDS = {}
        return _REAL_CENTROIDS

    try:
        wq = pd.read_excel(wq_path)
        wq.columns = [c.strip() for c in wq.columns]
        wq["District"] = wq["District"].astype(str).str.strip()
        wq["Latitude"] = pd.to_numeric(wq.get("Latitude"), errors="coerce")
        wq["Longitude"] = pd.to_numeric(wq.get("Longitude"), errors="coerce")
        valid = wq.dropna(subset=["Latitude", "Longitude"])
        if len(valid) == 0:
            _REAL_CENTROIDS = {}
            return _REAL_CENTROIDS
        g = valid.groupby("District").agg({
            "Latitude": "mean",
            "Longitude": "mean",
        }).reset_index()
        _REAL_CENTROIDS = {}
        for _, row in g.iterrows():
            key = _normalize_district_name(row["District"])
            if key:
                _REAL_CENTROIDS[key] = (round(float(row["Latitude"]), 4), round(float(row["Longitude"]), 4))
        print(f"[data_processor] real centroids loaded for {len(_REAL_CENTROIDS)} districts")
    except Exception as e:
        print(f"[data_processor] failed to load real centroids: {e}")
        _REAL_CENTROIDS = {}
    return _REAL_CENTROIDS


def _get_real_centroid(district: str) -> Tuple[float, float] | None:
    """Return real GPS centroid for a district, or None if not available."""
    centroids = _load_real_centroids()
    if not centroids:
        return None
    key = _normalize_district_name(district)
    if key in centroids:
        return centroids[key]
    # Fuzzy match
    import difflib
    matches = difflib.get_close_matches(key, list(centroids.keys()), n=1, cutoff=0.78)
    if matches:
        return centroids[matches[0]]
    return None


# --------------------------------------------------------------------------- #
# Name normalization (for fuzzy district matching across datasets)
# --------------------------------------------------------------------------- #
def _normalize_district_name(s) -> str:
    """Normalise district names: lowercase, strip punctuation/accents, remove spaces."""
    if not isinstance(s, str):
        return ""
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    import re as _re
    s = _re.sub(r"[^a-z0-9]", "", s)
    return s


# --------------------------------------------------------------------------- #
# Soil nutrient data loader (soil.csv)
# --------------------------------------------------------------------------- #
_SOIL_CACHE: Dict[str, Dict] | None = None


def load_soil_data() -> Dict[str, Dict]:
    """Load soil.csv — 6 micronutrient sufficiency % per district."""
    global _SOIL_CACHE
    if _SOIL_CACHE is not None:
        return _SOIL_CACHE
    soil_path = BASE_DIR / "data" / "soil.csv"
    if not soil_path.exists():
        print("[data_processor] soil.csv not found — soil nutrients disabled")
        _SOIL_CACHE = {}
        return _SOIL_CACHE

    print("[data_processor] loading soil nutrient data ...")
    soil = pd.read_csv(soil_path)
    soil.columns = [c.strip() for c in soil.columns]
    soil = soil.rename(columns={"District": "district"})
    for col in ["Zn %", "Zn", "Fe%", "Fe", "Cu %", "Cu", "Mn %", "Mn", "B %", "B", "S %", "S"]:
        pass  # column names vary
    # Find nutrient columns by prefix
    for col in soil.columns:
        cl = col.lower().strip()
        if cl.startswith("zn"): soil["Zn"] = pd.to_numeric(soil[col], errors="coerce")
        elif cl.startswith("fe"): soil["Fe"] = pd.to_numeric(soil[col], errors="coerce")
        elif cl.startswith("cu"): soil["Cu"] = pd.to_numeric(soil[col], errors="coerce")
        elif cl.startswith("mn"): soil["Mn"] = pd.to_numeric(soil[col], errors="coerce")
        elif cl.startswith("b") and cl != "district": soil["B"] = pd.to_numeric(soil[col], errors="coerce")
        elif cl.startswith("s") and cl != "district": soil["S"] = pd.to_numeric(soil[col], errors="coerce")
    for col in ["Zn", "Fe", "Cu", "Mn", "B", "S"]:
        if col not in soil.columns:
            soil[col] = 50.0
        soil[col] = soil[col].fillna(soil[col].median() if not pd.isna(soil[col].median()) else 50.0)
    soil["soil_nutrient_score"] = soil[["Zn", "Fe", "Cu", "Mn", "B", "S"]].mean(axis=1).round(1)

    lookup: Dict[str, Dict] = {}
    for _, row in soil.iterrows():
        district = str(row["district"]).strip()
        key = _normalize_district_name(district)
        if not key:
            continue
        lookup[key] = {
            "district": district,
            "Zn": round(float(row["Zn"]), 1), "Fe": round(float(row["Fe"]), 1),
            "Cu": round(float(row["Cu"]), 1), "Mn": round(float(row["Mn"]), 1),
            "B": round(float(row["B"]), 1), "S": round(float(row["S"]), 1),
            "soil_nutrient_score": round(float(row["soil_nutrient_score"]), 1),
        }
    print(f"[data_processor] soil nutrients loaded for {len(lookup)} districts")
    _SOIL_CACHE = lookup
    return lookup


def get_soil_for_district(district: str) -> Dict | None:
    """Look up soil nutrient data for a district name using fuzzy matching."""
    soil = load_soil_data()
    if not soil:
        return None
    key = _normalize_district_name(district)
    if not key:
        return None
    if key in soil:
        return soil[key]
    import difflib
    matches = difflib.get_close_matches(key, list(soil.keys()), n=1, cutoff=0.78)
    if matches:
        return soil[matches[0]]
    return None


# --------------------------------------------------------------------------- #
# Water quality data loader (ground_water_quality_dataset.xlsx)
# --------------------------------------------------------------------------- #
_WATER_CACHE: Dict[str, Dict] | None = None


def _to_num(s):
    """Convert to float, treating '-', 'BDL', '#REF!' etc. as NaN."""
    if s is None:
        return float("nan")
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s or s in ("-", "BDL", "#REF!", "NR", "NA", "N/A"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def load_water_quality() -> Dict[str, Dict]:
    """Load ground_water_quality_dataset.xlsx → district-level water quality."""
    global _WATER_CACHE
    if _WATER_CACHE is not None:
        return _WATER_CACHE

    wq_path = BASE_DIR / "data" / "ground_water_quality_dataset.xlsx"
    if not wq_path.exists():
        print("[data_processor] water quality xlsx not found — water quality disabled")
        _WATER_CACHE = {}
        return _WATER_CACHE

    print("[data_processor] loading water quality data ...")
    try:
        wq = pd.read_excel(wq_path)
    except Exception as e:
        print(f"[data_processor] failed to read water quality xlsx: {e}")
        _WATER_CACHE = {}
        return _WATER_CACHE

    wq.columns = [c.strip() for c in wq.columns]
    for c in ["State", "District", "Location"]:
        if c in wq.columns:
            wq[c] = wq[c].astype(str).str.strip()

    # Map source columns to clean names
    # Note: multiple source columns may map to the same destination (e.g. EC).
    # We only set NaN if no source column has been found yet.
    col_map = {
        "pH": "pH", "EC (µS/cm at": "EC", "EC (µS/cm at 25°C)": "EC",
        "Cl (mg/L)": "Cl", "F (mg/L)": "F", "SO4": "SO4", "NO3": "NO3",
        "Total Hardness": "hardness", "Ca (mg/L)": "Ca", "Mg (mg/L)": "Mg",
        "Na (mg/L)": "Na", "K (mg/L)": "K", "Fe (ppm)": "Fe_water",
        "As (ppb)": "As", "U (ppb)": "U",
    }
    for src, dst in col_map.items():
        if src in wq.columns:
            wq[dst] = wq[src].apply(_to_num)
        elif dst not in wq.columns:
            # Only set NaN if the destination column doesn't exist yet
            # (prevents overwriting a valid column set by an earlier key)
            wq[dst] = float("nan")

    # Aggregate to district level
    agg_cols = {dst: "mean" for dst in ["pH", "EC", "Cl", "F", "SO4", "NO3",
                "hardness", "Ca", "Mg", "Na", "K", "Fe_water", "As", "U"]}
    district_agg = wq.groupby(["State", "District"]).agg(agg_cols).reset_index()

    lookup: Dict[str, Dict] = {}
    for _, row in district_agg.iterrows():
        district = str(row["District"]).strip()
        key = _normalize_district_name(district)
        if not key:
            continue
        # SAR (Sodium Adsorption Ratio)
        na_meq = row["Na"] / 23.0 if not pd.isna(row["Na"]) else 0
        ca_meq = row["Ca"] / 20.0 if not pd.isna(row["Ca"]) else 0
        mg_meq = row["Mg"] / 12.15 if not pd.isna(row["Mg"]) else 0
        sar = na_meq / (((ca_meq + mg_meq) / 2) ** 0.5) if (ca_meq + mg_meq) > 0 else 0

        # Water quality score (0-100) based on FAO irrigation guidelines
        score = 100
        ec = row["EC"] if not pd.isna(row["EC"]) else 0
        if ec > 3000: score -= 35
        elif ec > 2250: score -= 25
        elif ec > 1500: score -= 15
        elif ec > 750: score -= 5
        if sar > 26: score -= 30
        elif sar > 18: score -= 20
        elif sar > 10: score -= 10
        na = row["Na"] if not pd.isna(row["Na"]) else 0
        if na > 920: score -= 15
        elif na > 460: score -= 8
        cl = row["Cl"] if not pd.isna(row["Cl"]) else 0
        if cl > 355: score -= 15
        elif cl > 142: score -= 8
        f_val = row["F"] if not pd.isna(row["F"]) else 0
        if f_val > 5: score -= 10
        elif f_val > 2: score -= 5
        score = max(0, min(100, score))
        if score >= 80: label = "Excellent"
        elif score >= 60: label = "Good"
        elif score >= 40: label = "Moderate"
        elif score >= 20: label = "Poor"
        else: label = "Unsuitable"

        def _val(v, n=1):
            return round(float(v), n) if not pd.isna(v) else None

        lookup[key] = {
            "district": district,
            "state": str(row["State"]).strip() if "State" in district_agg.columns else "",
            "pH": _val(row["pH"], 2), "EC": _val(row["EC"], 1),
            "Na": _val(row["Na"]), "Cl": _val(row["Cl"]), "F": _val(row["F"], 2),
            "NO3": _val(row["NO3"]), "SO4": _val(row["SO4"]),
            "hardness": _val(row["hardness"]), "Ca": _val(row["Ca"]), "Mg": _val(row["Mg"]),
            "K": _val(row["K"]), "Fe_water": _val(row["Fe_water"], 2),
            "As": _val(row["As"], 2), "U": _val(row["U"], 2),
            "SAR": round(float(sar), 2),
            "water_quality_score": round(float(score), 1),
            "water_quality_label": label,
        }
    print(f"[data_processor] water quality loaded for {len(lookup)} districts")
    _WATER_CACHE = lookup
    return lookup


def get_water_quality_for_district(district: str) -> Dict | None:
    """Look up water quality data for a district name using fuzzy matching."""
    wq = load_water_quality()
    if not wq:
        return None
    key = _normalize_district_name(district)
    if not key:
        return None
    if key in wq:
        return wq[key]
    import difflib
    matches = difflib.get_close_matches(key, list(wq.keys()), n=1, cutoff=0.78)
    if matches:
        return wq[matches[0]]
    return None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _safe_float(v) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------- #
# Suitability model
# --------------------------------------------------------------------------- #
# Synthesise per-district agricultural drivers from crop-production history.
# These features are NOT real climate measurements — we approximate them from
# the productivity statistics available in the dataset so the system works
# end-to-end without external climate APIs. Each metric is normalised across
# all districts so the 0-100 suitability score is comparable nationally.

def _norm(series: pd.Series, invert: bool = False) -> pd.Series:
    """Min-max normalise to 0-1, optionally inverted (higher raw = worse)."""
    s = series.copy()
    q_lo, q_hi = s.quantile(0.02), s.quantile(0.98)
    s = s.clip(q_lo, q_hi)
    rng = (q_hi - q_lo) or 1.0
    n = (s - q_lo) / rng
    return (1 - n) if invert else n


def build_district_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw crop records into one row per district."""
    # Drop rows with no yield/area info — they cannot inform suitability
    work = df[df["area"].fillna(0) > 0].copy()
    work["yield"] = work["yield"].fillna(0)
    work["production"] = work["production"].fillna(0)

    # Use Total season if available else fall back to Whole Year else Kharif+Rabi sum
    # For aggregation simplicity, just take all rows per district/crop.
    g = work.groupby(["state_name", "district_name"])

    feats = g.agg(
        total_area=("area", "sum"),
        total_production=("production", "sum"),
        avg_yield=("yield", "mean"),
        median_yield=("yield", "median"),
        n_crops=("crop_name", "nunique"),
        n_seasons=("season", "nunique"),
        n_years=("year", "nunique"),
        crop_records=("crop_name", "count"),
    ).reset_index()

    # Derived: yield_efficiency = production per unit area (overall)
    feats["yield_efficiency"] = feats["total_production"] / feats["total_area"].clip(lower=1)
    # Diversity — clipped at typical max
    feats["diversity_score"] = feats["n_crops"].clip(upper=80) / 80.0
    # Production scale
    feats["production_scale"] = feats["total_production"].clip(lower=0)

    return feats


def compute_suitability(feats: pd.DataFrame) -> pd.DataFrame:
    """Compute 0-100 suitability score per district using weighted factors.

    The score is calibrated to give a balanced distribution across all four
    categories (Poor/Moderate/Good/Excellent) rather than concentrating at
    the low end. Factors are percentile-ranked rather than min-max normalised
    so outliers don't compress the middle of the range.
    """
    feats = feats.copy()

    # Percentile ranks for crop-production metrics
    feats["p_yield"]       = feats["avg_yield"].rank(pct=True) * 100
    feats["p_efficiency"]  = feats["yield_efficiency"].rank(pct=True) * 100
    feats["p_diversity"]   = feats["n_crops"].rank(pct=True) * 100
    feats["p_scale"]       = feats["total_production"].rank(pct=True) * 100
    feats["p_consistency"] = feats["n_years"].rank(pct=True) * 100

    # ----- Soil nutrients (soil.csv) -----
    soil_data = load_soil_data()
    soil_scores = []
    has_soil_list = []
    for _, r in feats.iterrows():
        soil = get_soil_for_district(r["district_name"])
        if soil:
            soil_scores.append(soil["soil_nutrient_score"])
            has_soil_list.append(True)
        else:
            soil_scores.append(float("nan"))
            has_soil_list.append(False)
    feats["soil_nutrient_score"] = soil_scores
    feats["has_soil_data"] = has_soil_list
    has_soil_mask = feats["has_soil_data"]
    soil_pct = pd.Series(index=feats.index, dtype=float)
    if has_soil_mask.any():
        soil_pct.loc[has_soil_mask] = feats.loc[has_soil_mask, "soil_nutrient_score"].rank(pct=True) * 100
    feats["p_soil"] = soil_pct.fillna(50.0).round(1)

    # ----- Water quality (ground_water_quality_dataset.xlsx) -----
    wq_data = load_water_quality()
    wq_scores = []
    has_wq_list = []
    wq_ec_list = []
    wq_sar_list = []
    wq_na_list = []
    wq_cl_list = []
    wq_f_list = []
    wq_ph_list = []
    for _, r in feats.iterrows():
        wq = get_water_quality_for_district(r["district_name"])
        if wq:
            wq_scores.append(wq["water_quality_score"])
            has_wq_list.append(True)
            wq_ec_list.append(wq.get("EC"))
            wq_sar_list.append(wq.get("SAR"))
            wq_na_list.append(wq.get("Na"))
            wq_cl_list.append(wq.get("Cl"))
            wq_f_list.append(wq.get("F"))
            wq_ph_list.append(wq.get("pH"))
        else:
            wq_scores.append(float("nan"))
            has_wq_list.append(False)
            wq_ec_list.append(float("nan"))
            wq_sar_list.append(float("nan"))
            wq_na_list.append(float("nan"))
            wq_cl_list.append(float("nan"))
            wq_f_list.append(float("nan"))
            wq_ph_list.append(float("nan"))
    feats["wq_score"] = wq_scores
    feats["has_wq_data"] = has_wq_list
    feats["wq_EC"] = wq_ec_list
    feats["wq_SAR"] = wq_sar_list
    feats["wq_Na"] = wq_na_list
    feats["wq_Cl"] = wq_cl_list
    feats["wq_F"] = wq_f_list
    feats["wq_pH"] = wq_ph_list
    has_wq_mask = feats["has_wq_data"]
    wq_pct = pd.Series(index=feats.index, dtype=float)
    if has_wq_mask.any():
        wq_pct.loc[has_wq_mask] = feats.loc[has_wq_mask, "wq_score"].rank(pct=True) * 100
    feats["p_water"] = wq_pct.fillna(50.0).round(1)

    # Suitability = weighted blend including soil + water quality
    weights = {
        "p_yield":       0.25,
        "p_efficiency":  0.20,
        "p_scale":       0.15,
        "p_soil":        0.13,
        "p_water":       0.12,
        "p_consistency": 0.10,
        "p_diversity":   0.05,
    }
    score = sum(feats[k] * w for k, w in weights.items())
    feats["suitability_score"] = score.round(1).clip(0, 100)

    def categorize(s: float) -> str:
        if s >= 76: return "Excellent"
        if s >= 51: return "Good"
        if s >= 26: return "Moderate"
        return "Poor"
    feats["suitability_category"] = feats["suitability_score"].apply(categorize)

    # Sub-metric scores
    feats["score_yield"]       = feats["p_yield"].round(1)
    feats["score_efficiency"]  = feats["p_efficiency"].round(1)
    feats["score_diversity"]   = feats["p_diversity"].round(1)
    feats["score_scale"]       = feats["p_scale"].round(1)
    feats["score_consistency"] = feats["p_consistency"].round(1)
    feats["score_soil"]        = feats["p_soil"].round(1)
    feats["score_water"]       = feats["p_water"].round(1)

    # Rainfall proxy
    rain_pct = (0.5 * feats["p_diversity"]/100 + 0.5 * feats["p_yield"]/100)
    feats["rainfall_mm"] = (400 + rain_pct * 1800).round(0).astype(int)

    # Soil quality (real data when available, proxy otherwise)
    soil_quality = []
    for _, r in feats.iterrows():
        if r["has_soil_data"]:
            soil_quality.append(round(float(r["soil_nutrient_score"]), 1))
        else:
            proxy = (0.6 * r["p_efficiency"]/100 + 0.4 * r["p_consistency"]/100) * 100
            soil_quality.append(round(float(proxy), 1))
    feats["soil_quality"] = soil_quality

    # Temperature proxy
    feats["temperature_c"] = feats["state_name"].map(
        lambda s: 28.0 - (STATE_CENTROIDS.get(s, (22.0, 79.0))[0] - 22.0) * 0.4
    ).round(1)

    # Irrigation dependency proxy
    feats["irrigation_dependency"] = ((1 - rain_pct) * 100).round(1).clip(0, 100)

    return feats


# --------------------------------------------------------------------------- #
# Risk analysis
# --------------------------------------------------------------------------- #
def compute_risk_factors(row: pd.Series) -> List[Dict]:
    """Return list of risk dicts with level + detail."""
    risks = []

    # 1) Drought risk — low rainfall
    rain = row["rainfall_mm"]
    if rain < 700:
        level = "Critical" if rain < 500 else "High"
        risks.append({
            "name": "Low Rainfall / Drought Risk",
            "level": level,
            "score": round(100 - rain / 10, 1),
            "detail": f"Estimated mean rainfall ~{rain} mm/year is below the optimal range for most crops.",
            "mitigation": "Adopt drip irrigation, drought-tolerant varieties (bajra, jowar, millets), rainwater harvesting.",
        })
    elif rain > 1900:
        risks.append({
            "name": "Excess Rainfall / Waterlogging Risk",
            "level": "High",
            "score": round((rain - 1900) / 10, 1),
            "detail": f"Estimated rainfall ~{rain} mm/year may cause waterlogging and crop damage.",
            "mitigation": "Improve drainage, choose water-tolerant varieties like rice, banana, sugarcane.",
        })

    # 2) Soil quality
    if row["soil_quality"] < 40:
        risks.append({
            "name": "Poor Soil Nutrients",
            "level": "High" if row["soil_quality"] < 25 else "Moderate",
            "score": round(100 - row["soil_quality"], 1),
            "detail": f"Low soil quality index ({row['soil_quality']}/100) indicates depleted nutrients or poor texture.",
            "mitigation": "Apply organic manure, balanced NPK fertilisation, crop rotation with legumes.",
        })

    # 3) Temperature stress
    t = row["temperature_c"]
    if t > 33:
        risks.append({
            "name": "High Temperature Stress",
            "level": "High",
            "score": round((t - 33) * 12, 1),
            "detail": f"Mean temperature ~{t}°C may impact heat-sensitive crops.",
            "mitigation": "Use heat-tolerant cultivars, mulching, shade nets for vegetables.",
        })
    elif t < 18:
        risks.append({
            "name": "Low Temperature Risk",
            "level": "Moderate",
            "score": round((18 - t) * 8, 1),
            "detail": f"Mean temperature ~{t}°C may limit warm-season crops.",
            "mitigation": "Use protected cultivation, choose cold-tolerant varieties like wheat, mustard.",
        })

    # 4) Irrigation dependency
    if row["irrigation_dependency"] > 60:
        risks.append({
            "name": "High Irrigation Dependency",
            "level": "Critical" if row["irrigation_dependency"] > 80 else "High",
            "score": round(row["irrigation_dependency"], 1),
            "detail": f"Irrigation dependency index {row['irrigation_dependency']}/100 — heavy reliance on artificial water supply.",
            "mitigation": "Adopt micro-irrigation, mulching, drought-resistant crop selection.",
        })

    # 5) Low diversity
    if row["score_diversity"] < 30:
        risks.append({
            "name": "Low Crop Diversity",
            "level": "Moderate",
            "score": round(100 - row["score_diversity"], 1),
            "detail": "Few crop types cultivated — increases market and pest risk.",
            "mitigation": "Introduce crop rotation, intercropping, and diversify into pulses or oilseeds.",
        })

    # 6) Water quality risks (from ground_water_quality_dataset.xlsx)
    if "has_wq_data" in row and row["has_wq_data"]:
        ec = row.get("wq_EC", 0)
        if pd.isna(ec): ec = 0
        sar = row.get("wq_SAR", 0)
        if pd.isna(sar): sar = 0
        na = row.get("wq_Na", 0)
        if pd.isna(na): na = 0
        cl = row.get("wq_Cl", 0)
        if pd.isna(cl): cl = 0
        f_val = row.get("wq_F", 0)
        if pd.isna(f_val): f_val = 0
        ph = row.get("wq_pH", 7.0)
        if pd.isna(ph): ph = 7.0

        # 6a) High salinity (EC)
        if ec > 3000:
            risks.append({
                "name": "High Salinity Irrigation Water",
                "level": "Critical",
                "score": round(min(100, (ec - 2250) / 30), 1),
                "detail": f"EC {ec:.0f} µS/cm severely restricts crop choice (FAO threshold: 3000).",
                "mitigation": "Avoid salt-sensitive crops (pulses, vegetables); prefer barley, sugar beet, cotton, rice. Use gypsum amendments and leaching.",
            })
        elif ec > 2250:
            risks.append({
                "name": "Moderate Salinity Irrigation Water",
                "level": "High",
                "score": round((ec - 1500) / 10, 1),
                "detail": f"EC {ec:.0f} µS/cm may reduce yields of sensitive crops (FAO threshold: 2250).",
                "mitigation": "Select salt-tolerant varieties; ensure good drainage; monitor soil EC regularly.",
            })
        elif ec > 1500:
            risks.append({
                "name": "Slightly Saline Irrigation Water",
                "level": "Moderate",
                "score": round((ec - 750) / 15, 1),
                "detail": f"EC {ec:.0f} µS/cm — slight yield reduction possible for very sensitive crops.",
                "mitigation": "Prefer moderately tolerant crops (wheat, maize, sorghum); avoid pulses and vegetables.",
            })

        # 6b) High sodicity (SAR)
        if sar > 26:
            risks.append({
                "name": "High Sodicity Risk (SAR)",
                "level": "Critical",
                "score": round(min(100, sar * 2), 1),
                "detail": f"SAR {sar:.1f} — sodium dominates, destroys soil structure (FAO threshold: 26).",
                "mitigation": "Apply gypsum (2-5 t/ha) to displace sodium; grow rice for leaching; avoid dryland crops.",
            })
        elif sar > 18:
            risks.append({
                "name": "Moderate Sodicity Risk (SAR)",
                "level": "High",
                "score": round(sar * 2, 1),
                "detail": f"SAR {sar:.1f} — sodium buildup may degrade soil structure over time.",
                "mitigation": "Apply gypsum 1-2 t/ha; grow rice or barley; improve drainage.",
            })

        # 6c) High sodium
        if na > 920:
            risks.append({
                "name": "Excessive Sodium in Water",
                "level": "High",
                "score": round(min(100, (na - 460) / 10), 1),
                "detail": f"Sodium {na:.0f} mg/L is toxic for many crops (FAO threshold: 920).",
                "mitigation": "Blend with canal/rainwater; grow salt-tolerant varieties; apply gypsum.",
            })

        # 6d) High chloride
        if cl > 355:
            risks.append({
                "name": "High Chloride Irrigation Water",
                "level": "High",
                "score": round(min(100, (cl - 142) / 3), 1),
                "detail": f"Chloride {cl:.0f} mg/L is toxic to many crops (FAO threshold: 355).",
                "mitigation": "Avoid fruit crops and beans; grow barley, cotton, sugar beet, tomato.",
            })

        # 6e) High fluoride
        if f_val > 5:
            risks.append({
                "name": "High Fluoride Irrigation Water",
                "level": "High",
                "score": round(min(100, f_val * 12), 1),
                "detail": f"Fluoride {f_val:.1f} mg/L is toxic (WHO threshold: 1.5, FAO irrigation: 5).",
                "mitigation": "Use defluoridation; blend with rainwater; grow fluorine-tolerant crops (sorghum, cotton).",
            })

        # 6f) Extreme pH
        if ph > 8.5:
            risks.append({
                "name": "Alkaline Irrigation Water (High pH)",
                "level": "Moderate",
                "score": round((ph - 7.5) * 20, 1),
                "detail": f"pH {ph:.2f} — alkaline water reduces micronutrient availability (Fe, Zn, Mn).",
                "mitigation": "Apply elemental sulfur or acid-forming fertilizers (ammonium sulphate).",
            })
        elif ph < 6.0:
            risks.append({
                "name": "Acidic Irrigation Water (Low pH)",
                "level": "Moderate",
                "score": round((6.0 - ph) * 20, 1),
                "detail": f"pH {ph:.2f} — acidic water may mobilize toxic metals (Al, Mn).",
                "mitigation": "Apply lime (1-2 t/ha); avoid acid-tolerant crops like tea.",
            })

    # Fallback — if district is overall strong, no critical risks
    if not risks:
        risks.append({
            "name": "No Major Risks Identified",
            "level": "Low",
            "score": 10.0,
            "detail": "All major indicators are within acceptable ranges.",
            "mitigation": "Continue best practices: soil testing every 2 years, integrated pest management.",
        })

    # Sort by score desc
    risks.sort(key=lambda r: r["score"], reverse=True)
    return risks


# --------------------------------------------------------------------------- #
# Crop rankings per district
# --------------------------------------------------------------------------- #
def build_crop_rankings(df: pd.DataFrame, top_n: int = 10) -> Dict[str, List[Dict]]:
    """For each district, return top crops ranked by a confidence score."""
    work = df[df["area"].fillna(0) > 0].copy()
    work["yield"] = work["yield"].fillna(0)
    work["production"] = work["production"].fillna(0)

    g = work.groupby(["state_name", "district_name", "crop_name"]).agg(
        total_area=("area", "sum"),
        total_production=("production", "sum"),
        avg_yield=("yield", "mean"),
        n_years=("year", "nunique"),
        n_seasons=("season", "nunique"),
    ).reset_index()

    # Crop national stats for confidence baseline
    national = work.groupby("crop_name").agg(
        nat_yield=("yield", "mean"),
        nat_area=("area", "sum"),
    )

    rankings: Dict[str, List[Dict]] = {}
    for (state, district), grp in g.groupby(["state_name", "district_name"]):
        # District yield benchmark
        dist_avg_yield = grp["avg_yield"].mean()
        crops = []
        for _, r in grp.iterrows():
            nat_y = national.loc[r["crop_name"], "nat_yield"] if r["crop_name"] in national.index else r["avg_yield"]
            # Suitability % = blend of district-relative yield + national-relative yield + scale + persistence
            rel_district = min(r["avg_yield"] / max(dist_avg_yield, 0.01), 3.0) / 3.0
            rel_national = min(r["avg_yield"] / max(nat_y, 0.01), 3.0) / 3.0
            scale = min(r["total_area"] / (grp["total_area"].quantile(0.9) or 1), 1.0)
            persistence = r["n_years"] / 26.0  # max years in dataset
            score = (0.35 * rel_district + 0.25 * rel_national + 0.20 * scale + 0.20 * persistence) * 100
            score = max(0, min(100, score))
            # Confidence — based on amount of data (n_years * n_records normalised)
            confidence = min(95, 40 + r["n_years"] * 2 + scale * 30)
            # Performance rating
            if score >= 80:
                rating = "Excellent"
            elif score >= 65:
                rating = "Very Good"
            elif score >= 50:
                rating = "Good"
            elif score >= 35:
                rating = "Moderate"
            else:
                rating = "Limited"
            crops.append({
                "crop": r["crop_name"],
                "type": _crop_type_for(r["crop_name"]),
                "suitability_pct": round(score, 1),
                "confidence": round(confidence, 1),
                "performance_rating": rating,
                "avg_yield": round(r["avg_yield"], 3),
                "total_area": int(r["total_area"]),
                "total_production": int(r["total_production"]),
                "n_years": int(r["n_years"]),
            })
        crops.sort(key=lambda c: c["suitability_pct"], reverse=True)
        rankings[f"{state}__{district}"] = crops[:top_n]
    return rankings


# Crop type lookup (built once from dataset)
_CROP_TYPE_MAP: Dict[str, str] = {}

def _build_crop_type_map(df: pd.DataFrame) -> None:
    global _CROP_TYPE_MAP
    if _CROP_TYPE_MAP:
        return
    sub = df[["crop_name", "crop_type"]].drop_duplicates()
    _CROP_TYPE_MAP = dict(zip(sub["crop_name"], sub["crop_type"]))

def _crop_type_for(crop: str) -> str:
    return _CROP_TYPE_MAP.get(crop, "Other")


# --------------------------------------------------------------------------- #
# Yearly productivity trends (for trend line chart)
# --------------------------------------------------------------------------- #
def build_yearly_trends(df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """For each district, compute per-year production / yield / area.

    Used to plot agricultural productivity trends over time (1997-2023).
    Returns dict keyed by 'state__district' -> list of yearly dicts.
    """
    work = df[df["area"].fillna(0) > 0].copy()
    work["yield"] = work["yield"].fillna(0)
    work["production"] = work["production"].fillna(0)

    g = work.groupby(["state_name", "district_name", "year"]).agg(
        total_area=("area", "sum"),
        total_production=("production", "sum"),
        avg_yield=("yield", "mean"),
        n_crops=("crop_name", "nunique"),
    ).reset_index()

    trends: Dict[str, List[Dict]] = {}
    for (state, district), grp in g.groupby(["state_name", "district_name"]):
        key = f"{state}__{district}"
        # Sort by year (year is string like "1997-1998" — sort lexically works)
        grp = grp.sort_values("year")
        rows = []
        for _, r in grp.iterrows():
            rows.append({
                "year": r["year"],
                "production": int(r["total_production"]),
                "area": int(r["total_area"]),
                "avg_yield": round(float(r["avg_yield"]), 3),
                "n_crops": int(r["n_crops"]),
            })
        trends[key] = rows
    return trends


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def run_pipeline(force: bool = False) -> None:
    """Run full data-processing pipeline. Uses cache if present unless force=True."""
    cache_files = [
        CACHE_DIR / "district_profiles.json",
        CACHE_DIR / "crop_rankings.json",
        CACHE_DIR / "map_data.json",
        CACHE_DIR / "states.json",
        CACHE_DIR / "crop_yield_stats.json",
        CACHE_DIR / "yearly_trends.json",
    ]
    if all(f.exists() for f in cache_files) and not force:
        print("[data_processor] cache hit — skipping rebuild")
        return

    print("[data_processor] loading dataset ...")
    df = pd.read_csv(DATA_PATH)
    # Standardise state/district names
    df["state_name"] = df["state_name"].astype(str).str.strip()
    df["district_name"] = df["district_name"].astype(str).str.strip()
    df["crop_name"] = df["crop_name"].astype(str).str.strip()
    df["season"] = df["season"].astype(str).str.strip()

    # Build crop type lookup
    _build_crop_type_map(df)

    print("[data_processor] building district features ...")
    feats = build_district_features(df)
    print("[data_processor] computing suitability scores ...")
    scores = compute_suitability(feats)

    print("[data_processor] building crop rankings ...")
    rankings = build_crop_rankings(df, top_n=10)

    print("[data_processor] building national crop stats ...")
    crop_stats = df.groupby("crop_name").agg(
        avg_yield=("yield", "mean"),
        total_area=("area", "sum"),
        total_production=("production", "sum"),
        n_districts=("district_name", "nunique"),
    ).round(2).reset_index().to_dict(orient="records")

    print("[data_processor] building yearly productivity trends ...")
    yearly_trends = build_yearly_trends(df)

    # ---------------- Build outputs ----------------
    states_index: Dict[str, List[str]] = {}
    district_profiles: Dict[str, Dict] = {}
    map_data: List[Dict] = []

    for _, row in scores.iterrows():
        state = row["state_name"]
        district = row["district_name"]
        key = f"{state}__{district}"
        crops = rankings.get(key, [])

        risks = compute_risk_factors(row)
        lat, lon = district_centroid(state, district)

        # Top production stats
        top_crops = [c["crop"] for c in crops[:5]]
        # Build soil_nutrients object
        soil = get_soil_for_district(district)
        soil_obj = {
            "has_data": soil is not None,
            "Zn": soil["Zn"] if soil else None,
            "Fe": soil["Fe"] if soil else None,
            "Cu": soil["Cu"] if soil else None,
            "Mn": soil["Mn"] if soil else None,
            "B":  soil["B"]  if soil else None,
            "S":  soil["S"]  if soil else None,
            "composite_score": soil["soil_nutrient_score"] if soil else None,
        }
        # Build water_quality object
        wq = get_water_quality_for_district(district)
        wq_obj = {
            "has_data": wq is not None,
            "pH": wq["pH"] if wq else None,
            "EC": wq["EC"] if wq else None,
            "Na": wq["Na"] if wq else None,
            "Cl": wq["Cl"] if wq else None,
            "F":  wq["F"]  if wq else None,
            "NO3": wq["NO3"] if wq else None,
            "SO4": wq["SO4"] if wq else None,
            "hardness": wq["hardness"] if wq else None,
            "Ca": wq["Ca"] if wq else None,
            "Mg": wq["Mg"] if wq else None,
            "K":  wq["K"]  if wq else None,
            "SAR": wq["SAR"] if wq else None,
            "water_quality_score": wq["water_quality_score"] if wq else None,
            "water_quality_label": wq["water_quality_label"] if wq else "No data",
        }
        profile = {
            "state": state,
            "district": district,
            "state_code": STATE_CODE_MAP.get(state, ""),
            "lat": lat,
            "lon": lon,
            "suitability_score": float(row["suitability_score"]),
            "suitability_category": row["suitability_category"],
            "metrics": {
                "yield_score": float(row["score_yield"]),
                "efficiency_score": float(row["score_efficiency"]),
                "diversity_score": float(row["score_diversity"]),
                "scale_score": float(row["score_scale"]),
                "consistency_score": float(row["score_consistency"]),
                "soil_score": float(row["score_soil"]),
                "water_score": float(row["score_water"]),
            },
            "rainfall_mm": int(row["rainfall_mm"]),
            "soil_quality": float(row["soil_quality"]),
            "temperature_c": float(row["temperature_c"]),
            "irrigation_dependency": float(row["irrigation_dependency"]),
            "soil_nutrients": soil_obj,
            "water_quality": wq_obj,
            "n_crops_grown": int(row["n_crops"]),
            "crop_records": int(row["crop_records"]),
            "n_years_data": int(row["n_years"]),
            "total_area_ha": int(row["total_area"]),
            "total_production_t": int(row["total_production"]),
            "avg_yield": round(float(row["avg_yield"]), 3),
            "top_crops": top_crops,
            "risks": risks,
        }
        district_profiles[key] = profile

        states_index.setdefault(state, []).append(district)

        map_data.append({
            "state": state,
            "district": district,
            "state_code": STATE_CODE_MAP.get(state, ""),
            "suitability_score": float(row["suitability_score"]),
            "category": row["suitability_category"],
            "lat": lat,
            "lon": lon,
            "top_crop": top_crops[0] if top_crops else "N/A",
        })

    states_index = {s: sorted(d) for s, d in sorted(states_index.items())}

    # ---------------- Write cache ----------------
    with open(CACHE_DIR / "district_profiles.json", "w") as f:
        json.dump(district_profiles, f)
    with open(CACHE_DIR / "crop_rankings.json", "w") as f:
        json.dump(rankings, f)
    with open(CACHE_DIR / "map_data.json", "w") as f:
        json.dump(map_data, f)
    with open(CACHE_DIR / "states.json", "w") as f:
        json.dump(states_index, f)
    with open(CACHE_DIR / "crop_yield_stats.json", "w") as f:
        json.dump(crop_stats, f)
    with open(CACHE_DIR / "yearly_trends.json", "w") as f:
        json.dump(yearly_trends, f)

    print(f"[data_processor] done. {len(district_profiles)} districts, "
          f"{len(states_index)} states, {len(crop_stats)} crops, "
          f"{len(yearly_trends)} district-year trend points.")


# --------------------------------------------------------------------------- #
# Accessors (used at runtime)
# --------------------------------------------------------------------------- #
_cache: Dict = {}

def _load(name: str):
    if name not in _cache:
        with open(CACHE_DIR / f"{name}.json") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def get_states() -> Dict[str, List[str]]:
    return _load("states")


def get_all_districts() -> Dict[str, Dict]:
    return _load("district_profiles")


def get_district(state: str, district: str) -> Dict | None:
    return _load("district_profiles").get(f"{state}__{district}")


def get_crop_rankings(state: str, district: str, top_n: int = 5) -> List[Dict]:
    crops = _load("crop_rankings").get(f"{state}__{district}", [])
    return crops[:top_n]


def get_map_data() -> List[Dict]:
    return _load("map_data")


def get_crop_stats() -> List[Dict]:
    return _load("crop_yield_stats")


def get_yearly_trend(state: str, district: str) -> List[Dict]:
    """Return list of yearly productivity records for a district."""
    return _load("yearly_trends").get(f"{state}__{district}", [])


def search_districts(query: str, limit: int = 10) -> List[Dict]:
    """Fuzzy substring search across all districts."""
    q = query.strip().lower()
    if not q:
        return []
    profiles = _load("district_profiles")
    results = []
    for key, p in profiles.items():
        if q in p["district"].lower() or q in p["state"].lower():
            results.append({
                "state": p["state"],
                "district": p["district"],
                "suitability_score": p["suitability_score"],
                "category": p["suitability_category"],
            })
            if len(results) >= limit:
                break
    return results


def find_nearby_better(state: str, district: str, limit: int = 5) -> List[Dict]:
    """Recommend nearby districts with better suitability score."""
    profiles = _load("district_profiles")
    src = profiles.get(f"{state}__{district}")
    if not src:
        return []
    src_score = src["suitability_score"]
    src_coord = (src["lat"], src["lon"])

    candidates = []
    for key, p in profiles.items():
        if p["state"] == state and p["district"] == district:
            continue
        if p["suitability_score"] <= src_score:
            continue
        dist_km = haversine_km(src_coord, (p["lat"], p["lon"]))
        if dist_km > 600:  # only suggest reasonably near districts
            continue
        top_crop = p["top_crops"][0] if p["top_crops"] else "N/A"
        candidates.append({
            "state": p["state"],
            "district": p["district"],
            "distance_km": round(dist_km, 0),
            "suitability_score": p["suitability_score"],
            "category": p["suitability_category"],
            "top_crop": top_crop,
        })
    candidates.sort(key=lambda c: c["distance_km"])
    return candidates[:limit]


def find_nearest_district(lat: float, lon: float, limit: int = 1) -> List[Dict]:
    """Find the closest district(s) in our database to a given lat/lon.

    Used as a fallback when reverse-geocoding returns a town/city name that
    isn't itself a district (e.g. user is in Ponneri town → returns
    Thiruvallur district). Computes haversine distance to every district
    centroid and returns the nearest one(s).
    """
    profiles = _load("district_profiles")
    src_coord = (lat, lon)
    candidates = []
    for key, p in profiles.items():
        dist_km = haversine_km(src_coord, (p["lat"], p["lon"]))
        top_crop = p["top_crops"][0] if p["top_crops"] else "N/A"
        candidates.append({
            "state": p["state"],
            "district": p["district"],
            "distance_km": round(dist_km, 1),
            "suitability_score": p["suitability_score"],
            "category": p["suitability_category"],
            "top_crop": top_crop,
            "lat": p["lat"],
            "lon": p["lon"],
        })
    candidates.sort(key=lambda c: c["distance_km"])
    return candidates[:limit]


if __name__ == "__main__":
    run_pipeline(force="--force" in os.sys.argv)
