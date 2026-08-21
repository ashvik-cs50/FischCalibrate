"""
input_controller.py
--------------------
Cross-platform (Windows + macOS) mouse/keyboard control for the macro.

Why not just pyautogui everywhere?
  - On Windows, many games ignore ordinary "SendInput" style clicks. `pydirectinput`
    speaks the lower-level API games expect, so we prefer it there.
  - On macOS, `pydirectinput` does not exist, so we use `pyautogui` (which needs
    Accessibility permission granted to your Terminal / Python).

This module hides those differences behind one small API:
    tap(x, y)          -> move + left click
    hold_left()        -> press and keep the left button down
    release_left()     -> let the left button up
    is_holding()       -> bool
"""

from __future__ import annotations

import platform
import time

import pyautogui

pyautogui.FAILSAFE = False   # we manage our own kill-switch hotkey
pyautogui.PAUSE = 0.0        # no implicit sleeps; we time things ourselves

_IS_WINDOWS = platform.system() == "Windows"

# Prefer pydirectinput on Windows for game-compatible input.
_backend = None
if _IS_WINDOWS:
    try:
        import pydirectinput  # type: ignore
        pydirectinput.FAILSAFE = False
        pydirectinput.PAUSE = 0.0
        _backend = pydirectinput
    except Exception:
        _backend = None


class InputController:
    def __init__(self) -> None:
        self._holding = False
        self._backend_name = "pydirectinput" if _backend else "pyautogui"

    @property
    def backend(self) -> str:
        return self._backend_name

    # ---- movement -------------------------------------------------------
    def move(self, x: int, y: int) -> None:
        x, y = int(x), int(y)
        if _backend:
            _backend.moveTo(x, y)
        else:
            pyautogui.moveTo(x, y)

    # ---- clicking -------------------------------------------------------
    def tap(self, x: int, y: int, settle: float = 0.03) -> None:
        """Move to (x, y) and perform a single left click."""
        self.move(x, y)
        time.sleep(0.01)
        if _backend:
            _backend.click()
        else:
            pyautogui.click()
        if settle:
            time.sleep(settle)

    # ---- press / hold ---------------------------------------------------
    def hold_left(self) -> None:
        if self._holding:
            return
        if _backend:
            _backend.mouseDown()
        else:
            pyautogui.mouseDown()
        self._holding = True

    def release_left(self) -> None:
        if not self._holding:
            return
        if _backend:
            _backend.mouseUp()
        else:
            pyautogui.mouseUp()
        self._holding = False

    def is_holding(self) -> bool:
        return self._holding

    # ---- keyboard -------------------------------------------------------
    def press_key(self, key: str) -> None:
        """Tap a keyboard key (e.g. the 'favorite' hotkey after a good catch)."""
        if not key:
            return
        if _backend:
            _backend.press(key)
        else:
            pyautogui.press(key)

    def cleanup(self) -> None:
        """Always release the mouse when stopping so it isn't stuck down."""
        try:
            self.release_left()
        except Exception:
            pass
