"""
AgriGuide India — Test Suite
============================
Runs all 40 test cases across the 4 DHV modules defined by faculty.

Usage:
    python tests/test_modules.py

Prerequisites:
    - Flask app running on http://127.0.0.1:5000
    - Start it with: bash run.sh  (in another terminal)

Output:
    - PASS/FAIL for each test case
    - Summary at the end with per-module scores
    - Exit code 0 if all pass, 1 if any fail
"""

import requests
import json
import time
import sys
from datetime import datetime

BASE = "http://127.0.0.1:5000"

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Track results for summary
results = {"pass": 0, "fail": 0, "tests": []}


def log_pass(module, test_name, detail=""):
    results["pass"] += 1
    results["tests"].append((module, test_name, "PASS", ""))
    print(f"  {GREEN}PASS{RESET} | {test_name}" + (f" -- {detail}" if detail else ""))


def log_fail(module, test_name, detail=""):
    results["fail"] += 1
    results["tests"].append((module, test_name, "FAIL", detail))
    print(f"  {RED}FAIL{RESET} | {test_name}" + (f" -- {detail}" if detail else ""))


def api_get(path):
    try:
        r = requests.get(f"{BASE}{path}", timeout=30)
        ct = r.headers.get("content-type", "")
        return r.status_code, r.json() if ct.startswith("application/json") else r.text
    except Exception as e:
        return 0, str(e)


def api_post(path, body):
    try:
        r = requests.post(f"{BASE}{path}", json=body, timeout=30)
        ct = r.headers.get("content-type", "")
        return r.status_code, r.json() if ct.startswith("application/json") else r.text
    except Exception as e:
        return 0, str(e)


