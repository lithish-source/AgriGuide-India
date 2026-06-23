"""
AgriGuide India — Recommendation Engine
=======================================
Wraps the precomputed crop rankings into the public API used by the
Flask app: top-5 crops, alternative-district suggestions, summary
insights, and per-crop growing advice.
"""

from __future__ import annotations
from typing import Dict, List
from . import data_processor as dp


# Per-crop growing advice (curated short notes for the citizen UI).
CROP_ADVICE: Dict[str, Dict] = {
    "Rice": {
        "irrigation": "Maintain 2-5 cm standing water during vegetative stage; alternate wetting & drying saves 25% water.",
        "fertilizer": "Basal NPK 80:40:40 kg/ha; split N at tillering and panicle initiation.",
        "season": "Kharif (June-Oct) primary; Rabi (Jan-Apr) in irrigated tracts.",
        "risk": "Blast disease under high humidity; stem borer in tillering.",
    },
    "Wheat": {
        "irrigation": "4-6 irrigations at CRI, tillering, late jointing, flowering, dough stage.",
        "fertilizer": "120:60:40 NPK kg/ha basal + 2 N top-dressings.",
        "season": "Rabi (Nov-Apr).",
        "risk": "Rust diseases; terminal heat stress above 30°C.",
    },
    "Sugarcane": {
        "irrigation": "Drip or furrow irrigation every 10-15 days; critical in tillering & grand growth.",
        "fertilizer": "150:75:60 NPK kg/ha + 10 t/ha FYM.",
        "season": "Annual — planted spring (Feb-Mar) or autumn (Oct-Nov).",
        "risk": "Red rot, woolly aphid, waterlogging in early stage.",
    },
    "Cotton(Lint)": {
        "irrigation": "Bt cotton under drip — 2-4 L/day/plant; avoid waterlogging.",
        "fertilizer": "120:60:60 NPK kg/ha + micronutrients.",
        "season": "Kharif (May-Jul sowing).",
        "risk": "Bollworm, pink bollworm resistance, leaf curl virus.",
    },
    "Maize": {
        "irrigation": "Critical at knee-high, tasseling, silking, and grain-filling.",
        "fertilizer": "120:60:40 NPK kg/ha + 25 kg ZnSO4/ha.",
        "season": "Kharif & Rabi both possible.",
        "risk": "Fall armyworm, stem borer, waterlogging at seedling.",
    },
    "Groundnut": {
        "irrigation": "Light irrigations at pegging & pod development; avoid waterlogging.",
        "fertilizer": "20:40:40 NPK + gypsum 500 kg/ha at pegging.",
        "season": "Kharif (Jun-Sep) & Rabi (Nov-Feb) — Rabi gives higher yield.",
        "risk": "Tikka leaf spot, aflatoxin in late harvest.",
    },
    "Bajra": {
        "irrigation": "Drought-tolerant — 1-2 irrigations at tillering & flowering if needed.",
        "fertilizer": "60:30:30 NPK kg/ha.",
        "season": "Kharif (Jun-Sep).",
        "risk": "Downy mildew, smut.",
    },
    "Jowar": {
        "irrigation": "Rabi jowar — 3-4 irrigations; Kharif jowar mostly rainfed.",
        "fertilizer": "80:40:40 NPK kg/ha.",
        "season": "Kharif & Rabi both.",
        "risk": "Shoot fly, stem borer, grain mould.",
    },
    "Ragi": {
        "irrigation": "Hardy crop; 2 irrigations at flowering if dry.",
        "fertilizer": "50:40:25 NPK + FYM 5 t/ha.",
        "season": "Kharif.",
        "risk": "Blast, neck blast under fog.",
    },
    "Arhar/Tur": {
        "irrigation": "1-2 irrigations at flowering & pod fill; avoid waterlogging.",
        "fertilizer": "25:50:25 NPK + Rhizobium seed treatment.",
        "season": "Kharif (Jun-Jul).",
        "risk": "Pod borer, sterility mosaic.",
    },
    "Soyabean": {
        "irrigation": "Critical at flowering & pod filling — avoid stress.",
        "fertilizer": "20:60:40 NPK + Rhizobium & PSB.",
        "season": "Kharif (Jun-Jul).",
        "risk": "Yellow mosaic virus, stem fly.",
    },
    "Coconut": {
        "irrigation": "Drip 60-100 L/palm/day in summer; basin irrigation weekly.",
        "fertilizer": "500g N + 320g P + 1200g K per palm/year + 25 kg FYM.",
        "season": "Perennial — planting Jun-Jul or Dec-Jan.",
        "risk": "Eriophyid mite, bud rot, ganoderma wilt.",
    },
    "Banana": {
        "irrigation": "Drip 10-20 L/plant/day; high water requirement.",
        "fertilizer": "200:90:300 g NPK per plant per year + 10 kg FYM.",
        "season": "Year-round planting; 12-14 month crop.",
        "risk": "Panama wilt, sigatoka leaf spot, bunchy top.",
    },
    "Sunflower": {
        "irrigation": "Critical at button formation & seed filling.",
        "fertilizer": "60:30:30 NPK kg/ha.",
        "season": "Spring (Jan-Feb) & Kharif.",
        "risk": "Head rot, birds damage, alternating temperatures.",
    },
    "Gram": {
        "irrigation": "Light irrigation at branching & pod filling; mostly rainfed on residual moisture.",
        "fertilizer": "20:40:20 NPK + Rhizobium.",
        "season": "Rabi (Oct-Nov) on residual moisture.",
        "risk": "Wilt, pod borer, Helicoverpa.",
    },
}

