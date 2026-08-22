"""
calibrate.py
------------
Interactive helper to tune the macro to YOUR screen/resolution. Nothing here
is required to run the macro, but a 2-minute calibration makes detection far
more reliable.

Usage:
    python src/calibrate.py            # full guided calibration
    python src/calibrate.py region     # only pick the screen regions
    python src/calibrate.py color      # only sample HSV colors

How region picking works:
    A screenshot opens. Drag a box with the mouse, press ENTER to accept
    (or 'c' to cancel). The fractional region is printed AND written back
    into config.json.

How color picking works:
    A screenshot opens. Click on the color you want to detect (the fish
    marker, the white shake prompt, etc). The suggested HSV lower/upper
    range is printed so you can paste it into config.json.
"""

from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np
from mss import mss

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import resolve_config_path  # noqa: E402

CFG_PATH = resolve_config_path()


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg: dict) -> None:
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"  -> saved to {CFG_PATH}")


def grab_full(cfg: dict):
    with mss() as sct:
        mon = sct.monitors[int(cfg.get("monitor", 1))]
        raw = np.asarray(sct.grab(mon))
        img = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
    return img, mon


def _fit(img, max_w=1280):
    h, w = img.shape[:2]
    if w <= max_w:
        return img, 1.0
    scale = max_w / w
    return cv2.resize(img, (int(w * scale), int(h * scale))), scale


def pick_region(cfg: dict) -> None:
    names = ["shake.region", "reel.region", "reel.progress.region"]
    img, mon = grab_full(cfg)
    disp, scale = _fit(img)

    for dotted in names:
        print(f"\nDraw a box for [{dotted}] then press ENTER (ESC to skip).")
        r = cv2.selectROI(f"Select: {dotted}", disp, showCrosshair=True)
        cv2.destroyAllWindows()
        x, y, w, h = r
        if w == 0 or h == 0:
            print("  skipped.")
            continue
        # convert display px -> full px -> fraction of monitor
        region = {
            "x": round((x / scale) / mon["width"], 4),
            "y": round((y / scale) / mon["height"], 4),
            "w": round((w / scale) / mon["width"], 4),
            "h": round((h / scale) / mon["height"], 4),
        }
        print(f"  {dotted} = {region}")
        _assign(cfg, dotted, region)
        _show_region_saved(dotted, region)
    save_cfg(cfg)


def _show_region_saved(name: str, region: dict) -> None:
    """Brief popup confirming the region was saved (useful when no console)."""
    msg = np.zeros((90, 420, 3), dtype=np.uint8)
    cv2.putText(msg, f"Saved: {name}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(msg, f"x={region['x']}  y={region['y']}  w={region['w']}  h={region['h']}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.imshow("Saved", msg)
    cv2.waitKey(900)
    cv2.destroyAllWindows()


def _sample_one(disp, hsv, title: str):
    """Show the screenshot, let the user click sample pixels for ONE color,
    press Q to finish. Returns (lower, upper) HSV lists or None if skipped."""
    samples = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            samples.append(hsv[y, x].tolist())
            # Visual feedback on the image itself (matters when there is no console)
            cv2.circle(disp, (x, y), 3, (0, 255, 0), -1)
            print(f"  sampled HSV={hsv[y, x].tolist()} (total {len(samples)})")

    win = f"{title} — click the color, press Q when done (ESC to skip)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    skipped = False
    while True:
        cv2.imshow(win, disp)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"):
            break
        if key == 27:  # ESC
            skipped = True
            break
    cv2.destroyAllWindows()

    if skipped or not samples:
        return None
    arr = np.array(samples)
    lo = np.clip(arr.min(axis=0) - [10, 60, 60], [0, 0, 0], [180, 255, 255])
    hi = np.clip(arr.max(axis=0) + [10, 60, 60], [0, 0, 0], [180, 255, 255])
    # Show a small summary window so the user can confirm the result (useful
    # when running as a windowless .app with no console).
    _show_summary(title, len(samples), lo, hi)
    return lo.astype(int).tolist(), hi.astype(int).tolist()


def _show_summary(title: str, n: int, lo, hi) -> None:
    """Brief popup that shows the sampled range so the user knows it worked."""
    msg = np.zeros((110, 420, 3), dtype=np.uint8)
    cv2.putText(msg, title[:38], (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(msg, f"Samples: {n}", (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(msg, f"lo={lo.tolist()}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(msg, f"hi={hi.tolist()}", (210, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1, cv2.LINE_AA)
    cv2.imshow("Saved", msg)
    cv2.waitKey(1200)
    cv2.destroyAllWindows()


def pick_color(cfg: dict) -> None:
    """Guided color calibration. For each named target the user clicks sample
    pixels; the resulting HSV range is written straight into config.json."""
    # (dotted lower key, dotted upper key, friendly prompt)
    targets = [
        ("shake.hsv_lower", "shake.hsv_upper",
         "SHAKE prompt (the white 'Shake!' text/button)"),
        ("reel.target_hsv_lower", "reel.target_hsv_upper",
         "REEL fish/target marker"),
        ("reel.control_hsv_lower", "reel.control_hsv_upper",
         "REEL your control marker"),
    ]
    img, _ = grab_full(cfg)
    disp, _ = _fit(img)
    hsv = cv2.cvtColor(disp, cv2.COLOR_BGR2HSV)

    for lo_key, hi_key, prompt in targets:
        print(f"\n[{prompt}] click sample pixels, then press Q (ESC to skip).")
        result = _sample_one(disp, hsv, prompt)
        if result is None:
            print("  skipped.")
            continue
        lo, hi = result
        _assign(cfg, lo_key, lo)
        _assign(cfg, hi_key, hi)
        print(f"  {lo_key} = {lo}")
        print(f"  {hi_key} = {hi}")
    save_cfg(cfg)


def _assign(cfg: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def main() -> None:
    cfg = load_cfg()
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "region"):
        pick_region(cfg)
    if mode in ("all", "color"):
        cfg = load_cfg()   # reload in case regions were saved
        pick_color(cfg)
    print("\nCalibration done.")
    # Final popup so the user knows it's safe to close the app.
    msg = np.zeros((80, 360, 3), dtype=np.uint8)
    cv2.putText(msg, "Calibration done!", (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (120, 255, 120), 2, cv2.LINE_AA)
    cv2.putText(msg, "You can close this window.", (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.imshow("Done", msg)
    cv2.waitKey(1500)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