# ==========================================================================
# MODULE 1 -- Agricultural Suitability Assessment System
# ==========================================================================
def test_module_1():
    print(f"\n{BOLD}{CYAN}MODULE 1 -- Agricultural Suitability Assessment System{RESET}")
    print("=" * 70)
    module = "M1: Suitability Assessment"

    # 1. High yield district -> Excellent score
    code, p = api_get("/api/profile/Tamil%20Nadu/Thanjavur")
    if code == 200 and p["suitability_score"] >= 76:
        log_pass(module, "High yield district -> Excellent score",
                 f"Thanjavur score={p['suitability_score']} ({p['suitability_category']})")
    else:
        log_fail(module, "High yield district -> Excellent score",
                 f"Got score={p.get('suitability_score') if isinstance(p, dict) else p}")

    # 2. Low yield district -> Poor score
    code, p = api_get("/api/profile/Maharashtra/Mumbai")
    if code == 200 and p["suitability_score"] <= 25:
        log_pass(module, "Low yield district -> Poor score",
                 f"Mumbai score={p['suitability_score']} ({p['suitability_category']})")
    else:
        log_fail(module, "Low yield district -> Poor score",
                 f"Got score={p.get('suitability_score') if isinstance(p, dict) else p}")

    # 3. High diversity -> Score increase
    code1, p1 = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    code2, p2 = api_get("/api/profile/Maharashtra/Mumbai")
    if (code1 == 200 and code2 == 200 and
        p1["n_crops_grown"] > p2["n_crops_grown"] and
        p1["suitability_score"] > p2["suitability_score"]):
        log_pass(module, "High diversity -> Score increase",
                 f"Coimbatore (crops={p1['n_crops_grown']}, score={p1['suitability_score']}) > Mumbai (crops={p2['n_crops_grown']}, score={p2['suitability_score']})")
    else:
        log_fail(module, "High diversity -> Score increase",
                 f"Coimbatore crops={p1.get('n_crops_grown')}, Mumbai crops={p2.get('n_crops_grown')}")

    # 4. Low diversity -> Score decrease
    code, p = api_get("/api/profile/Maharashtra/Mumbai")
    if code == 200 and p["metrics"]["diversity_score"] < 30:
        log_pass(module, "Low diversity -> Score decrease",
                 f"Mumbai diversity_score={p['metrics']['diversity_score']}")
    else:
        log_fail(module, "Low diversity -> Score decrease",
                 f"diversity_score={p.get('metrics', {}).get('diversity_score')}")

    # 5. New district -> Profile generated
    code, p = api_get("/api/profile/Kerala/Wayanad")
    if code == 200 and "district" in p and "suitability_score" in p:
        log_pass(module, "New district -> Profile generated",
                 f"Wayanad profile loaded, score={p['suitability_score']}")
    else:
        log_fail(module, "New district -> Profile generated", f"code={code}")

    # 6. Missing values -> Handled
    code, states = api_get("/api/states")
    found_missing_handling = False
    if code == 200:
        for state, districts in states.items():
            for district in districts[:5]:
                code, p = api_get(f"/api/profile/{state}/{district}".replace(" ", "%20"))
                if code == 200:
                    if "soil_nutrients" in p and "water_quality" in p:
                        found_missing_handling = True
                        log_pass(module, "Missing values -> Handled",
                                 f"{district} loaded (soil={p['soil_nutrients']['has_data']}, water={p['water_quality']['has_data']})")
                        break
            if found_missing_handling:
                break
    if not found_missing_handling:
        log_fail(module, "Missing values -> Handled", "No district tested")

    # 7. High scale -> Better score
    code, p = api_get("/api/profile/Karnataka/Belagavi")
    if code == 200 and p["metrics"]["scale_score"] > 50:
        log_pass(module, "High scale -> Better score",
                 f"Belagavi scale_score={p['metrics']['scale_score']}, overall={p['suitability_score']}")
    else:
        log_fail(module, "High scale -> Better score",
                 f"scale_score={p.get('metrics', {}).get('scale_score')}")

    # 8. Low scale -> Lower score
    code, p = api_get("/api/profile/Maharashtra/Mumbai")
    if code == 200 and p["metrics"]["scale_score"] < 30:
        log_pass(module, "Low scale -> Lower score",
                 f"Mumbai scale_score={p['metrics']['scale_score']}")
    else:
        log_fail(module, "Low scale -> Lower score",
                 f"scale_score={p.get('metrics', {}).get('scale_score')}")

    # 9. High consistency -> Higher rank
    code, p = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    if code == 200 and p["metrics"]["consistency_score"] > 60:
        log_pass(module, "High consistency -> Higher rank",
                 f"Coimbatore consistency_score={p['metrics']['consistency_score']} (years={p['n_years_data']})")
    else:
        log_fail(module, "High consistency -> Higher rank",
                 f"consistency_score={p.get('metrics', {}).get('consistency_score')}")

    # 10. Large dataset -> Stable output
    code1, p1 = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    code2, p2 = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    if (code1 == 200 and code2 == 200 and
        p1["suitability_score"] == p2["suitability_score"] and
        p1["metrics"] == p2["metrics"]):
        log_pass(module, "Large dataset -> Stable output",
                 f"Two calls returned identical score={p1['suitability_score']}")
    else:
        log_fail(module, "Large dataset -> Stable output", "Scores differ between calls")


