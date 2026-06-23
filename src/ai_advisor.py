"""
AgriGuide India — AI Farming Advisor
====================================
Hybrid advisor:
  1) If LLM_API_KEY env var is set → calls an OpenAI-compatible chat API
     (OpenAI, Groq, Together, OpenRouter, ZAI, Ollama, etc.) with the
     district profile as context.
  2) Otherwise → falls back to a fully-offline rule-based advisor that
     uses intent detection to compose district-specific answers.

Both paths return the same response shape so the frontend doesn't change.

Environment variables
---------------------
LLM_API_KEY    (required for LLM mode)   Your API key, e.g. "sk-..."
LLM_BASE_URL   (optional, default OpenAI)  e.g. "https://api.openai.com/v1"
LLM_MODEL      (optional, default gpt-4o-mini)  e.g. "gpt-4o", "llama-3.1-70b"
"""

from __future__ import annotations
import os
import re
import json
from typing import Dict, List, Optional
from . import data_processor as dp
from . import recommendation_engine as rec


# --------------------------------------------------------------------------- #
# LLM client (OpenAI-compatible chat completions)
# --------------------------------------------------------------------------- #
def _llm_config() -> Dict:
    """Read LLM config from environment, return None if not configured."""
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    }


def _build_system_prompt(state: Optional[str], district: Optional[str],
                         user_message: str = "") -> str:
    """Build a context-rich system prompt using the district profile.

    Detects district names mentioned in the user's message and loads those
    profiles too — so the LLM can answer questions about ANY district in
    India, not just the currently-selected one.
    """
    base = (
        "You are AgriGuide AI, a friendly and practical farming advisor for "
        "Indian farmers and citizens. You answer questions about crop selection, "
        "irrigation, fertilizer, soil, rainfall, risks, yields, seasons, and "
        "nearby alternatives for ANY district in India.\n\n"
        "Guidelines:\n"
        "- Answer in plain, simple language a farmer can understand.\n"
        "- Keep answers concise: 3-6 short sentences or a tight bullet list.\n"
        "- Always reference the specific district data when relevant.\n"
        "- If recommending crops, mention 2-3 specific crops with reasoning.\n"
        "- If suggesting practices, give concrete, actionable steps.\n"
        "- Use **bold** for crop names, district names, and key numbers.\n"
        "- You can answer questions about ANY district — if the user mentions "
        "a different district than the one currently selected, USE THE DATA "
        "PROVIDED IN THE CONTEXT for that mentioned district. Do NOT refuse.\n"
        "- If a user asks about a district and you have data for it, answer "
        "with that district's specific profile. The 'currently selected "
        "district' is just a default, not a constraint.\n"
        "- If the question is unrelated to agriculture, politely redirect.\n"
    )

    # ----- Detect any districts mentioned in the user's message -----
    mentioned = detect_districts_in_message(user_message) if user_message else []

    # Build a list of district profiles to include in context:
    # 1. The currently-selected district (if any) — labeled as "default"
    # 2. Any districts mentioned in the message (deduped against #1)
    contexts: List[str] = []

    if state and district:
        sel = dp.get_district(state, district)
        if sel:
            contexts.append(_format_district_context(sel, is_selected=True))

    for m_state, m_district in mentioned:
        # Skip if it's the same as the selected district
        if state and district and m_state == state and m_district == district:
            continue
        m_profile = dp.get_district(m_state, m_district)
        if m_profile:
            contexts.append(_format_district_context(m_profile, is_selected=False))

    if not contexts:
        if mentioned:
            return base + (
                f"\nNOTE: The user asked about district(s) {', '.join(d for _, d in mentioned)} "
                "but that district is not in our database of 740 Indian districts. "
                "Politely let the user know and suggest they pick a different district or "
                "search the map for nearby options."
            )
        return base + (
            "\nNo specific district context is available yet. If the user asks a "
            "district-specific question, ask them which district they'd like to know about. "
            "You can answer general agricultural questions even without a district."
        )

    return base + "\n\n" + "\n\n".join(contexts)


