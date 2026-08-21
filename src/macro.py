"""
macro.py
--------
The brain. A small state machine that plays Fisch on autopilot:

    IDLE ──(F8)──► CAST ──► WAIT_BITE ──► SHAKE ──► REEL ──► (loop) ──► CAST
                    ▲                                             │
                    └─────────────────────────────────────────────┘

  CAST      : click at the cast point to throw the rod.
  WAIT_BITE : short pause while the bobber lands / a fish bites.
  SHAKE     : the vision engine hunts the white "Shake!" prompt and clicks it
              repeatedly until it disappears (bite secured).
  REEL      : the control loop. Vision reads the fish (target) and the player
              marker; we hold/release left-click to keep the marker on the fish
              until the catch completes or times out.

Hotkeys (global, work even when Roblox is focused):
    F8  -> start / stop the autopilot
    F9  -> quit the program

The goal: catch as many good fish as possible, hands-free.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from enum import Enum, auto

from pynput import keyboard

# Allow running as `python src/macro.py` or `python -m src.macro`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hf_client import HuggingFaceBrain          # noqa: E402
from input_controller import InputController  # noqa: E402
from paths import resolve_config_path, setup_logging  # noqa: E402
from vision import Vision                       # noqa: E402


class State(Enum):
    IDLE = auto()
    CAST = auto()
    WAIT_BITE = auto()
    SHAKE = auto()
    REEL = auto()
    COOLDOWN = auto()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class FischMacro:
    def __init__(self, config_path: str) -> None:
        self.cfg = load_config(config_path)
        self.vision = Vision(self.cfg)
        self.input = InputController()
        self.brain = HuggingFaceBrain(self.cfg)

        self.running = False           # is the autopilot actively fishing?
        self.alive = True              # is the program itself alive?
        self.state = State.IDLE

        self.stats = {"casts": 0, "catches": 0, "good": 0, "start": time.time()}
        self._t = self.cfg["timings"]
        self._debug = self.cfg.get("debug", {})

    # ---- hotkeys --------------------------------------------------------
    def _on_key(self, key) -> None:
        name = getattr(key, "name", None) or getattr(key, "char", None)
        if name is None:
            return
        name = name.lower()
        if name == self.cfg["hotkeys"]["start_stop"]:
            self.toggle()
        elif name == self.cfg["hotkeys"]["quit"]:
            self.shutdown()

    def toggle(self) -> None:
        self.running = not self.running
        if self.running:
            self.state = State.CAST
            print("\n[▶] Autopilot ON — fishing started.")
        else:
            self.input.cleanup()
            self.state = State.IDLE
            print("\n[⏸] Autopilot OFF — idle. (press F8 to resume)")

    def shutdown(self) -> None:
        print("\n[✗] Quitting…")
        self.running = False
        self.alive = False
        self.input.cleanup()

    # ---- main loop ------------------------------------------------------
    def run(self) -> None:
        self._print_banner()
        listener = keyboard.Listener(on_press=self._on_key)
        listener.start()

        try:
            while self.alive:
                if not self.running:
                    time.sleep(0.05)
                    continue
                self._step()
        finally:
            self.input.cleanup()
            listener.stop()

    def _step(self) -> None:
        if self.state == State.CAST:
            self._do_cast()
        elif self.state == State.WAIT_BITE:
            self._do_wait_bite()
        elif self.state == State.SHAKE:
            self._do_shake()
        elif self.state == State.REEL:
            self._do_reel()
        elif self.state == State.COOLDOWN:
            self._log("cooldown")
            self._sleep_interruptible(self._t["loop_cooldown_seconds"])
            if self.running:
                self.state = State.CAST

    # ---- states ---------------------------------------------------------
    def _do_cast(self) -> None:
        cx, cy = self.vision.frac_to_abs_point(
            self.cfg["cast"]["click_x_frac"],
            self.cfg["cast"]["click_y_frac"],
        )
        self._log("cast")
        self.input.move(cx, cy)
        self.input.hold_left()
        self._sleep_interruptible(self._t["cast_hold_seconds"])
        self.input.release_left()
        self.stats["casts"] += 1
        self.state = State.WAIT_BITE

    def _do_wait_bite(self) -> None:
        self._log("wait for bite")
        self._sleep_interruptible(self._t["wait_after_cast_seconds"])
        if self.running:
            self.state = State.SHAKE

    def _do_shake(self) -> None:
        self._log("scanning for shake prompt")
        deadline = time.time() + self._t["shake_scan_timeout_seconds"]
        clicks = 0
        misses = 0
        settle = self.cfg["shake"].get("click_settle_seconds", 0.05)

        while self.running and time.time() < deadline:
            point = self.vision.find_shake_click()
            if point:
                self.input.tap(point[0], point[1], settle=settle)
                clicks += 1
                misses = 0
            else:
                misses += 1
                # A short streak of "no prompt" after we've clicked at least
                # once means the shake phase is over -> move on to reeling.
                if clicks > 0 and misses >= 6:
                    break
                time.sleep(0.03)

        self.state = State.REEL if self.running else State.IDLE

    def _do_reel(self) -> None:
        self._log("reeling")
        r = self.cfg["reel"]
        deadzone_frac = float(r.get("deadzone_frac", 0.04))
        hold_bias = float(r.get("hold_bias", 0.5))
        tick = self._t["reel_tick_seconds"]

        deadline = time.time() + self._t["reel_timeout_seconds"]
        last_valid = time.time()
        empty_streak = 0

        while self.running and time.time() < deadline:
            # progress-bar based completion (optional)
            prog = self.vision.read_progress()
            if prog is not None and prog >= r["progress"]["full_fraction"]:
                self._catch_done("progress full")
                return

            reading = self.vision.read_reel()
            if not reading.valid:
                empty_streak += 1
                # If the bar disappeared for a moment after we were tracking,
                # the catch likely finished.
                if time.time() - last_valid > 0.6 and empty_streak > 8:
                    self._catch_done("bar gone")
                    return
                time.sleep(tick)
                continue

            empty_streak = 0
            last_valid = time.time()

            span = max(1.0, reading.region_right - reading.region_left)
            error = (reading.target_x - reading.control_x) / span  # -1..1

            if error > deadzone_frac:
                # target is to the RIGHT of us -> push right (hold)
                self.input.hold_left()
            elif error < -deadzone_frac:
                # target is to the LEFT -> release to drift left
                self.input.release_left()
            else:
                # centered: apply a light bias hold to counteract gravity
                if hold_bias >= 0.5:
                    self.input.hold_left()
                else:
                    self.input.release_left()

            time.sleep(tick)

        # timed out or stopped
        self.input.release_left()
        if self.running:
            self._catch_done("reel timeout")
        else:
            self.state = State.IDLE

    # ---- helpers --------------------------------------------------------
    def _catch_done(self, reason: str) -> None:
        self.input.release_left()
        self.stats["catches"] += 1
        elapsed = time.time() - self.stats["start"]
        rate = self.stats["catches"] / (elapsed / 3600) if elapsed > 0 else 0
        print(f"[🎣] Catch #{self.stats['catches']} ({reason}) "
              f"| casts={self.stats['casts']} | good={self.stats['good']} "
              f"| ~{rate:.0f}/hr")
        self._evaluate_catch()
        self.state = State.COOLDOWN

    def _evaluate_catch(self) -> None:
        """Ask the Hugging Face cloud brain whether this catch is a good one and,
        if so, favorite it. Silently no-ops if HF is disabled/unreachable."""
        if not self.brain.ready:
            return
        catch_cfg = self.cfg.get("catch", {})
        region = catch_cfg.get("region")
        if not region:
            return

        # let the catch popup fully appear before screenshotting
        self._sleep_interruptible(float(catch_cfg.get("act_after_seconds", 0.4)))
        image_png = self.vision.capture_png(region)
        verdict = self.brain.classify_catch(image_png)
        if verdict is None:
            return

        tag = "GOOD" if verdict.is_good else "skip"
        print(f"[🧠] HF verdict: '{verdict.label}' "
              f"({verdict.score:.2f}) -> {tag}")

        if verdict.is_good:
            self.stats["good"] += 1
            if catch_cfg.get("act_on_good", True):
                self.input.press_key(catch_cfg.get("favorite_key", "f"))
                print(f"[⭐] Favorited good catch "
                      f"(key '{catch_cfg.get('favorite_key', 'f')}').")

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if not self.running or not self.alive:
                return
            time.sleep(min(0.03, end - time.time()))

    def _log(self, msg: str) -> None:
        if self._debug.get("print_state", True):
            print(f"[{self.state.name:<9}] {msg}")

    def _print_banner(self) -> None:
        sk = self.cfg["hotkeys"]["start_stop"].upper()
        qk = self.cfg["hotkeys"]["quit"].upper()
        print("=" * 58)
        print("  FISCH AI MACRO — local computer-vision autopilot")
        print("=" * 58)
        print(f"  Input backend : {self.input.backend}")
        print(f"  Monitor       : {self.vision.screen_w}x{self.vision.screen_h}")
        brain = (f"Hugging Face ({self.brain.model})" if self.brain.ready
                 else "off (keeping every catch)")
        print(f"  Catch brain   : {brain}")
        print(f"  Start / Stop  : {sk}")
        print(f"  Quit          : {qk}")
        print("-" * 58)
        print("  Focus the Roblox window, then press START.")
        print("=" * 58)


def main() -> None:
    setup_logging()
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else resolve_config_path()
    FischMacro(cfg_path).run()


if __name__ == "__main__":
    main()
