"""
AgriGuide India — Flask Application
====================================
Citizen-facing agricultural suitability & crop recommendation portal.

Endpoints
---------
GET   /                          — landing + search + map + profile (SPA-like)
GET   /compare                    — district comparison page
GET   /advisor                    — full-screen AI advisor
GET   /api/states                 — state->districts index
GET   /api/search?q=              — district search
GET   /api/profile/<state>/<district>           — full district profile
GET   /api/crops/<state>/<district>             — top crops for district
GET   /api/risks/<state>/<district>             — risk factors
GET   /api/alternatives/<state>/<district>      — nearby better districts
GET   /api/map/state              — state choropleth spec
GET   /api/map/district           — district scatter spec
POST  /api/advisor                — AI advisor {message, state, district}
GET   /api/report/<state>/<district>             — download PDF report
GET   /api/compare?state_a=..&district_a=..&state_b=..&district_b=..  — comparison data
"""

from __future__ import annotations
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_file, abort, Response

# Make src importable
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src import data_processor as dp
from src import recommendation_engine as rec
from src import map_engine as me
from src import ai_advisor as ai
from src import report_generator as rg

# Ensure cache is built on first run
dp.run_pipeline()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 300


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/compare")
def compare_page():
    return render_template("compare.html")


@app.route("/advisor")
def advisor_page():
    return render_template("advisor.html")


# --------------------------------------------------------------------------- #
# API — data lookups
# --------------------------------------------------------------------------- #
@app.route("/api/states")
def api_states():
    return jsonify(dp.get_states())


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    return jsonify(dp.search_districts(q, limit=15))


@app.route("/api/profile/<state>/<district>")
def api_profile(state, district):
    p = dp.get_district(state, district)
    if not p:
        return jsonify({"error": "District not found"}), 404
    summary = rec.get_summary(state, district)
    return jsonify({**p, "summary": summary})


@app.route("/api/crops/<state>/<district>")
def api_crops(state, district):
    top_n = int(request.args.get("n", 5))
    return jsonify(rec.recommend_top_crops(state, district, top_n=top_n))


@app.route("/api/crops-all/<state>/<district>")
def api_crops_all(state, district):
    return jsonify(rec.get_crop_distribution(state, district))


@app.route("/api/trend/<state>/<district>")
def api_trend(state, district):
    """Yearly productivity trend for the line chart."""
    return jsonify(dp.get_yearly_trend(state, district))


@app.route("/api/risks/<state>/<district>")
def api_risks(state, district):
    p = dp.get_district(state, district)
    if not p:
        return jsonify({"error": "District not found"}), 404
    return jsonify(p["risks"])


@app.route("/api/alternatives/<state>/<district>")
def api_alternatives(state, district):
    limit = int(request.args.get("n", 5))
    return jsonify(rec.suggest_alternatives(state, district, limit=limit))


@app.route("/api/nearest-district")
def api_nearest_district():
    """Find nearest district in our database to a given lat/lon.

    Used by the geolocation feature as a fallback when reverse-geocoding
    returns a town/city name that isn't itself a district.
    """
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lon query params required"}), 400
    limit = int(request.args.get("n", 1))
    return jsonify(dp.find_nearest_district(lat, lon, limit=limit))


# --------------------------------------------------------------------------- #
# API — map specs (Plotly JSON)
# --------------------------------------------------------------------------- #
@app.route("/api/map/state")
def api_map_state():
    return jsonify(me.build_state_choropleth_spec())


@app.route("/api/map/district")
def api_map_district():
    return jsonify(me.build_district_scatter_spec())


# --------------------------------------------------------------------------- #
# API — advisor
# --------------------------------------------------------------------------- #
@app.route("/api/advisor", methods=["POST"])
def api_advisor():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    state = data.get("state")
    district = data.get("district")
    if not message:
        return jsonify({"error": "Message required"}), 400
    result = ai.ask(message, state=state, district=district)
    return jsonify(result)


@app.route("/api/advisor/questions")
def api_advisor_questions():
    return jsonify({"questions": ai.SUGGESTED_QUESTIONS})


@app.route("/api/advisor/status")
def api_advisor_status():
    """Report whether the LLM is configured (so the UI can show a badge)."""
    cfg = ai._llm_config()
    return jsonify({
        "llm_enabled": cfg is not None,
        "model": cfg["model"] if cfg else None,
        "provider": (cfg["base_url"] if cfg else None),
    })