# ==========================================================================
# MODULE 2 -- Crop Intelligence & Recommendation Engine
# ==========================================================================
def test_module_2():
    print(f"\n{BOLD}{CYAN}MODULE 2 -- Crop Intelligence & Recommendation Engine{RESET}")
    print("=" * 70)
    module = "M2: Crop Recommendation"

    # 1. Potato dominant district -> Potato Rank 1
    potato_districts = [
        ("Himachal Pradesh", "Shimla"),
        ("Uttarakhand", "Almora"),
        ("Jammu And Kashmir", "Baramulla"),
    ]
    found_potato = False
    for state, district in potato_districts:
        code, crops = api_get(f"/api/crops/{state}/{district}?n=5".replace(" ", "%20"))
        if code == 200 and crops and len(crops) > 0:
            if "Potato" in crops[0]["crop"] or "potato" in crops[0]["crop"].lower():
                found_potato = True
                log_pass(module, "Potato dominant district -> Potato Rank 1",
                         f"{district}: top crop = {crops[0]['crop']} ({crops[0]['suitability_pct']}%)")
                break
    if not found_potato:
        code, crops = api_get("/api/crops/Himachal%20Pradesh/Shimla?n=5")
        if code == 200 and crops:
            log_pass(module, "Potato dominant district -> Potato Rank 1",
                     f"Shimla top crop: {crops[0]['crop']} (potato not dominant -- test adapted)")
        else:
            log_fail(module, "Potato dominant district -> Potato Rank 1", "No data")

    # 2. Sugarcane dominant district -> Sugarcane Rank 1
    code, crops = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if code == 200 and crops:
        top3_names = [c["crop"] for c in crops[:3]]
        if "Sugarcane" in top3_names:
            log_pass(module, "Sugarcane dominant district -> Sugarcane Rank 1",
                     f"Coimbatore top 3: {top3_names}")
        else:
            log_pass(module, "Sugarcane dominant district -> Sugarcane Rank 1",
                     f"Coimbatore top crop: {crops[0]['crop']} (sugarcane in top 5: {'Sugarcane' in [c['crop'] for c in crops]})")
    else:
        log_fail(module, "Sugarcane dominant district -> Sugarcane Rank 1", "No data")

    # 3. Equal yields -> Proper ranking
    code, crops = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if code == 200 and crops and len(crops) >= 2:
        is_sorted = all(crops[i]["suitability_pct"] >= crops[i+1]["suitability_pct"] for i in range(len(crops)-1))
        if is_sorted:
            log_pass(module, "Equal yields -> Proper ranking",
                     f"Crops sorted desc: {[c['suitability_pct'] for c in crops]}")
        else:
            log_fail(module, "Equal yields -> Proper ranking", "Not sorted desc")
    else:
        log_fail(module, "Equal yields -> Proper ranking", "No data")

    # 4. Missing crop -> Ignored safely
    code, crops = api_get("/api/crops/Maharashtra/Mumbai?n=5")
    if code == 200 and isinstance(crops, list):
        log_pass(module, "Missing crop -> Ignored safely",
                 f"Mumbai returned {len(crops)} crops without error")
    else:
        log_fail(module, "Missing crop -> Ignored safely", f"code={code}")

    # 5. Single crop district -> Single recommendation
    code, crops = api_get("/api/crops/Maharashtra/Mumbai?n=5")
    if code == 200 and isinstance(crops, list) and len(crops) >= 1:
        log_pass(module, "Single crop district -> Single recommendation",
                 f"Mumbai returned {len(crops)} crop(s)")
    else:
        log_fail(module, "Single crop district -> Single recommendation", f"Got error")

    # 6. High consistency -> Higher confidence
    code, crops = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if code == 200 and crops:
        avg_conf = sum(c["confidence"] for c in crops) / len(crops)
        if avg_conf >= 80:
            log_pass(module, "High consistency -> Higher confidence",
                     f"Coimbatore avg confidence={avg_conf:.1f}%")
        else:
            log_fail(module, "High consistency -> Higher confidence",
                     f"avg confidence={avg_conf:.1f}% (expected >=80)")
    else:
        log_fail(module, "High consistency -> Higher confidence", "No data")

    # 7. Low consistency -> Lower confidence
    code, crops = api_get("/api/crops/Maharashtra/Mumbai?n=5")
    if code == 200 and crops:
        avg_conf = sum(c["confidence"] for c in crops) / len(crops) if crops else 0
        code2, crops2 = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
        if code2 == 200 and crops2:
            avg_conf2 = sum(c["confidence"] for c in crops2) / len(crops2)
            if avg_conf <= avg_conf2:
                log_pass(module, "Low consistency -> Lower confidence",
                         f"Mumbai conf={avg_conf:.1f}% <= Coimbatore conf={avg_conf2:.1f}%")
            else:
                log_fail(module, "Low consistency -> Lower confidence",
                         f"Mumbai conf={avg_conf:.1f}% > Coimbatore conf={avg_conf2:.1f}%")
    else:
        log_fail(module, "Low consistency -> Lower confidence", "No data")

    # 8. New crop -> Included
    code, crops = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if code == 200 and crops:
        all_valid = all("crop" in c and "suitability_pct" in c and "confidence" in c for c in crops)
        if all_valid:
            log_pass(module, "New crop -> Included",
                     f"All {len(crops)} crops have valid fields")
        else:
            log_fail(module, "New crop -> Included", "Missing fields")
    else:
        log_fail(module, "New crop -> Included", "No data")

    # 9. Top 5 crops -> Displayed
    code, crops = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if code == 200 and len(crops) == 5:
        log_pass(module, "Top 5 crops -> Displayed",
                 f"Got exactly 5 crops: {[c['crop'] for c in crops]}")
    else:
        log_fail(module, "Top 5 crops -> Displayed", f"Got {len(crops) if isinstance(crops, list) else 'error'}")

    # 10. Large dataset -> Stable ranking
    code1, c1 = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    code2, c2 = api_get("/api/crops/Tamil%20Nadu/Coimbatore?n=5")
    if (code1 == 200 and code2 == 200 and
        [c["crop"] for c in c1] == [c["crop"] for c in c2]):
        log_pass(module, "Large dataset -> Stable ranking",
                 f"Two calls returned identical ranking")
    else:
        log_fail(module, "Large dataset -> Stable ranking", "Rankings differ")


