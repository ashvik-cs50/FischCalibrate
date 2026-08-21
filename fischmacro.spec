# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for the Fisch AI Macro.

Builds TWO standalone, dependency-free programs:
  * FischMacro   -> the autopilot (double-click to run)
  * FischCalibrate -> the region/color calibration tool

Platform behaviour:
  * Windows  -> FischMacro.exe (console) + FischCalibrate.exe
  * macOS    -> FischMacro.app (double-click bundle) + FischCalibrate.app

Build with:
    pyinstaller fischmacro.spec --noconfirm
(or just run build.bat / build.command which call this for you)
"""

import sys
from PyInstaller.utils.hooks import collect_submodules

IS_MAC = sys.platform == "darwin"

# pynput / pyautogui load platform backends dynamically -> help PyInstaller find them
hidden = (
    collect_submodules("pynput")
    + collect_submodules("pyautogui")
    + collect_submodules("mss")
    + collect_submodules("requests")
    + ["encodings.idna"]  # requests/urllib3 needs this at runtime when frozen
)

# Bundle a default config next to the code (copied out to an editable location
# on first run by src/paths.py).
datas = [("config.json", ".")]


def build(entry, name):
    a = Analysis(
        [entry],
        pathex=["src"],
        binaries=[],
        datas=datas,
        hiddenimports=hidden,
        hookspath=[],
        runtime_hooks=[],
        excludes=[],
        noarchive=False,
    )
    pyz = PYZ(a.pure)
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        # macOS: windowed app (no stray terminal); Windows: keep console for status
        console=not IS_MAC,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    return a, exe


macro_a, macro_exe = build("src/macro.py", "FischMacro")
calib_a, calib_exe = build("src/calibrate.py", "FischCalibrate")

if IS_MAC:
    macro_app = BUNDLE(
        macro_exe,
        name="FischMacro.app",
        icon=None,
        bundle_identifier="com.fischmacro.autopilot",
        info_plist={
            "NSHighResolutionCapable": True,
            # Ask for the permissions the tool needs on macOS.
            "NSAppleEventsUsageDescription": "Control the mouse to play the game.",
        },
    )
    calib_app = BUNDLE(
        calib_exe,
        name="FischCalibrate.app",
        icon=None,
        bundle_identifier="com.fischmacro.calibrate",
        info_plist={"NSHighResolutionCapable": True},
    )