def _format_district_context(profile: Dict, is_selected: bool = False) -> str:
    """Format a single district's profile for inclusion in the system prompt."""
    state = profile["state"]
    district = profile["district"]
    crops = rec.recommend_top_crops(state, district, top_n=5)
    risks = profile.get("risks", [])

    label = "CURRENTLY SELECTED DISTRICT (default if user doesn't specify)" if is_selected \
            else "DISTRICT MENTIONED BY USER (use this if the user is asking about this district)"

    crops_str = "\n".join(
        f"  - {c['crop']}: {c['suitability_pct']}% suitability, "
        f"{c['performance_rating']} (confidence {c['confidence']}%, "
        f"avg yield {c['avg_yield']} t/ha)"
        for c in crops
    ) or "  - (insufficient crop data)"

    risks_str = "\n".join(
        f"  - {r['name']} ({r['level']}, score {r['score']}/100): {r['detail']}"
        for r in risks
    ) or "  - No major risks identified"

    return f"""=== {label} ===
- District: {district}, {state}
- Overall agricultural suitability score: {profile['suitability_score']}/100 ({profile['suitability_category']})
- Rainfall (estimated): ~{profile['rainfall_mm']} mm/year
- Soil quality index: {profile['soil_quality']}/100
- Mean temperature (estimated): ~{profile['temperature_c']}°C
- Irrigation dependency: {profile['irrigation_dependency']}/100
- Crops historically grown: {profile['n_crops_grown']}
- Years of data: {profile['n_years_data']}

TOP RECOMMENDED CROPS for {district}:
{crops_str}

MAJOR RISK FACTORS for {district}:
{risks_str}"""


def detect_districts_in_message(message: str) -> List[tuple]:
    """Detect Indian district names mentioned in a user message.

    Returns list of (state, district) tuples for any district names found
    in our database of 740 districts. Case-insensitive, also handles
    partial matches like "Chennai" matching the district "Chennai".
    """
    if not message:
        return []
    msg_lower = message.lower()
    profiles = dp.get_all_districts()  # dict keyed by "state__district"
    matches: List[tuple] = []

    # Build a sorted list of district names (longest first to prefer
    # "West Godavari" over "Godavari" if both appear)
    all_districts = sorted(
        ((key.split("__", 1)[1], key.split("__", 1)[0]) for key in profiles.keys()),
        key=lambda x: -len(x[0])
    )

    for district_name, state_name in all_districts:
        d_lower = district_name.lower()
        # Word-boundary match (avoids matching "Pune" inside "Puneet")
        if re.search(r'\b' + re.escape(d_lower) + r'\b', msg_lower):
            # Avoid duplicate state__district entries
            if (state_name, district_name) not in matches:
                matches.append((state_name, district_name))
            # Stop after 3 matches to keep context manageable
            if len(matches) >= 3:
                break

    return matches


def ask_llm(message: str, state: Optional[str], district: Optional[str]) -> str:
    """Call the LLM API and return the assistant's reply as plain text.
    Raises on any error so caller can fall back to rule-based."""
    cfg = _llm_config()
    if not cfg:
        raise RuntimeError("LLM_API_KEY not set")

    # Use urllib to avoid adding `requests` as a hard dependency
    import urllib.request
    import urllib.error

    system_prompt = _build_system_prompt(state, district, user_message=message)
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.4,
        "max_tokens": 600,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"LLM API HTTP {e.code}: {err_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM API network error: {e.reason}")


