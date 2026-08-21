@echo off
REM ============================================================
REM  Fisch AI Macro - Windows BUILD script
REM  Produces standalone EXEs in the dist\ folder (no Python
REM  needed to RUN them afterwards).
REM  Just double-click this file.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv" (
    echo [setup] Creating virtual environment...
    python -m venv .venv
)
call ".venv\Scripts\activate.bat"

echo [setup] Installing dependencies + PyInstaller...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [build] Building FischMacro.exe and FischCalibrate.exe...
pyinstaller fischmacro.spec --noconfirm

echo.
echo ============================================================
echo  Done! Your programs are in the  dist\  folder:
echo     dist\FischMacro.exe        (the autopilot - run this)
echo     dist\FischCalibrate.exe    (tuning tool - run once)
echo ============================================================
pause
