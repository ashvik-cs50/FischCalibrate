#!/bin/bash
# ============================================================
#  Fisch AI Macro - macOS BUILD script
#  Produces FischMacro.app + FischCalibrate.app in dist/
#  (no Python needed to RUN them afterwards).
#  Double-click, or run: ./build.command
# ============================================================
cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
    echo "[setup] Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "[setup] Installing dependencies + PyInstaller..."
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo
echo "[build] Building FischMacro.app and FischCalibrate.app..."
pyinstaller fischmacro.spec --noconfirm

echo
echo "============================================================"
echo " Done! Your apps are in the  dist/  folder:"
echo "    dist/FischMacro.app        (the autopilot - open this)"
echo "    dist/FischCalibrate.app    (tuning tool - open once)"
echo
echo " First launch: right-click the app > Open (to bypass"
echo " Gatekeeper), and grant Accessibility + Screen Recording"
echo " in System Settings > Privacy & Security."
echo "============================================================"
