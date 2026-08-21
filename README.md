# 🎣 Fisch AI Macro

A hands-free **autopilot** for the Roblox game **Fisch**. It watches your screen with
a lightweight local vision engine and plays the whole fishing loop for you — cast,
shake, and reel — while an optional **Hugging Face cloud AI** grades each catch and
auto-favorites the good ones. All so you rack up as many good catches as possible
while AFK.

- **Hybrid "AI", built for weak PCs.**
  - **Local + featherweight:** the real-time cast/shake/reel control is plain
    [OpenCV](https://opencv.org/) color detection — ~1% CPU, **no GPU**, runs on
    any potato PC. (It reacts in milliseconds; a cloud call here would be far too
    slow, so this part stays local by design.)
  - **Cloud when it counts:** deciding *"is this a good catch?"* runs on the
    **[Hugging Face Inference API](https://huggingface.co/inference-api)** once per
    fish — so the heavy model runs on their servers, **not your PC**. Optional, and
    free-tier friendly.
- **Cross-platform.** Works on **Windows** and **macOS**. (Linux is intentionally
  not supported, per request.)
- **Fully automatic.** One hotkey starts it; it does the rest and prints a live
  catches-per-hour counter plus how many "good" catches it kept.

> ⚠️ **Please read before using.** Automating a Roblox game can violate Roblox's
> Terms of Service and may result in your account being banned. This tool only
> reads your screen and moves your real mouse (it does **not** inject code, read
> game memory, or modify Roblox). Use it at your own risk, ideally on an account
> you're willing to lose. You are responsible for how you use it.

---

## How it works

A tiny state machine drives everything:

```
CAST → WAIT FOR BITE → SHAKE (click the white prompt) → REEL (keep marker on fish)
     → [Hugging Face grades the catch → favorite if good] → repeat
```

1. **Cast** – clicks/holds at your cast point to throw the rod.
2. **Shake** – the vision engine finds the bright "Shake!" prompt anywhere in a
   region and clicks it until the bite is secured.
3. **Reel** – it tracks the moving **fish/target** and your **control marker**,
   then holds/releases left-click to keep them aligned until the catch lands.
4. **Grade (optional, cloud)** – it screenshots the caught-fish popup and asks the
   Hugging Face model whether it's a good/rare catch; if so, it presses your
   favorite key to keep it.

Everything the vision engine looks for (screen regions + colors) lives in
`config.json`, so you can tune it to any resolution or UI theme without editing code.

---

## Quick start

### Option A — standalone app / exe (no Python needed to run)

You can package everything into a **double-clickable `.exe` (Windows)** or **`.app`
(macOS)** so it runs on any machine without installing Python.

**Build it once:**

| OS | Do this |
|----|---------|
| Windows | Double-click **`build.bat`** |
| macOS | Run **`./build.command`** (or double-click it) |

When it finishes you'll find your programs in the **`dist/`** folder:

```
dist/FischMacro.exe      dist/FischCalibrate.exe        (Windows)
dist/FischMacro.app      dist/FischCalibrate.app        (macOS)
```

- **`FischMacro`** — the autopilot. Double-click it, focus Roblox, press **F8**.
- **`FischCalibrate`** — run once to tune regions/colors to your screen.
- A `config.json` (and `fischmacro.log` on macOS) is created next to the app on
  first launch — edit `config.json` any time to fine-tune.

> macOS note: the first time, **right-click the app → Open** to get past Gatekeeper,
> and grant **Accessibility** + **Screen Recording** to the app in
> *System Settings → Privacy & Security*. Because the `.app` has no console window,
> status is written to `fischmacro.log` next to the app.
> The `.exe`/`.app` must be built **on the OS you'll run it on** (build the `.exe`
> on Windows, the `.app` on macOS — PyInstaller does not cross-compile).

### Option B — run from source

### Windows
1. Install [Python 3.10+](https://www.python.org/downloads/) (check **"Add to PATH"**).
2. **Double-click `run.bat`.** First run auto-installs everything into a local `.venv`.
3. Open Roblox → Fisch, then in the macro window follow the hotkeys.

### macOS
1. Install Python 3.10+ (`brew install python` or python.org).
2. Grant your Terminal app permission under **System Settings → Privacy & Security**:
   - **Accessibility** (to move the mouse)
   - **Screen Recording** (to see the screen)
3. In Terminal: `./run.command` (or double-click it).
4. Open Roblox → Fisch and use the hotkeys.

### Hotkeys
| Key | Action |
|-----|--------|
| **F8** | Start / stop the autopilot |
| **F9** | Quit the program |

*(Change these in `config.json` under `"hotkeys"`.)*

---

## Calibration (2 minutes — highly recommended)

Default settings are a starting guess. To make detection reliable on **your**
screen, run the calibrator once:

```bash
# Windows
.venv\Scripts\activate && python src\calibrate.py

# macOS
source .venv/bin/activate && python src/calibrate.py
```

- **Regions:** a screenshot opens — drag a box around (a) the area where the
  "Shake!" prompt appears, (b) the reeling bar, (c) optionally the progress bar.
  Press **Enter** to save each. Regions are written straight into `config.json`.
- **Colors:** click on the fish marker, the control marker, and the white shake
  prompt. The tool prints suggested HSV ranges to paste into `config.json`.

---

## Tuning cheatsheet (`config.json`)

| Setting | What it does |
|--------|--------------|
| `cast.click_x_frac` / `click_y_frac` | Where the rod is cast (0..1 of screen). |
| `shake.hsv_lower/upper` | Color of the "Shake!" prompt (default = white). |
| `shake.min_blob_area` | Ignore blobs smaller than this (kills noise). |
| `reel.target_hsv_*` | Color of the fish/target marker. |
| `reel.control_hsv_*` | Color of your player control marker. |
| `reel.deadzone_frac` | How centered is "close enough" before adjusting. |
| `reel.hold_bias` | ≥0.5 = hold when centered (counteracts gravity); <0.5 = release. |
| `reel.progress.enabled` | Turn on to end reeling when a green progress bar fills. |
| `timings.*` | All the delays/timeouts, in seconds. |

**Reeling too far right?** Lower `hold_bias`. **Too far left?** Raise it.
**Jittery?** Increase `deadzone_frac` a little.

---

## Project layout

```
config.json              # all tunable settings (regions, colors, timings, hotkeys)
requirements.txt         # dependencies
fischmacro.spec          # PyInstaller build recipe (exe / app)
build.bat                # Windows: build standalone .exe files
build.command            # macOS: build standalone .app bundles
run.bat                  # Windows one-click launcher (run from source)
run.command              # macOS one-click launcher (run from source)
src/
  macro.py               # state machine + entry point (run this)
  vision.py              # local CV "AI": shake/reel/progress detection
  input_controller.py    # cross-platform mouse control (Windows/macOS)
  calibrate.py           # interactive region + color calibration tool
  paths.py               # config/log path resolution (source & frozen builds)
```

---

## Troubleshooting

- **Clicks don't register in Roblox (Windows):** run the macro window "as
  Administrator" — some setups require it for input to reach the game.
- **Nothing happens on macOS:** you almost certainly need to grant
  Accessibility **and** Screen Recording permissions, then fully restart Terminal.
- **It clicks the wrong spot / never finds the prompt:** run `calibrate.py` and
  re-pick the regions/colors for your resolution.
- **Play windowed (not fullscreen)** and keep the fishing UI unobstructed for
  the most reliable detection.
