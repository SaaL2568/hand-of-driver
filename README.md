# Hand Gesture Vehicle Control System

Final-year project for driving a simulated vehicle with hand gestures from a webcam. One controller fuses MediaPipe hand tracking (continuous steering, throttle and brake) with a fine-tuned YOLO11-nano model (discrete commands: emergency stop, gear, horn) and streams everything over UDP to a Pygame vehicle simulator.

## Current Status

| Component | Status | Entry point |
|---|---|---|
| YOLO11 training | Implemented | `training/train_gesture_model.py` |
| HaGRID dataset preparation | Implemented | `scripts/prepare_dataset.py` |
| Live YOLO webcam inference | Implemented | `inference/live_gesture_control.py` |
| **Integrated gesture controller (MediaPipe + YOLO)** | **Implemented - main entry point** | `simulator/mediapipe_thumb_controller.py` |
| Pygame simulator and UDP receiver | Implemented | `simulator/main.py` |
| First MediaPipe prototype (one channel at a time) | Superseded by the integrated controller | `inference/dynamic_mediapipe_test.py` |

The easiest way to run everything is `run_all.bat` (see [Unified Launcher](#unified-launcher-recommended)).

## Features

- Fine-tunes an Ultralytics YOLO11 nano model on nine hand-gesture classes.
- Reads gesture commands from a webcam in real time.
- Displays the detected gesture, confidence, FPS, and mapped vehicle action.
- Logs the active gesture once per second to `logs/gesture_control_log.csv`.
- Downloads and converts the selected HaGRID subset into YOLO format.

## Gesture Mapping

| Class ID | Gesture | Standalone YOLO app label | Integrated controller |
|---:|---|---|---|
| 0 | `fist` | START / GO | - |
| 1 | `palm` | STOP | EMERGENCY STOP (while held) |
| 2 | `like` | ACCELERATE | Driving pose (MediaPipe control) |
| 3 | `dislike` | BRAKE | - |
| 4 | `peace` | LEFT TURN | Toggle gear D / R |
| 5 | `ok` | RIGHT TURN | - |
| 6 | `call` | HORN | HORN (while held) |
| 7 | `stop` | PANIC / EMERGENCY STOP | EMERGENCY STOP (while held) |
| 8 | `no_gesture` | SAFE IDLE | - |

In the integrated controller a command fires only when YOLO's label **and** MediaPipe's finger pattern agree over several frames. Driving comes from MediaPipe alone: **thumb tilt = steering, hand height = throttle / brake** (both at once). New users get a 20-second calibration on first run.

## Requirements

- Windows 10 or 11.
- Python 3.10 or 3.11 recommended.
- A working webcam for live inference.
- Internet access for Python packages, the base YOLO11 weights, and the HaGRID dataset.
- Optional NVIDIA GPU with a compatible CUDA/PyTorch installation for faster training. CPU training is possible but considerably slower.
- Approximately 20 GB or more of free storage for the downloaded dataset, depending on the dataset split and cache.

## Installation

Open PowerShell in the repository root, the directory containing `gestures.yaml`.

### 1. Create and activate the virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current user, run PowerShell as your normal user and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again. The scripts can also be run without activation by using `.venv\Scripts\python.exe`.

### 2. Install Python dependencies

Install PyTorch first (CUDA 12.1 build for NVIDIA GPUs; leave out `--index-url` for the CPU build), then the pinned project requirements:

```powershell
python -m pip install --upgrade pip
python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r requirements.txt
```

`run_all.bat` does all of this automatically.

### 3. Check the installation

```powershell
python -c "import cv2, mediapipe, pandas, PIL, ultralytics; print('Dependencies OK')"
```

## Quick Start: Live Inference

Live inference requires a trained checkpoint at `models/gesture_yolo11n_best.pt`.

```powershell
.\.venv\Scripts\Activate.ps1
python inference\live_gesture_control.py
```

The webcam window opens on camera device `0`. Press `q` or `Esc` to exit. The script creates the `logs` directory automatically and writes detections to:

```text
logs/gesture_control_log.csv
```

The confidence threshold is currently `0.5`. The camera must be available to the Python process; close other applications that may be using it if capture fails.

## Training Workflow

Run these steps from the repository root.

### 1. Prepare the dataset

The preparation script downloads `ntsrigaud/hagrid-subset` from Hugging Face, keeps the nine classes above, and writes YOLO images and labels into `dataset/`.

Unauthenticated downloads:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\prepare_dataset.py
```

For higher Hugging Face download limits, create a Hugging Face access token and set it only in the current PowerShell session:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
python scripts\prepare_dataset.py
```

Expected output directories:

```text
dataset/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

### 2. Train and validate YOLO11

```powershell
python training\train_gesture_model.py
```

The script uses `yolo11n.pt`, trains for 41 epochs at image size 640, validates on the validation split, and retries with batch size 8 if CUDA or GPU memory fails at batch size 16.

Generated files include:

```text
runs/detect/gestureModelV1/weights/best.pt
models/gesture_yolo11n_best.pt
```

The copied file in `models/` is the checkpoint used by live inference and the integrated controller. It is committed to the repository (21 MB), so a fresh clone works without retraining; other training outputs and weights are ignored by Git.

### 3. Run the trained model

```powershell
python inference\live_gesture_control.py
```

## Simulator Quick Start

The simulator is a Pygame application in `simulator/` that receives UDP control packets and renders a 2D vehicle simulation. Use the project `.venv` for everything (it has YOLO/PyTorch installed).

### 1. Run the full system (end-to-end)
```powershell
.\.venv\Scripts\python.exe simulator\mediapipe_thumb_controller.py --user yourname
```
The controller opens the simulator by itself; closing either window closes both. Keys in the camera window: `Q`/`Esc` quit, `C` recalibrate, `P` save a camera + simulator screenshot pair. Use `--no-simulator` to run the controller alone, `--two-hands` to steer with one hand and gesture with the other.

### 2. Run the simulator alone (keyboard fallback mode)
```powershell
cd simulator
..\.venv\Scripts\python.exe main.py
```
- WASD/Arrow keys to drive, `S` reverse, `Space` brake, `P` panic
- Press `TAB` to toggle between keyboard and network input modes

### 3. Test the simulator with the mock sender
```powershell
cd simulator
..\.venv\Scripts\python.exe mock_sender.py --scenario slalom
```

Note: `inference\live_gesture_control.py` is the standalone YOLO demo; it only displays and logs gestures and does **not** drive the simulator.

See `simulator/README.md` for full documentation, network protocol, and keybindings.

## Unified Launcher (Recommended)

A single batch file handles **complete setup + run**:

```powershell
run_all.bat
```

This will:
1. Create `.venv` if missing
2. Install PyTorch (CUDA build if possible) and `requirements.txt`
3. Present a menu: **[1] Full System (controller + simulator)**, YOLO demo, Simulator only, Mock tests, Train, or Prepare Dataset

## Legacy Batch Files (Removed)

The old individual batch files (`prepare_dataset.bat`, `run.bat`, `run_training.bat`, `run_gesture_control.bat`, `run_mediapipe.bat`, `simulator/run_integrated.bat`) have been consolidated into `run_all.bat`.

## Repository Layout

```text
hand-of-driver/
├── gestures.yaml                   # YOLO dataset paths and nine class names
├── hand_landmarker.task             # MediaPipe model asset for the prototype
├── inference/
│   ├── live_gesture_control.py      # Supported YOLO webcam inference
│   └── dynamic_mediapipe_test.py    # Experimental MediaPipe prototype
├── scripts/
│   └── prepare_dataset.py           # Hugging Face download and YOLO conversion
├── training/
│   └── train_gesture_model.py       # YOLO11 training and validation
├── models/
│   └── gesture_yolo11n_best.pt      # Trained YOLO11n gesture model (committed)
├── simulator/
│   ├── mediapipe_thumb_controller.py  # MAIN ENTRY: integrated MediaPipe + YOLO controller
│   ├── gesture_commands.py          # YOLO worker + command fusion / voting
│   ├── calibration.py               # Per-user calibration profiles
│   ├── main.py                      # Pygame simulator (UDP receiver)
│   └── ...                          # physics, HUD, network, tests (see simulator/README.md)
├── report_screenshots/              # Report / appendix figures
├── requirements.txt                 # Pinned project dependencies
├── run_all.bat                      # Unified setup + run launcher
└── README.md
```

## MediaPipe Prototype (first iteration)

`inference/dynamic_mediapipe_test.py` is the first thumb-direction prototype. It classifies the thumb as left/right/up/down and drives only one channel at a time, which is why it was replaced by `simulator/mediapipe_thumb_controller.py`. It is kept for reference.

## Troubleshooting

**`Trained model not found`**

Run dataset preparation and training first. Live inference only loads `models/gesture_yolo11n_best.pt` and does not train automatically.

**`Dataset not found` or missing images**

Run `python scripts\prepare_dataset.py` from the repository root. Check that the internet connection is available and that `HF_TOKEN` is set if Hugging Face rate limits the request.

**Webcam cannot be opened**

Close applications using the camera, check Windows camera permissions, and verify that camera device `0` is correct.

**CUDA out of memory**

The training script retries with batch size 8. If that still fails, run with a CPU-only PyTorch installation or reduce the batch size in `training/train_gesture_model.py`.

**Gear / horn gestures do nothing**

The camera window's top-right panel must show a `YOLO` label (not `YOLO off`). YOLO needs the project `.venv`; the controller restarts itself in `.venv` automatically if it was started with another Python. The panel also shows MediaPipe's finger pattern and the vote counts, and each session writes `logs/gesture_session_<date>_<time>.csv`.

**Simulator errors**

Run the simulator with the project environment from the `simulator` folder:
```powershell
cd simulator
..\.venv\Scripts\python.exe main.py
```

## Data and Model Licenses

This is an academic capstone project. The HaGRID subset is distributed through [Hugging Face](https://huggingface.co/datasets/ntsrigaud/hagrid-subset) and is subject to its dataset license. The MediaPipe model is subject to Google's [MediaPipe Terms](https://developers.google.com/mediapipe/terms).