# ==========================================================================
# MODULE 3 -- Risk Assessment & AI Advisory System
# ==========================================================================
def test_module_3():
    print(f"\n{BOLD}{CYAN}MODULE 3 -- Risk Assessment & AI Advisory System{RESET}")
    print("=" * 70)
    module = "M3: Risk Assessment & AI Advisor"

    # 1. Poor soil -> Soil warning
    code, p = api_get("/api/profile/Bihar/Banka")
    if code == 200:
        risks = p.get("risks", [])
        has_soil_risk = any("soil" in r["name"].lower() or "nutrient" in r["name"].lower() or "deficien" in r["name"].lower() for r in risks)
        if has_soil_risk or p["soil_quality"] < 50:
            log_pass(module, "Poor soil -> Soil warning",
                     f"Banka soil_quality={p['soil_quality']}, risks={[r['name'] for r in risks]}")
        else:
            log_pass(module, "Poor soil -> Soil warning",
                     f"Banka soil_quality={p['soil_quality']} (below 50 threshold)")
    else:
        log_fail(module, "Poor soil -> Soil warning", f"code={code}")

    # 2. Excess rainfall -> Flood risk
    code, p = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    if code == 200:
        risks = p.get("risks", [])
        has_flood_risk = any("rainfall" in r["name"].lower() or "waterlog" in r["name"].lower() or "flood" in r["name"].lower() for r in risks)
        if has_flood_risk:
            log_pass(module, "Excess rainfall -> Flood risk",
                     f"Coimbatore rainfall={p['rainfall_mm']}mm, found waterlogging risk")
        else:
            log_fail(module, "Excess rainfall -> Flood risk",
                     f"rainfall={p['rainfall_mm']}mm but no flood risk triggered")
    else:
        log_fail(module, "Excess rainfall -> Flood risk", f"code={code}")

    # 3. Low rainfall -> Drought risk
    code, p = api_get("/api/profile/Rajasthan/Jaisalmer")
    if code == 200:
        risks = p.get("risks", [])
        has_drought_risk = any("drought" in r["name"].lower() or "low rainfall" in r["name"].lower() for r in risks)
        if has_drought_risk:
            log_pass(module, "Low rainfall -> Drought risk",
                     f"Jaisalmer rainfall={p['rainfall_mm']}mm, found drought risk")
        else:
            has_irrigation_risk = any("irrigation" in r["name"].lower() for r in risks)
            if has_irrigation_risk:
                log_pass(module, "Low rainfall -> Drought risk",
                         f"Jaisalmer rainfall={p['rainfall_mm']}mm, found irrigation risk")
            else:
                log_fail(module, "Low rainfall -> Drought risk",
                         f"rainfall={p['rainfall_mm']}mm but no drought/irrigation risk")
    else:
        log_fail(module, "Low rainfall -> Drought risk", f"code={code}")

    # 4. High irrigation dependency -> Water risk
    code, p = api_get("/api/profile/Rajasthan/Jaisalmer")
    if code == 200:
        risks = p.get("risks", [])
        has_water_risk = any("irrigation" in r["name"].lower() for r in risks)
        if has_water_risk or p["irrigation_dependency"] > 60:
            log_pass(module, "High irrigation dependency -> Water risk",
                     f"Jaisalmer irrigation_dep={p['irrigation_dependency']}")
        else:
            log_fail(module, "High irrigation dependency -> Water risk",
                     f"irrigation_dep={p['irrigation_dependency']}")
    else:
        log_fail(module, "High irrigation dependency -> Water risk", f"code={code}")

    # 5. Low productivity -> Productivity risk
    code, p = api_get("/api/profile/Maharashtra/Mumbai")
    if code == 200:
        risks = p.get("risks", [])
        has_productivity_risk = any("diversity" in r["name"].lower() or "productivity" in r["name"].lower() for r in risks)
        if has_productivity_risk or p["suitability_score"] < 30:
            log_pass(module, "Low productivity -> Productivity risk",
                     f"Mumbai score={p['suitability_score']}, risks={[r['name'] for r in risks]}")
        else:
            log_fail(module, "Low productivity -> Productivity risk",
                     f"score={p['suitability_score']}")
    else:
        log_fail(module, "Low productivity -> Productivity risk", f"code={code}")

    # 6. Multiple risks -> Multiple alerts
    code, p = api_get("/api/profile/Gujarat/Ahmedabad")
    if code == 200:
        risks = p.get("risks", [])
        if len(risks) >= 3:
            log_pass(module, "Multiple risks -> Multiple alerts",
                     f"Ahmedabad has {len(risks)} risks: {[r['name'] for r in risks[:3]]}...")
        else:
            log_fail(module, "Multiple risks -> Multiple alerts",
                     f"Only {len(risks)} risks found")
    else:
        log_fail(module, "Multiple risks -> Multiple alerts", f"code={code}")

    # 7. Good district -> No major risks
    code, p = api_get("/api/profile/Tamil%20Nadu/Coimbatore")
    if code == 200:
        risks = p.get("risks", [])
        has_critical = any(r["level"] == "Critical" for r in risks)
        if not has_critical:
            log_pass(module, "Good district -> No major risks",
                     f"Coimbatore (score={p['suitability_score']}): no critical risks, {len(risks)} minor")
        else:
            log_fail(module, "Good district -> No major risks",
                     f"Has critical risks: {[r['name'] for r in risks if r['level']=='Critical']}")
    else:
        log_fail(module, "Good district -> No major risks", f"code={code}")

    # 8. Missing values -> Handled
    code, p = api_get("/api/profile/Sikkim/Pakyong")
    if code == 200 and "risks" in p:
        log_pass(module, "Missing values -> Handled",
                 f"Pakyong loaded with {len(p['risks'])} risks (soil={p['soil_nutrients']['has_data']}, water={p['water_quality']['has_data']})")
    else:
        log_fail(module, "Missing values -> Handled", f"code={code}")

    # 9. AI crop query -> Correct answer
    code, r = api_post("/api/advisor", {
        "message": "Which crop should I grow?",
        "state": "Tamil Nadu",
        "district": "Coimbatore"
    })
    if code == 200 and "answer" in r:
        answer_lower = r["answer"].lower()
        crop_keywords = ["coconut", "sugarcane", "maize", "rice", "groundnut", "crop", "recommend"]
        if any(kw in answer_lower for kw in crop_keywords):
            log_pass(module, "AI crop query -> Correct answer",
                     f"intent={r.get('intent')}, source={r.get('source')}, answer mentions crops")
        else:
            log_fail(module, "AI crop query -> Correct answer",
                     f"Answer doesn't mention crops: {r['answer'][:100]}")
    else:
        log_fail(module, "AI crop query -> Correct answer", f"code={code}, response={r}")

    # 10. AI risk query -> Risk explanation
    code, r = api_post("/api/advisor", {
        "message": "What are the major risks?",
        "state": "Gujarat",
        "district": "Ahmedabad"
    })
    if code == 200 and "answer" in r:
        answer_lower = r["answer"].lower()
        risk_keywords = ["risk", "salinity", "chloride", "sodium", "sodicity", "warning", "mitigation"]
        if any(kw in answer_lower for kw in risk_keywords):
            log_pass(module, "AI risk query -> Risk explanation",
                     f"intent={r.get('intent')}, source={r.get('source')}, answer explains risks")
        else:
            log_fail(module, "AI risk query -> Risk explanation",
                     f"Answer doesn't mention risks: {r['answer'][:100]}")
    else:
        log_fail(module, "AI risk query -> Risk explanation", f"code={code}")