# --------------------------------------------------------------------------- #
# Intent detection (used by both LLM and rule-based paths)
# --------------------------------------------------------------------------- #
INTENT_PATTERNS: List[Dict] = [
    {"intent": "recommend_crop", "patterns": [
        r"\bwhich crop\b", r"\bwhat crop\b", r"\bbest crop\b",
        r"\brecommend.*crop\b", r"\bwhat should i grow\b",
        r"\bwhich should i (plant|grow|cultivate)\b",
    ]},
    {"intent": "irrigation", "patterns": [
        r"\birrigat", r"\bwater (method|supply|management)\b",
        r"\bwatering\b", r"\bdrip\b", r"\bsprinkler\b",
    ]},
    {"intent": "fertilizer", "patterns": [
        r"\bfertil", r"\bnpk\b", r"\bmanure\b", r"\bcompost\b",
        r"\burea\b", r"\bnutrient\b",
    ]},
    {"intent": "risks", "patterns": [
        r"\brisk", r"\bthreat\b", r"\bchallenge\b", r"\bproblem\b",
        r"\bdanger\b", r"\bhazard\b",
    ]},
    {"intent": "yield", "patterns": [
        r"\byield\b", r"\bproduction\b", r"\boutput\b",
        r"\bwhich crop gives\b", r"\bbest yield\b",
    ]},
    {"intent": "soil", "patterns": [
        r"\bsoil\b", r"\bph\b", r"\bnutrient\b", r"\bfertility\b",
    ]},
    {"intent": "rainfall", "patterns": [
        r"\brain", r"\bprecipitation\b", r"\bmonsoon\b",
    ]},
    {"intent": "compare", "patterns": [
        r"\bcompare\b", r"\bnearby\b", r"\balternative\b",
        r"\bother district\b",
    ]},
    {"intent": "season", "patterns": [
        r"\bseason\b", r"\bwhen.*plant\b", r"\bsowing\b",
        r"\bharvest\b", r"\bkharif\b", r"\brabi\b",
    ]},
]


def detect_intent(message: str) -> str:
    m = message.lower()
    for entry in INTENT_PATTERNS:
        for pat in entry["patterns"]:
            if re.search(pat, m):
                return entry["intent"]
    return "general"


# ------------------------- Response builders ------------------------- #
def _format_top_crops(state: str, district: str) -> str:
    crops = rec.recommend_top_crops(state, district, top_n=5)
    if not crops:
        return "I don't have enough crop data for this district."
    lines = [f"Based on {district}, {state}'s historical performance, here are your top 5 recommended crops:"]
    for i, c in enumerate(crops, 1):
        lines.append(f"{i}. **{c['crop']}** — {c['suitability_pct']}% suitability "
                     f"({c['performance_rating']}, confidence {c['confidence']}%)")
    lines.append("")
    lines.append(f"The strongest pick is **{crops[0]['crop']}** at {crops[0]['suitability_pct']}% — "
                 "consider it as your primary crop if it fits your market and resources.")
    return "\n".join(lines)


def _format_irrigation(state: str, district: str) -> str:
    p = dp.get_district(state, district)
    if not p:
        return "Please select a district first."
    deps = p["irrigation_dependency"]
    rain = p["rainfall_mm"]
    crops = rec.recommend_top_crops(state, district, top_n=3)
    lines = [
        f"For **{district}, {state}**:",
        f"- Estimated rainfall: ~{rain} mm/year",
        f"- Irrigation dependency index: {deps}/100",
    ]
    if deps > 60:
        lines.append("- ⚠️ High irrigation dependency — prioritise **drip or sprinkler irrigation** to conserve water.")
    elif rain > 1500:
        lines.append("- Adequate rainfall — **protect crops from waterlogging** with good drainage.")
    else:
        lines.append("- Moderate irrigation needs — **basin or furrow irrigation** is generally suitable.")
    if crops:
        lines.append("")
        lines.append("Crop-specific advice:")
        for c in crops:
            lines.append(f"- {c['crop']}: {c['advice']['irrigation']}")
    return "\n".join(lines)