# --------------------------------------------------------------------------- #
# API — compare
# --------------------------------------------------------------------------- #
@app.route("/api/compare")
def api_compare():
    sa = request.args.get("state_a")
    da = request.args.get("district_a")
    sb = request.args.get("state_b")
    db = request.args.get("district_b")
    if not all([sa, da, sb, db]):
        return jsonify({"error": "state_a, district_a, state_b, district_b required"}), 400
    pa = dp.get_district(sa, da)
    pb = dp.get_district(sb, db)
    if not pa:
        return jsonify({"error": f"District {da}, {sa} not found"}), 404
    if not pb:
        return jsonify({"error": f"District {db}, {sb} not found"}), 404
    ca = rec.recommend_top_crops(sa, da, top_n=5)
    cb = rec.recommend_top_crops(sb, db, top_n=5)

    # Unified comparison object for radar + cards
    return jsonify({
        "a": {
            "state": pa["state"], "district": pa["district"],
            "score": pa["suitability_score"], "category": pa["suitability_category"],
            "metrics": pa["metrics"],
            "rainfall_mm": pa["rainfall_mm"],
            "soil_quality": pa["soil_quality"],
            "temperature_c": pa["temperature_c"],
            "irrigation_dependency": pa["irrigation_dependency"],
            "n_crops_grown": pa["n_crops_grown"],
            "top_crops": pa["top_crops"],
            "crops": ca,
            "risks": pa["risks"],
        },
        "b": {
            "state": pb["state"], "district": pb["district"],
            "score": pb["suitability_score"], "category": pb["suitability_category"],
            "metrics": pb["metrics"],
            "rainfall_mm": pb["rainfall_mm"],
            "soil_quality": pb["soil_quality"],
            "temperature_c": pb["temperature_c"],
            "irrigation_dependency": pb["irrigation_dependency"],
            "n_crops_grown": pb["n_crops_grown"],
            "top_crops": pb["top_crops"],
            "crops": cb,
            "risks": pb["risks"],
        },
    })


# --------------------------------------------------------------------------- #
# API — PDF report
# --------------------------------------------------------------------------- #
@app.route("/api/report/<state>/<district>")
def api_report(state, district):
    try:
        cmp_state = request.args.get("cmp_state")
        cmp_district = request.args.get("cmp_district")
        pdf_bytes = rg.generate_report(state, district,
                                       comparison_state=cmp_state,
                                       comparison_district=cmp_district)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    filename = f"AgriGuide_{district}_{state}.pdf".replace(" ", "_")
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "districts": len(dp.get_all_districts()),
        "states": len(dp.get_states()),
    })


# --------------------------------------------------------------------------- #
# File downloads (so users can grab the project ZIP via the public URL)
# --------------------------------------------------------------------------- #
PROJECT_ZIP = Path(__file__).resolve().parent.parent / "download" / "AgriGuideIndia_code.zip"
DATASET_ZIP = Path(__file__).resolve().parent / "data" / "agriculture datast.csv.zip"


@app.route("/download/code")
def download_code():
    """Download the AgriGuide India code ZIP (no dataset, ~60KB)."""
    if not PROJECT_ZIP.exists():
        abort(404, description="Code ZIP not built")
    return send_file(
        str(PROJECT_ZIP),
        as_attachment=True,
        download_name="AgriGuideIndia_code.zip",
        mimetype="application/zip",
    )


@app.route("/download/dataset")
def download_dataset():
    """Download the original agriculture dataset ZIP (~9MB)."""
    if not DATASET_ZIP.exists():
        abort(404, description="Dataset ZIP not found")
    return send_file(
        str(DATASET_ZIP),
        as_attachment=True,
        download_name="agriculture_datast.csv.zip",
        mimetype="application/zip",
    )


@app.route("/downloads")
def downloads_page():
    """Simple HTML page with clickable download links."""
    return """
<!doctype html>
<html><head><title>AgriGuide India — Downloads</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0a0f1c; color: #f8fafc; max-width: 720px; margin: 0 auto; padding: 3rem 1.5rem; }
h1 { color: #4ade80; }
.card { background: #131c33; border: 1px solid #1f2a47; border-radius: 14px;
        padding: 1.5rem; margin: 1.2rem 0; }
.card h2 { margin-top: 0; color: #f8fafc; font-size: 1.2rem; }
.card p { color: #94a3b8; line-height: 1.5; }
.btn { display: inline-block; background: linear-gradient(135deg, #16a34a, #22c55e);
       color: white; padding: 0.75rem 1.5rem; border-radius: 10px; text-decoration: none;
       font-weight: 600; margin-top: 0.5rem; }
.btn:hover { opacity: 0.9; }
code { background: #1a2440; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
</style></head>
<body>
<h1>📦 AgriGuide India — Downloads</h1>

<div class="card">
  <h2>1. Application Code (58 KB)</h2>
  <p>All the Python, HTML, CSS, JS, README, and run scripts. Does NOT include the dataset.</p>
  <a class="btn" href="/download/code">⬇ Download AgriGuideIndia_code.zip</a>
</div>

<div class="card">
  <h2>2. Agriculture Dataset (9 MB)</h2>
  <p>The original <code>agriculture datast.csv.zip</code> you uploaded. Unzip it, rename the CSV
  to <code>agriculture_dataset.csv</code>, and place it inside <code>AgriGuideIndia/data/</code>.</p>
  <a class="btn" href="/download/dataset">⬇ Download agriculture_datast.csv.zip</a>
</div>

<div class="card">
  <h2>Setup instructions</h2>
  <p>1. Download both files above.<br>
  2. Unzip <code>AgriGuideIndia_code.zip</code> anywhere.<br>
  3. Unzip the dataset, rename the CSV to <code>agriculture_dataset.csv</code>,
     put it in <code>AgriGuideIndia/data/</code>.<br>
  4. Copy <code>.env.example</code> to <code>.env</code>, paste your LLM API key.<br>
  5. Run <code>bash run.sh</code> (Mac/Linux) or <code>run.bat</code> (Windows).<br>
  6. Open <code>http://localhost:5000</code>.</p>
</div>

</body></html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Debug mode disabled by default — the auto-reloader was killing the
    # process between requests in some sandbox environments. Enable via
    # FLASK_DEBUG=1 if you need it during local development.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    use_reloader = debug
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=use_reloader)