DEFAULT_ADVICE = {
    "irrigation": "Use efficient irrigation (drip/sprinkler) and schedule based on soil moisture monitoring.",
    "fertilizer": "Apply balanced NPK based on soil test; supplement with micronutrients (Zn, B, Fe) as needed.",
    "season": "Follow recommended sowing window for your agro-climatic zone.",
    "risk": "Practice integrated pest management; monitor weather advisories regularly.",
}


def get_advice_for_crop(crop: str) -> Dict:
    """Return growing advice for a crop, with fallback to default."""
    return CROP_ADVICE.get(crop, DEFAULT_ADVICE)


def recommend_top_crops(state: str, district: str, top_n: int = 5) -> List[Dict]:
    """Return top-N crops for a district, enriched with advice."""
    crops = dp.get_crop_rankings(state, district, top_n=top_n)
    for c in crops:
        c["advice"] = get_advice_for_crop(c["crop"])
    return crops


def get_crop_distribution(state: str, district: str) -> List[Dict]:
    """Return all ranked crops for a district — used for pie chart."""
    return dp.get_crop_rankings(state, district, top_n=15)


def get_summary(state: str, district: str) -> Dict:
    """Short human-readable summary of the district's agricultural profile."""
    profile = dp.get_district(state, district)
    if not profile:
        return {"headline": "No data available.", "bullets": []}

    score = profile["suitability_score"]
    cat = profile["suitability_category"]
    top = profile["top_crops"][:3]
    bullets = [
        f"Overall suitability: {score}/100 ({cat}).",
        f"Top crops: {', '.join(top) if top else 'insufficient data'}.",
        f"Rainfall: ~{profile['rainfall_mm']} mm/year; Soil quality: {profile['soil_quality']}/100.",
        f"{profile['n_crops_grown']} crops historically cultivated across {profile['n_years_data']} years of data.",
    ]
    if profile["risks"] and profile["risks"][0]["level"] != "Low":
        bullets.append(f"Top risk: {profile['risks'][0]['name']} ({profile['risks'][0]['level']}).")
    return {"headline": f"{district}, {state} — {cat} ({score}/100)", "bullets": bullets}


def suggest_alternatives(state: str, district: str, limit: int = 5) -> List[Dict]:
    """Nearby districts with better suitability."""
    return dp.find_nearby_better(state, district, limit=limit)
