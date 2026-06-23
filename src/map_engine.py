"""
AgriGuide India — Map Engine
============================
Builds Plotly choropleth specs for the India map (state-level rollup)
and scatter-mapbox overlays (district-level points).
"""

from __future__ import annotations
from typing import Dict, List, Any
from collections import defaultdict
from . import data_processor as dp


CATEGORY_COLORS = {
    "Excellent": "#16a34a",  # green
    "Good":      "#eab308",  # yellow
    "Moderate":  "#f97316",  # orange
    "Poor":      "#dc2626",  # red
}

CATEGORY_ORDER = ["Excellent", "Good", "Moderate", "Poor"]


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, "#9ca3af")


def category_for_score(score: float) -> str:
    if score >= 76:
        return "Excellent"
    if score >= 51:
        return "Good"
    if score >= 26:
        return "Moderate"
    return "Poor"


def state_rollup() -> List[Dict[str, Any]]:
    """Aggregate district-level scores to state level (mean)."""
    by_state = defaultdict(list)
    for d in dp.get_map_data():
        by_state[d["state"]].append(d)
    rows = []
    for state, items in by_state.items():
        scores = [i["suitability_score"] for i in items]
        avg = sum(scores) / len(scores)
        rows.append({
            "state": state,
            "state_code": items[0]["state_code"],
            "avg_score": round(avg, 1),
            "max_score": round(max(scores), 1),
            "min_score": round(min(scores), 1),
            "category": category_for_score(avg),
            "n_districts": len(items),
        })
    return rows


def build_state_choropleth_spec() -> Dict[str, Any]:
    """Plotly spec for state-level choropleth using built-in India GeoJSON."""
    rows = state_rollup()
    return {
        "data": [{
            "type": "choropleth",
            "locationmode": "ISO-3",
            "locations": [r["state_code"] for r in rows],
            "z": [r["avg_score"] for r in rows],
            "text": [f"{r['state']}<br>Avg: {r['avg_score']}<br>Districts: {r['n_districts']}"
                     for r in rows],
            "colorscale": [
                [0.00, "#dc2626"],
                [0.26, "#f97316"],
                [0.51, "#eab308"],
                [0.76, "#16a34a"],
                [1.00, "#15803d"],
            ],
            "zmin": 0,
            "zmax": 100,
            "colorbar": {"title": "Suitability", "thickness": 12, "x": 0.02},
            "marker": {"line": {"color": "#0f172a", "width": 0.5}},
        }],
        "layout": {
            "title": {"text": "Agricultural Suitability — India (State Average)", "font": {"color": "#e2e8f0"}},
            "geo": {
                "scope": "asia",
                "projection": {"type": "conic conformal"},
                "showframe": False,
                "showcoastlines": True,
                "coastlinecolor": "#334155",
                "showland": True,
                "landcolor": "#1e293b",
                "showocean": True,
                "oceancolor": "#0f172a",
                "showcountries": True,
                "countrycolor": "#475569",
                "lataxis": {"range": [6, 38]},
                "lonaxis": {"range": [67, 98]},
                "center": {"lat": 22.5, "lon": 82.5},
            },
            "margin": {"l": 0, "r": 0, "t": 40, "b": 0},
            "paper_bgcolor": "transparent",
            "plot_bgcolor": "transparent",
            "height": 520,
        },
    }


def build_district_scatter_spec() -> Dict[str, Any]:
    """Plotly scatter-mapbox spec showing all districts as colored points."""
    data = dp.get_map_data()
    # Group by category to enable per-color hover styling
    specs_by_cat: Dict[str, Dict] = {}
    for d in data:
        cat = d["category"]
        if cat not in specs_by_cat:
            specs_by_cat[cat] = {
                "type": "scattergeo",
                "mode": "markers",
                "name": cat,
                "lat": [],
                "lon": [],
                "text": [],
                "marker": {"size": 7, "color": category_color(cat),
                           "opacity": 0.75, "line": {"width": 0}},
                "hovertemplate": "<b>%{text}</b><extra></extra>",
            }
        specs_by_cat[cat]["lat"].append(d["lat"])
        specs_by_cat[cat]["lon"].append(d["lon"])
        specs_by_cat[cat]["text"].append(
            f"{d['district']}, {d['state']}<br>Score: {d['suitability_score']}/100 ({d['category']})<br>Top crop: {d['top_crop']}"
        )
    # Ensure consistent category order
    traces = [specs_by_cat[c] for c in CATEGORY_ORDER if c in specs_by_cat]
    return {
        "data": traces,
        "layout": {
            "title": {"text": "District-Level Suitability Map", "font": {"color": "#e2e8f0"}},
            "geo": {
                "scope": "asia",
                "projection": {"type": "mercator"},
                "showframe": False,
                "showcoastlines": True,
                "coastlinecolor": "#334155",
                "showland": True,
                "landcolor": "#1e293b",
                "showocean": True,
                "oceancolor": "#0f172a",
                "showcountries": True,
                "countrycolor": "#475569",
                "lataxis": {"range": [6, 38]},
                "lonaxis": {"range": [67, 98]},
                "center": {"lat": 22.5, "lon": 82.5},
            },
            "margin": {"l": 0, "r": 0, "t": 40, "b": 0},
            "paper_bgcolor": "transparent",
            "plot_bgcolor": "transparent",
            "legend": {"orientation": "h", "y": -0.05, "x": 0.5, "xanchor": "center",
                       "font": {"color": "#cbd5e1"}},
            "height": 520,
        },
    }


def get_state_summary() -> List[Dict[str, Any]]:
    """Return list of state rollup rows for use in JS/UI."""
    return state_rollup()