def _format_fertilizer(state: str, district: str) -> str:
    p = dp.get_district(state, district)
    if not p:
        return "Please select a district first."
    crops = rec.recommend_top_crops(state, district, top_n=3)
    lines = [
        f"Fertilizer strategy for **{district}, {state}**:",
        f"- Soil quality index: {p['soil_quality']}/100 — "
        + ("adequate; maintain with regular organic inputs." if p["soil_quality"] >= 60
           else "low; prioritise soil amendments and organic matter."),
        "",
        "Recommended approach by crop:",
    ]
    for c in crops:
        lines.append(f"- **{c['crop']}**: {c['advice']['fertilizer']}")
    lines.append("")
    lines.append("Tip: Always base NPK rates on a recent soil test — overuse wastes money and degrades soil.")
    return "\n".join(lines)


def _format_risks(state: str, district: str) -> str:
    p = dp.get_district(state, district)
    if not p:
        return "Please select a district first."
    lines = [f"Major agricultural risks for **{district}, {state}**:"]
    for r in p["risks"]:
        lines.append(f"- **{r['name']}** ({r['level']}, score {r['score']}/100)")
        lines.append(f"  - {r['detail']}")
        lines.append(f"  - Mitigation: {r['mitigation']}")
    return "\n".join(lines)


def _format_yield(state: str, district: str) -> str:
    crops = rec.recommend_top_crops(state, district, top_n=5)
    if not crops:
        return "Insufficient yield data for this district."
    crops_by_yield = sorted(crops, key=lambda c: c["avg_yield"], reverse=True)
    top = crops_by_yield[0]
    lines = [
        f"For **{district}, {state}**, the highest-yielding recommended crop is **{top['crop']}** "
        f"with an average yield of {top['avg_yield']} tonnes/hectare.",
        "",
        "Yield ranking (top 5):",
    ]
    for c in crops_by_yield:
        lines.append(f"- {c['crop']}: {c['avg_yield']} t/ha")
    return "\n".join(lines)


def _format_soil(state: str, district: str) -> str:
    p = dp.get_district(state, district)
    if not p:
        return "Please select a district first."
    lines = [
        f"Soil profile for **{district}, {state}**:",
        f"- Quality index: {p['soil_quality']}/100",
        f"- Suitability score: {p['suitability_score']}/100 ({p['suitability_category']})",
        f"- Crops historically grown: {p['n_crops_grown']}",
    ]
    if p["soil_quality"] < 40:
        lines.append("- Recommendation: Apply 10-15 t/ha FYM or compost; introduce legumes in rotation to fix nitrogen.")
    elif p["soil_quality"] < 70:
        lines.append("- Recommendation: Maintain fertility with green manuring and balanced NPK.")
    else:
        lines.append("- Soil is in good condition — sustain with regular organic inputs and cover cropping.")
    return "\n".join(lines)


def _format_rainfall(state: str, district: str) -> str:
    p = dp.get_district(state, district)
    if not p:
        return "Please select a district first."
    rain = p["rainfall_mm"]
    lines = [
        f"Rainfall profile for **{district}, {state}**:",
        f"- Estimated annual rainfall: ~{rain} mm",
    ]
    if rain < 700:
        lines.append("- Low rainfall zone — choose drought-tolerant crops like bajra, jowar, millets, groundnut.")
    elif rain < 1200:
        lines.append("- Moderate rainfall — suitable for maize, pulses, cotton, oilseeds.")
    elif rain < 1800:
        lines.append("- Good rainfall — suitable for rice, sugarcane, banana, cotton.")
    else:
        lines.append("- High rainfall — ensure drainage; rice, banana, coconut, tapioca thrive.")
    return "\n".join(lines)


def _format_compare(state: str, district: str) -> str:
    alts = rec.suggest_alternatives(state, district, limit=5)
    if not alts:
        return f"No nearby districts with better suitability were found for {district}. Your district is already well-suited or the top performer in its region."
    lines = [f"Nearby districts with **better agricultural suitability** than {district}, {state}:"]
    for a in alts:
        lines.append(f"- {a['district']}, {a['state']} — {a['distance_km']:.0f} km away, "
                     f"score {a['suitability_score']}/100 ({a['category']}), top crop: {a['top_crop']}")
    return "\n".join(lines)


