# Hand Gesture Vehicle Control System

Final-year project: drive a simulated car with hand gestures from a webcam. MediaPipe hand tracking gives continuous steering, throttle and brake. A fine-tuned YOLO11-nano model adds discrete commands (emergency stop, gear, horn). Everything streams over UDP to a Pygame simulator.

## Quick Start (Windows)

Requirements: Windows 10/11, **Python 3.11** ([python.org](https://www.python.org/downloads/), tick *Add python.exe to PATH*), a webcam. An NVIDIA GPU is optional (YOLO runs faster with one).

1. **`setup.bat`**: one-time install. It creates `.venv`, installs PyTorch (the CUDA build if an NVIDIA GPU is found, otherwise CPU) and `requirements.txt`, then checks everything. Needs internet.
2. **`run.bat`**: menu to start the project. Works offline after setup.

| `run.bat` option | What it does |
|---|---|
| 1 | **Full system**: gesture controller (webcam) + simulator |
| 2 | Full system, forcing a fresh calibration |
| 3 | Simulator only, keyboard driving |
| 4 | Simulator + scripted test driver (slalom / panic / circle / interactive) |
| 5 | Standalone YOLO gesture demo (does not drive the simulator) |
| 6 | Train the YOLO model (downloads the HaGRID dataset if missing) |

> Moving to another PC: copy or clone the repo **without** the `.venv` folder and run `setup.bat` there. A copied `.venv` will not work; `setup.bat` detects one and rebuilds it.

## Controls

**Driving (MediaPipe):** hold a thumbs-up. Tilt the thumb to steer; raise or lower the hand for throttle or brake. Both work at the same time. A new user name triggers a 20-second calibration first.

**Commands (YOLO + MediaPipe must agree over several frames):**

| Gesture | Command |
|---|---|
| Open palm / `stop` | Emergency stop (while held) |
| Peace | Toggle gear D / R |
| Call sign (pinky out) | Horn (while held) |

**Camera window keys:** `Q`/`Esc` quit, `C` recalibrate, `S` skip calibration, `P` save a camera + simulator screenshot pair. Closing either window closes both.

**Simulator keyboard:** WASD/arrows drive, `S` reverse, `Space` brake, `P` panic, `TAB` switch keyboard/network, `R` reset, `H` help, `Esc` quit.

## Command Line (optional)

```powershell
.\.venv\Scripts\python.exe simulator\mediapipe_thumb_controller.py --user yourname
```

Useful flags: `--calibrate`, `--two-hands`, `--camera N`, `--no-yolo`, `--no-simulator`. Each run writes `logs/gesture_session_<date>_<time>.csv`.

Simulator tests: `cd simulator` then `..\.venv\Scripts\python.exe -m unittest test_simulator`.

## Repository Layout

```text
setup.bat / run.bat              # one-time install / launcher menu
simulator/
  mediapipe_thumb_controller.py  # MAIN ENTRY: MediaPipe + YOLO controller (starts the simulator)
  gesture_commands.py            # YOLO worker + command fusion / voting
  calibration.py                 # per-user calibration profiles
  main.py                        # Pygame simulator (UDP receiver); see simulator/README.md
models/gesture_yolo11n_best.pt   # trained YOLO11n gesture model
hand_landmarker.task             # MediaPipe hand model
inference/live_gesture_control.py  # standalone YOLO demo
scripts/prepare_dataset.py       # HaGRID download -> YOLO format
training/train_gesture_model.py  # YOLO11 training (41 epochs, imgsz 640)
gestures.yaml                    # dataset paths + 9 class names
```

YOLO classes: `fist, palm, like, dislike, peace, ok, call, stop, no_gesture`.

## Troubleshooting

- **First start is slow (20–30 s):** normal; the models load in the background.
- **Webcam won't open:** close other apps using it, check Windows camera privacy settings, or try `--camera 1`.
- **Gear / horn do nothing:** the camera window's top-right panel must say `YOLO`, not `YOLO off`. Re-run `setup.bat`.
- **Setup fails installing mediapipe/torch:** use Python 3.11.
- **Car doesn't respond:** the simulator HUD should read *GESTURE CONNECTED*; press `TAB` if it is in keyboard mode.

## Licenses

Academic project. The [HaGRID subset](https://huggingface.co/datasets/ntsrigaud/hagrid-subset) is subject to its dataset license; the MediaPipe model to Google's [MediaPipe Terms](https://developers.google.com/mediapipe/terms).