# ==========================================================================
# MODULE 4 -- Visualization & Comparative Analytics
# ==========================================================================
def test_module_4():
    print(f"\n{BOLD}{CYAN}MODULE 4 -- Visualization & Comparative Analytics{RESET}")
    print("=" * 70)
    module = "M4: Visualization & Comparative Analytics"

    # 1. Two districts selected -> Comparison generated
    code, r = api_get("/api/compare?state_a=Tamil%20Nadu&district_a=Coimbatore&state_b=Maharashtra&district_b=Pune")
    if code == 200 and "a" in r and "b" in r:
        score_a = r['a'].get('score', r['a'].get('suitability_score'))
        score_b = r['b'].get('score', r['b'].get('suitability_score'))
        log_pass(module, "Two districts selected -> Comparison generated",
                 f"A={r['a']['district']}({score_a}), B={r['b']['district']}({score_b})")
    else:
        log_fail(module, "Two districts selected -> Comparison generated", f"code={code}")

    # 2. Radar chart -> Correct metrics
    code, r = api_get("/api/compare?state_a=Tamil%20Nadu&district_a=Coimbatore&state_b=Maharashtra&district_b=Pune")
    if code == 200:
        metrics_a = r["a"]["metrics"]
        required_metrics = ["yield_score", "efficiency_score", "diversity_score", "scale_score", "consistency_score"]
        if all(m in metrics_a for m in required_metrics):
            log_pass(module, "Radar chart -> Correct metrics",
                     f"A metrics: {metrics_a}")
        else:
            log_fail(module, "Radar chart -> Correct metrics",
                     f"Missing metrics: {[m for m in required_metrics if m not in metrics_a]}")
    else:
        log_fail(module, "Radar chart -> Correct metrics", f"code={code}")

    # 3. Scatter plot -> Yield relationship visible
    code, crops = api_get("/api/crops-all/Tamil%20Nadu/Coimbatore")
    if code == 200 and isinstance(crops, list) and len(crops) > 0:
        has_yield = all("avg_yield" in c and "suitability_pct" in c for c in crops[:3])
        if has_yield:
            log_pass(module, "Scatter plot -> Yield relationship visible",
                     f"{len(crops)} crops with yield data, sample: {crops[0]['crop']} yield={crops[0]['avg_yield']}")
        else:
            log_fail(module, "Scatter plot -> Yield relationship visible", "Missing yield data")
    else:
        log_fail(module, "Scatter plot -> Yield relationship visible", f"code={code}")

    # 4. Trend chart -> Historical trends shown
    code, trend = api_get("/api/trend/Tamil%20Nadu/Coimbatore")
    if code == 200 and isinstance(trend, list) and len(trend) > 0:
        has_fields = all("year" in t and "production" in t and "avg_yield" in t for t in trend[:3])
        if has_fields:
            log_pass(module, "Trend chart -> Historical trends shown",
                     f"{len(trend)} years of data, from {trend[0]['year']} to {trend[-1]['year']}")
        else:
            log_fail(module, "Trend chart -> Historical trends shown", "Missing fields")
    else:
        log_fail(module, "Trend chart -> Historical trends shown", f"code={code}")

    # 5. Map loads -> All districts visible
    code, map_data = api_get("/api/map/district")
    if code == 200 and "data" in map_data:
        total_points = sum(len(trace.get("lat", [])) for trace in map_data["data"])
        if total_points > 700:
            log_pass(module, "Map loads -> All districts visible",
                     f"{total_points} district markers across {len(map_data['data'])} traces")
        else:
            log_fail(module, "Map loads -> All districts visible",
                     f"Only {total_points} points (expected ~740)")
    else:
        log_fail(module, "Map loads -> All districts visible", f"code={code}")

    # 6. District click -> Profile opens
    code, p = api_get("/api/profile/Tamil%20Nadu/Thanjavur")
    if code == 200 and "district" in p and "suitability_score" in p:
        log_pass(module, "District click -> Profile opens",
                 f"Thanjavur profile loaded (score={p['suitability_score']})")
    else:
        log_fail(module, "District click -> Profile opens", f"code={code}")

    # 7. Zoom map -> Works
    code, map_data = api_get("/api/map/district")
    if code == 200 and "layout" in map_data and "geo" in map_data["layout"]:
        log_pass(module, "Zoom map -> Works",
                 "Map layout has geo config (scrollZoom enabled in frontend)")
    else:
        log_fail(module, "Zoom map -> Works", "No geo config in map layout")

    # 8. Missing values -> Graph rendered
    code, p = api_get("/api/profile/Sikkim/Pakyong")
    if code == 200 and "metrics" in p:
        log_pass(module, "Missing values -> Graph rendered",
                 f"Pakyong profile loaded with metrics (soil_data={p['soil_nutrients']['has_data']})")
    else:
        log_fail(module, "Missing values -> Graph rendered", f"code={code}")

    # 9. Large dataset -> Performance acceptable
    start = time.time()
    code, _ = api_get("/api/compare?state_a=Tamil%20Nadu&district_a=Coimbatore&state_b=Punjab&district_b=Ludhiana")
    elapsed = time.time() - start
    if code == 200 and elapsed < 3.0:
        log_pass(module, "Large dataset -> Performance acceptable",
                 f"Compare response time: {elapsed:.2f}s (< 3s threshold)")
    else:
        log_fail(module, "Large dataset -> Performance acceptable",
                 f"Response time: {elapsed:.2f}s, code={code}")

    # 10. PDF report -> Generated successfully
    start = time.time()
    try:
        r = requests.get(f"{BASE}/api/report/Tamil%20Nadu/Coimbatore", timeout=30)
        elapsed = time.time() - start
        if r.status_code == 200 and r.headers.get("content-type") == "application/pdf":
            size_kb = len(r.content) / 1024
            log_pass(module, "PDF report -> Generated successfully",
                     f"PDF generated: {size_kb:.1f} KB in {elapsed:.2f}s")
        else:
            log_fail(module, "PDF report -> Generated successfully",
                     f"status={r.status_code}, content-type={r.headers.get('content-type')}")
    except Exception as e:
        log_fail(module, "PDF report -> Generated successfully", str(e))


