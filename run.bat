@echo off
REM ============================================================
REM  Fisch AI Macro - Windows launcher
REM  Double-click this file to set up (first run) and start.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv" (
    echo [setup] Creating virtual environment...
    python -m venv .venv
    call ".venv\Scripts\activate.bat"
    echo [setup] Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

echo.
echo Starting macro. Focus the Roblox window, then press F8 to fish, F9 to quit.
echo.
python src\macro.py
pause