def _format_season(state: str, district: str) -> str:
    crops = rec.recommend_top_crops(state, district, top_n=5)
    if not crops:
        return "Insufficient data for season advice."
    lines = [f"Sowing seasons for top recommended crops in **{district}, {state}**:"]
    for c in crops:
        lines.append(f"- {c['crop']}: {c['advice']['season']}")
    return "\n".join(lines)


def _format_general(state: str, district: str) -> str:
    summary = rec.get_summary(state, district)
    lines = [summary["headline"], ""]
    lines.extend(summary["bullets"])
    lines.append("")
    lines.append("You can ask me about: **crop recommendation, irrigation, fertilizer, risks, "
                 "yield, soil, rainfall, season, or nearby districts**.")
    return "\n".join(lines)


INTENT_HANDLERS = {
    "recommend_crop": _format_top_crops,
    "irrigation":     _format_irrigation,
    "fertilizer":     _format_fertilizer,
    "risks":          _format_risks,
    "yield":          _format_yield,
    "soil":           _format_soil,
    "rainfall":       _format_rainfall,
    "compare":        _format_compare,
    "season":         _format_season,
    "general":        _format_general,
}


# ------------------------- Public API ------------------------- #
SUGGESTED_QUESTIONS = [
    "Which crop should I grow?",
    "What irrigation method is recommended?",
    "What fertilizer strategy should I use?",
    "Which crop gives the best yield?",
    "What are the major agricultural risks?",
    "Are there better nearby districts?",
]


def ask(message: str, state: Optional[str] = None, district: Optional[str] = None) -> Dict:
    """Return an advisor response.

    Tries LLM first if LLM_API_KEY is set; falls back to rule-based on any
    error. Always returns the same response shape:
        {intent, answer, suggested_questions, source}
    where `source` is "llm" or "rules" so the frontend can show a small badge.
    """
    intent = detect_intent(message)
    source = "rules"

    # --- Try LLM path if configured ---
    if _llm_config():
        try:
            answer = ask_llm(message, state, district)
            # Refuse empty LLM responses
            if answer and len(answer.strip()) > 0:
                source = "llm"
                mentioned = detect_districts_in_message(message)
                return {
                    "intent": intent,
                    "answer": answer,
                    "suggested_questions": SUGGESTED_QUESTIONS[:4],
                    "source": source,
                    "detected_districts": [{"state": s, "district": d} for s, d in mentioned],
                }
        except Exception as e:
            # Log and fall through to rule-based
            print(f"[ai_advisor] LLM call failed, falling back to rules: {e}")

    # --- Rule-based fallback (or default if no API key) ---
    # If the user mentioned a different district in their message, switch
    # the rule-based handler to use THAT district (not the selected one).
    effective_state, effective_district = state, district
    mentioned = detect_districts_in_message(message)
    if mentioned:
        # If they mentioned multiple, use the first one that isn't the selected
        for m_state, m_district in mentioned:
            if not (state and district and m_state == state and m_district == district):
                effective_state, effective_district = m_state, m_district
                break

    if effective_state and effective_district:
        handler = INTENT_HANDLERS.get(intent, _format_general)
        try:
            answer = handler(effective_state, effective_district)
            # If we switched districts based on the message, prefix with note
            if mentioned and effective_state != state:
                answer = f"You asked about **{effective_district}, {effective_state}** — here's what the data says:\n\n" + answer
        except Exception as e:
            answer = f"I couldn't fully process that. Please try rephrasing. (Error: {e})"
    else:
        # No district selected — give general advice and ask user to pick a district
        answer = ("I'd love to help with that! Please **select your district** using the search "
                  "box or the map first — I'll then tailor my advice to your local conditions. "
                  "You can ask me about crops, irrigation, fertilizer, risks, yield, soil, "
                  "rainfall, seasons, or alternative districts.")

    return {
        "intent": intent,
        "answer": answer,
        "suggested_questions": SUGGESTED_QUESTIONS[:4],
        "source": source,
        "detected_districts": [{"state": s, "district": d} for s, d in mentioned],
    }