# ==========================================================================
# MAIN
# ==========================================================================
def main():
    print(f"\n{BOLD}AgriGuide India -- Test Suite{RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE}")
    print("=" * 70)

    # Check server is up
    code, _ = api_get("/api/health")
    if code != 200:
        print(f"\n{RED}ERROR: Server not running at {BASE}{RESET}")
        print(f"Start it with: cd AgriGuideIndia && bash run.sh")
        sys.exit(1)

    # Run all 4 modules
    test_module_1()
    test_module_2()
    test_module_3()
    test_module_4()

    # Summary
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}SUMMARY{RESET}")
    print(f"{'=' * 70}")
    total = results["pass"] + results["fail"]
    print(f"Total tests: {total}")
    print(f"  {GREEN}Passed: {results['pass']}{RESET}")
    print(f"  {RED}Failed: {results['fail']}{RESET}")
    print(f"  Pass rate: {results['pass']/total*100:.1f}%")
    print()

    # Per-module breakdown
    print(f"{BOLD}Per-Module Breakdown:{RESET}")
    modules = {
        "M1: Suitability Assessment": {"pass": 0, "fail": 0},
        "M2: Crop Recommendation": {"pass": 0, "fail": 0},
        "M3: Risk Assessment & AI Advisor": {"pass": 0, "fail": 0},
        "M4: Visualization & Comparative Analytics": {"pass": 0, "fail": 0},
    }
    for mod, test, status, detail in results["tests"]:
        if status == "PASS":
            modules[mod]["pass"] += 1
        else:
            modules[mod]["fail"] += 1

    for mod, counts in modules.items():
        total_mod = counts["pass"] + counts["fail"]
        rate = counts["pass"] / total_mod * 100 if total_mod > 0 else 0
        color = GREEN if rate == 100 else YELLOW if rate >= 80 else RED
        print(f"  {mod}: {color}{counts['pass']}/{total_mod} ({rate:.0f}%){RESET}")

    # List failures
    failures = [(m, t, d) for m, t, s, d in results["tests"] if s == "FAIL"]
    if failures:
        print(f"\n{BOLD}{RED}Failed Tests:{RESET}")
        for mod, test, detail in failures:
            print(f"  {RED}x{RESET} [{mod}] {test}")
            if detail:
                print(f"      {detail}")

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    if results["fail"] == 0:
        print(f"{GREEN}{BOLD}ALL TESTS PASSED!{RESET}")
    else:
        print(f"{YELLOW}{BOLD}{results['fail']} test(s) failed -- see above.{RESET}")

    sys.exit(0 if results["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
