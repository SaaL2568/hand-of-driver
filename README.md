# Hand Gesture Vehicle Control System

**Final Year Capstone Project** — Two complementary gesture-control pipelines for real-time vehicle command:

| Pipeline | Technology | Control Type | Use Case |
|----------|------------|--------------|----------|
| **Part A — Static** | YOLO11n + HaGRID | 9 discrete gestures | Command triggers (start, stop, horn, panic) |
| **Part B — Dynamic** | MediaPipe Tasks API + Pygame Simulator | Continuous thumb steering + pedals | Analog driving (steer, throttle, brake) |

---

## 🎮 Part A: Static Gesture Commands (YOLO11)

Fine-tuned **Ultralytics YOLO11 nano** on HaGRID subset (9 classes).

| Class ID | Gesture | Vehicle Command | Description |
|----------|---------|----------------|-------------|
| `0` | **fist** | `START / GO` | Engine start / vehicle launch |
| `1` | **palm** | `STOP` | Standard vehicle stop |
| `2` | **like** | `ACCELERATE` | Increase speed |
| `3` | **dislike** | `BRAKE` | Decrease speed / apply brakes |
| `4` | **peace** | `LEFT TURN` | Steer left |
| `5` | **ok** | `RIGHT TURN` | Steer right |
| `6` | **call** | `HORN` | Sound vehicle horn |
| `7` | **stop** | `PANIC / EMERGENCY STOP` | Emergency override |
| `8` | **no_gesture** | `SAFE IDLE` | Safe default (no command) |

### Part A: Repository Structure
```
final-year/
├── dataset/                      # YOLO-format images & labels (train/val/test)
├── models/
│   └── gesture_yolo11n_best.pt   # Fine-tuned checkpoint (20 MB)
├── scripts/
│   └── prepare_dataset.py        # HaGRID downloader → YOLO converter
├── training/
│   └── train_gesture_model.py    # YOLO11 training (41 epochs, auto OOM fallback)
├── inference/
│   ├── live_gesture_control.py   # YOLO webcam inference + CSV logging
│   └── dynamic_mediapipe_test.py # Original MediaPipe thumb prototype
├── gestures.yaml                 # YOLO class config (nc=9)
├── yolo11n.pt                    # Base YOLO11n weights
└── weights/
    └── yolo26n.pt                # Alt weights
```

### Part A: Quick Start
```powershell
# 1. Activate venv
.\.venv\Scripts\Activate.ps1

# 2. Prepare dataset (downloads HaGRID from HuggingFace)
.\.venv\Scripts\python.exe scripts/prepare_dataset.py

# 3. Train model (GPU, 41 epochs, saves to models/gesture_yolo11n_best.pt)
.\.venv\Scripts\python.exe training/train_gesture_model.py

# 4. Run live YOLO inference (webcam → gesture → vehicle command + CSV log)
.\.venv\Scripts\python.exe inference/live_gesture_control.py
```
**Batch launchers**: `run.bat` (menu), `run_gesture_control.bat`, `run_training.bat`, `prepare_dataset.bat`

---

## 🕹️ Part B: Dynamic Thumb Control + 2D Simulator

Continuous analog control using **MediaPipe Hand Landmarker (Tasks API)** → UDP → **Pygame vehicle simulator**.

### Control Mapping
| Thumb Motion | Vehicle Output |
|--------------|----------------|
| Point **LEFT** | Steer left (−1.0 … 0) |
| Point **RIGHT** | Steer right (0 … +1.0) |
| Thumb **HIGH** (top of frame) | Throttle (0.0 → 1.0) |
| Thumb **LOW** (bottom of frame) | Brake (0.0 → 1.0) |
| Thumb **CENTER** | Coast / idle |
| Point **DOWN** + very low | **PANIC STOP** (throttle=0, brake=1, panic=true) |

