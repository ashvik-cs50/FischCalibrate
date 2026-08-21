"""
vision.py
---------
The local, forever-free "AI" of the macro: a computer-vision engine built on
OpenCV. No cloud, no API keys, no cost. It grabs pixels from your screen and
answers three questions the macro needs:

  1. find_shake_click()  -> where (if anywhere) is the white "Shake!" prompt?
  2. read_reel()         -> where is the target (fish) and the player marker?
  3. read_progress()     -> is the catch progress bar full yet?

Everything is driven by HSV color ranges in config.json so you can tune it to
your resolution / UI theme without touching code (use calibrate.py to help).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
from mss import mss


@dataclass
class ReelReading:
    target_x: Optional[float]      # absolute screen x of the fish/target center
    control_x: Optional[float]     # absolute screen x of the player marker
    region_left: int
    region_right: int

    @property
    def valid(self) -> bool:
        return self.target_x is not None and self.control_x is not None


class Vision:
    def __init__(self, config: dict) -> None:
        self.cfg = config
        self._sct = mss()
        monitors = self._sct.monitors
        idx = int(config.get("monitor", 1))
        idx = idx if 0 <= idx < len(monitors) else 1
        self.mon = monitors[idx]
        self.screen_w = self.mon["width"]
        self.screen_h = self.mon["height"]
        self.origin_x = self.mon["left"]
        self.origin_y = self.mon["top"]

    # ---- geometry helpers ----------------------------------------------
    def frac_to_abs_point(self, xf: float, yf: float) -> Tuple[int, int]:
        return (
            int(self.origin_x + xf * self.screen_w),
            int(self.origin_y + yf * self.screen_h),
        )

    def _region_box(self, region: dict) -> dict:
        return {
            "left": int(self.origin_x + region["x"] * self.screen_w),
            "top": int(self.origin_y + region["y"] * self.screen_h),
            "width": max(1, int(region["w"] * self.screen_w)),
            "height": max(1, int(region["h"] * self.screen_h)),
        }

    def grab(self, region: dict) -> np.ndarray:
        box = self._region_box(region)
        raw = np.asarray(self._sct.grab(box))     # BGRA
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def capture_png(self, region: dict) -> Optional[bytes]:
        """Grab a region and encode it as PNG bytes (for the HF cloud brain)."""
        frame = self.grab(region)
        ok, buf = cv2.imencode(".png", frame)
        return buf.tobytes() if ok else None

    @staticmethod
    def _mask(bgr: np.ndarray, lower, upper) -> np.ndarray:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))

    # ---- 1) shake detection --------------------------------------------
    def find_shake_click(self) -> Optional[Tuple[int, int]]:
        s = self.cfg["shake"]
        region = s["region"]
        frame = self.grab(region)
        mask = self._mask(frame, s["hsv_lower"], s["hsv_upper"])
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_area = float(s.get("min_blob_area", 300))
        for c in contours:
            area = cv2.contourArea(c)
            if area >= best_area:
                best_area = area
                best = c

        if best is None:
            return None

        M = cv2.moments(best)
        if M["m00"] == 0:
            return None
        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]

        box = self._region_box(region)
        return (int(box["left"] + cx), int(box["top"] + cy))

    # ---- 2) reel minigame ----------------------------------------------
    def read_reel(self) -> ReelReading:
        r = self.cfg["reel"]
        region = r["region"]
        frame = self.grab(region)
        box = self._region_box(region)
        left = box["left"]
        right = box["left"] + box["width"]

        target_x = self._centroid_x(frame, r["target_hsv_lower"],
                                    r["target_hsv_upper"], left)
        control_x = self._centroid_x(frame, r["control_hsv_lower"],
                                     r["control_hsv_upper"], left)
        return ReelReading(target_x, control_x, left, right)

    def _centroid_x(self, frame: np.ndarray, lower, upper,
                    left_offset: int) -> Optional[float]:
        mask = self._mask(frame, lower, upper)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        col_sum = mask.sum(axis=0).astype(np.float64)
        total = col_sum.sum()
        if total <= 0:
            return None
        xs = np.arange(col_sum.shape[0], dtype=np.float64)
        cx = (xs * col_sum).sum() / total
        return left_offset + cx

    # ---- 3) progress bar -----------------------------------------------
    def read_progress(self) -> Optional[float]:
        p = self.cfg["reel"].get("progress", {})
        if not p.get("enabled", False):
            return None
        frame = self.grab(p["region"])
        mask = self._mask(frame, p["hsv_lower"], p["hsv_upper"])
        filled = float((mask > 0).sum())
        total = float(mask.size)
        return filled / total if total else 0.0
