# Hand Gesture Vehicle Control System

Final-year project for recognising hand gestures from a webcam and mapping them to vehicle commands. The currently implemented and runnable pipeline is the YOLO11 static-gesture pipeline. A MediaPipe prototype is also included, but the simulator integration is not present in this checkout.

## Current Status

| Component | Status | Entry point |
|---|---|---|
| YOLO11 training | Implemented | `training/train_gesture_model.py` |
| HaGRID dataset preparation | Implemented | `scripts/prepare_dataset.py` |
| Live YOLO webcam inference | Implemented | `inference/live_gesture_control.py` |
| MediaPipe thumb prototype | Experimental and currently incomplete | `inference/dynamic_mediapipe_test.py` |
| Pygame simulator and UDP client | Implemented | `simulator/main.py` |

The batch files `run.bat`, `run_mediapipe.bat`, and the simulator options in `run.bat` now work with the included simulator files in `simulator/`. Use the YOLO commands in this README for the supported workflow, or the simulator commands for end-to-end testing.

## Features

- Fine-tunes an Ultralytics YOLO11 nano model on nine hand-gesture classes.
- Reads gesture commands from a webcam in real time.
- Displays the detected gesture, confidence, FPS, and mapped vehicle action.
- Logs the active gesture once per second to `logs/gesture_control_log.csv`.
- Downloads and converts the selected HaGRID subset into YOLO format.

## Gesture Mapping

| Class ID | Gesture | Vehicle command |
|---:|---|---|
| 0 | `fist` | START / GO |
| 1 | `palm` | STOP |
| 2 | `like` | ACCELERATE |
| 3 | `dislike` | BRAKE |
| 4 | `peace` | LEFT TURN |
| 5 | `ok` | RIGHT TURN |
| 6 | `call` | HORN |
| 7 | `stop` | PANIC / EMERGENCY STOP |
| 8 | `no_gesture` | SAFE IDLE |

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

There is no committed `requirements.txt` in the current repository, so install the packages directly:

```powershell
python -m pip install --upgrade pip
python -m pip install ultralytics opencv-python pandas huggingface-hub Pillow mediapipe
```

`ultralytics` installs PyTorch as a dependency. For NVIDIA GPU training, install the PyTorch build appropriate for the installed CUDA driver from the official PyTorch selector before installing or upgrading `ultralytics`.

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

The copied file in `models/` is the checkpoint used by live inference. Training outputs and model weights are ignored by Git, so keep a backup if the trained model must be shared.

### 3. Run the trained model

```powershell
python inference\live_gesture_control.py
```

## Simulator Quick Start

The simulator is a standalone Pygame application in the `simulator/` directory that receives UDP gesture commands and renders a 2D vehicle simulation.

### 1. Install simulator dependencies
```powershell
cd simulator
pip install -r requirements.txt
```

### 2. Run the simulator (keyboard fallback mode)
```powershell
python main.py
```
- Uses WASD/Arrow keys for control
- Press `TAB` to toggle between keyboard and network input modes

### 3. Run with live gesture control (end-to-end)
**Terminal 1** - Start simulator:
```powershell
cd simulator
python main.py
```

**Terminal 2** - Start YOLO gesture inference:
```powershell
cd ..
.\.venv\Scripts\Activate.ps1
python inference\live_gesture_control.py
```

**Terminal 3** (optional) - Test with mock sender:
```powershell
cd simulator
python mock_sender.py --scenario slalom
```

See `simulator/README.md` for full documentation, network protocol, and keybindings.

## Unified Launcher (Recommended)

A single batch file handles **complete setup + run**:

```powershell
run_all.bat
```

This will:
1. Create `.venv` if missing
2. Install all Python dependencies (main + simulator)
3. Present a menu to run: Train, Inference, Simulator, Full Integration, Mock Tests, or Prepare Dataset

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
├── simulator/                       # Pygame simulator with UDP client (see simulator/README.md)
├── prepare_dataset.bat
├── run.bat
├── run_gesture_control.bat
├── run_mediapipe.bat                # References unavailable simulator code
├── run_training.bat
└── README.md
```

## MediaPipe Prototype

`inference/dynamic_mediapipe_test.py` contains an experimental thumb-direction prototype using `hand_landmarker.task`. It displays direction, action, and intensity, and includes UDP telemetry hooks for the simulator. The simulator is now included in `simulator/` with a UDP client (`gesture_client.py`) that can receive commands from this prototype.

## Troubleshooting

**`Trained model not found`**

Run dataset preparation and training first. Live inference only loads `models/gesture_yolo11n_best.pt` and does not train automatically.

**`Dataset not found` or missing images**

Run `python scripts\prepare_dataset.py` from the repository root. Check that the internet connection is available and that `HF_TOKEN` is set if Hugging Face rate limits the request.

**Webcam cannot be opened**

Close applications using the camera, check Windows camera permissions, and verify that camera device `0` is correct.

**CUDA out of memory**

The training script retries with batch size 8. If that still fails, run with a CPU-only PyTorch installation or reduce the batch size in `training/train_gesture_model.py`.

**Simulator launcher errors**

Ensure you have installed simulator dependencies:
```powershell
cd simulator
pip install -r requirements.txt
```
Then run from the simulator directory:
```powershell
python main.py
```

## Data and Model Licenses

This is an academic capstone project. The HaGRID subset is distributed through [Hugging Face](https://huggingface.co/datasets/ntsrigaud/hagrid-subset) and is subject to its dataset license. The MediaPipe model is subject to Google's [MediaPipe Terms](https://developers.google.com/mediapipe/terms).
