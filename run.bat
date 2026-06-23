@echo off
REM ==========================================================================
REM AgriGuide India - Run Script (Windows)
REM ==========================================================================
REM Usage:
REM   1. Copy .env.example to .env  ->  fill in your LLM_API_KEY
REM   2. Double-click run.bat  (or run from Command Prompt)
REM --------------------------------------------------------------------------
cd /d "%~dp0"

REM --- Load .env if it exists ---
if exist .env (
    echo Loading .env ...
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "%%a=%%b"
    )
)

REM --- Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM --- Check dependencies ---
python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies ...
    python -m pip install --user flask pandas numpy scikit-learn plotly reportlab
)

REM --- Build cache if missing ---
if not exist cache\district_profiles.json (
    echo Building data cache first run, ~30 seconds ...
    python src\data_processor.py --force
)

REM --- Print LLM status ---
if defined LLM_API_KEY (
    echo LLM advisor ENABLED
) else (
    echo LLM_API_KEY not set - advisor will run in offline rule-based mode.
    echo   See .env.example for setup instructions.
)

REM --- Start server ---
if not defined PORT set PORT=5000
echo.
echo AgriGuide India starting on http://localhost:%PORT%
echo    Press Ctrl+C to stop.
echo.
python app.py
pause
