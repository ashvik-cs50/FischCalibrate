"""
paths.py
--------
Shared helpers for locating config.json and setting up logging, in a way that
works BOTH when running from source and when packaged into an .exe / .app with
PyInstaller.

Key idea for packaged builds: config.json (and the log file) should live in an
editable location NEXT TO the executable/app bundle, not inside the read-only
PyInstaller bundle. On first run we copy the bundled default out there.
"""

from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def external_dir() -> str:
    """The user-editable directory that sits next to the exe / .app.

    - From source: the project root (parent of src/).
    - Windows exe (onefile): the folder containing the .exe.
    - macOS .app: the folder containing the .app bundle.
    """
    if not is_frozen():
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(here)

    exe_dir = os.path.dirname(sys.executable)
    unix_dir = exe_dir.replace(os.sep, "/")
    if ".app/Contents/MacOS" in unix_dir:
        app_root = exe_dir.split(".app")[0] + ".app"
        return os.path.dirname(app_root)
    return exe_dir


def bundled_resource(name: str) -> str:
    """Path to a file bundled inside the PyInstaller archive (or on disk)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, name)
    return os.path.join(external_dir(), name)


def resolve_config_path() -> str:
    """Return the path to an editable config.json, creating it on first run."""
    ext = os.path.join(external_dir(), "config.json")
    if os.path.exists(ext):
        return ext

    if is_frozen():
        src = bundled_resource("config.json")
        try:
            with open(src, "r", encoding="utf-8") as s, \
                    open(ext, "w", encoding="utf-8") as d:
                d.write(s.read())
            print(f"[setup] Wrote editable config to {ext}")
            return ext
        except Exception:
            return src  # fall back to read-only bundled copy
    return ext


class _Tee:
    """Write to multiple streams at once (console + log file)."""

    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]

    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass


def setup_logging() -> None:
    """When packaged (esp. a windowless macOS .app), also log to a file so the
    user can confirm the tool is running. No-op when running from source."""
    if not is_frozen():
        return
    log_path = os.path.join(external_dir(), "fischmacro.log")
    try:
        f = open(log_path, "a", buffering=1, encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, f)
        sys.stderr = _Tee(sys.__stderr__, f)
        print(f"\n[log] --- session started, logging to {log_path} ---")
    except Exception:
        pass
