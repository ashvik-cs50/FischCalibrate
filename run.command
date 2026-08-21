#!/bin/bash
# ============================================================
#  Fisch AI Macro - macOS launcher
#  Double-click (or run in Terminal) to set up and start.
#  NOTE: macOS needs Accessibility + Screen Recording permission
#        granted to your Terminal app (System Settings > Privacy).
# ============================================================
cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
    echo "[setup] Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "[setup] Installing dependencies..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo
echo "Starting macro. Focus the Roblox window, then press F8 to fish, F9 to quit."
echo
python src/macro.py