### Part B: Repository Structure
```
final-year/simulator/
├── main.py                        # Pygame simulator (60 FPS, UDP receiver)
├── network.py                     # UDP JSON receiver + VehicleCommand protocol
├── gesture_client.py              # UDP sender library (Part A → Part B)
├── mediapipe_thumb_controller.py  # MediaPipe Tasks API thumb tracker (Part A sender)
├── hand_gesture_controller.py     # Legacy MediaPipe controller (mp.solutions.hands)
├── hand_landmarker.task           # MediaPipe model (7.8 MB)
├── physics.py                     # Bicycle model kinematics
├── world.py                       # City track, camera, rendering
├── car.py                         # Vehicle physics + rendering
├── hud.py                         # Telemetry dashboard (speed, steer, radar, panic)
├── config.py                      # All tunable parameters
├── mock_sender.py                 # Test scenarios (slalom, panic, circle, interactive)
├── test_simulator.py              # Unit tests
├── requirements.txt               # pygame, opencv, mediapipe>=1.0, numpy<2
├── run_integrated.bat             # Launches simulator + thumb controller
└── README.md                      # Simulator-specific docs
```

### Network Protocol (UDP JSON, port 5005)
```json
{
  "steeringAngle": -1.0 to 1.0,   // -1=full left, 0=center, +1=full right
  "throttle": 0.0 to 1.0,         // 0=idle, 1=max acceleration
  "brake": 0.0 to 1.0,            // 0=released, 1=full brake
  "panicStop": true/false,        // Emergency cutoff
  "timestamp": 1726053892.124     // Unix epoch (latency tracking)
}
```

### Part B: Quick Start
```powershell
cd simulator

# Option 1: One-click launcher (opens two windows)
run_integrated.bat

# Option 2: Manual (two terminals)
# Terminal 1 — Simulator
venv\Scripts\activate.bat
python main.py --width 1280 --height 720

# Terminal 2 — Thumb Controller (webcam)
venv\Scripts\activate.bat
python mediapipe_thumb_controller.py --model hand_landmarker.task --ip 127.0.0.1 --port 5005 --camera 0
```

**Simulator controls** (keyboard fallback):
| Key | Action |
|-----|--------|
| `W` / `↑` | Throttle |
| `S` / `↓` | Reverse |
| `Space` | Brake |
| `A` / `←` | Steer left |
| `D` / `→` | Steer right |
| `P` | Panic stop |
| `Tab` | Toggle NETWORK ↔ KEYBOARD mode |
| `R` | Reset car |
| `Esc` | Quit |

---

## 🔧 Environment

| Component | Version |
|-----------|---------|
| Python | 3.11.9 |
| PyTorch | 2.5.1 + CUDA 12.1 |
| Ultralytics | 8.4.138 |
| OpenCV | 5.0.0 |
| MediaPipe | 1.0.1 (Tasks API) |
| Pygame | 2.6.1 |

**Two virtual environments**:
- `final-year/.venv/` — YOLO training & inference (PyTorch CUDA)
- `final-year/simulator/venv/` — Pygame + MediaPipe (no CUDA needed)

---

## 🎯 Project Highlights (Novelty)

1. **Hybrid discrete + continuous control** — YOLO classifies *what* command (start/stop/horn); MediaPipe thumb tracks *how much* (steering angle, throttle depth).
2. **Safety arbitration** — Panic gestures override continuous control; dead-man idle on hand loss; confidence-gated commands.
3. **UDP decoupled architecture** — Vision (Part A) and physics (Part B) run in separate processes; testable via `mock_sender.py` without camera.
4. **Laptop-camera optimised** — Low detection thresholds (0.3), high-res capture (1280×720), visual zone overlays, aggressive smoothing.
5. **Full evaluation suite** — YOLO per-class mAP@50/50-95, simulator packet-rate/latency HUD, automated slalom/panic test scenarios.

---

## 📹 Demo Checklist

- [ ] YOLO model trained (`models/gesture_yolo11n_best.pt` exists)
- [ ] `live_gesture_control.py` runs, detects 9 gestures, logs CSV
- [ ] Simulator opens, shows city track + HUD
- [ ] Thumb controller opens webcam, shows zone overlays
- [ ] UDP packets flow: thumb movement → simulator steering/throttle/brake
- [ ] Panic gesture triggers red banner + emergency physics
- [ ] Mock sender slalom test passes (validates protocol independently)

---

## 📄 License
Academic capstone project. MediaPipe model subject to Google's [MediaPipe Terms](https://developers.google.com/mediapipe/terms). HaGRID dataset subject to [HuggingFace license](https://huggingface.co/datasets/ntsrigaud/hagrid-subset).