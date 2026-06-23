#!/usr/bin/env bash
# ==========================================================================
# AgriGuide India — Run Script (Mac / Linux)
# ==========================================================================
# Usage:
#   1. Copy .env.example to .env  →  fill in your LLM_API_KEY
#   2. bash run.sh
# --------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

# --- Load .env if it exists ---
if [ -f .env ]; then
  echo "Loading .env ..."
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# --- Check Python ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ from https://python.org"
  exit 1
fi

# --- Check dependencies ---
python3 -c "import flask" 2>/dev/null || {
  echo "Installing dependencies ..."
  python3 -m pip install --user flask pandas numpy scikit-learn plotly reportlab
}

# --- Build cache if missing ---
if [ ! -f cache/district_profiles.json ]; then
  echo "Building data cache (first run, ~30 seconds) ..."
  python3 src/data_processor.py --force
fi

# --- Print LLM status ---
if [ -n "$LLM_API_KEY" ]; then
  echo "✓ LLM advisor ENABLED (model: ${LLM_MODEL:-gpt-4o-mini})"
else
  echo "⚠ LLM_API_KEY not set — advisor will run in offline rule-based mode."
  echo "  See .env.example for setup instructions."
fi

# --- Start server ---
PORT="${PORT:-5000}"
echo ""
echo "🚀 AgriGuide India starting on http://localhost:$PORT"
echo "   Press Ctrl+C to stop."
echo ""
exec python3 app.py
