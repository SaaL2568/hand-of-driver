# Hand Gesture Vehicle-Control System (YOLO11)

Fine-tuned **Ultralytics YOLO11 (nano)** model trained on the HaGRID hand gesture dataset subset to recognize 9 hand gestures for real-time vehicle command control.

---

## 🎮 Command Mapping Table

| Class ID | Gesture | Vehicle Command | Function Description |
| :---: | :--- | :--- | :--- |
| `0` | **fist** | `START / GO` | Engine start / vehicle launch |
| `1` | **palm** | `STOP` | Standard vehicle stop |
| `2` | **like** | `ACCELERATE` | Increase speed |
| `3` | **dislike** | `BRAKE` | Decrease speed / apply brakes |
| `4` | **peace** | `LEFT TURN` | Steer left |
| `5` | **ok** | `RIGHT TURN` | Steer right |
| `6` | **call** | `HORN` | Sound vehicle horn |
| `7` | **stop** | `PANIC / EMERGENCY STOP` | Emergency override stop (reserved) |
| `8` | **no_gesture** | `SAFE IDLE` | Safe default state (no command) |

---

## 📁 Repository Structure

```text
final-year/
├── dataset/                    # Converted YOLO image & label splits
│   ├── images/                 # train, val, test splits
│   └── labels/                 # YOLO txt labels per split
├── models/
│   └── gesture_yolo11n_best.pt # Exported fine-tuned best model checkpoint
├── scripts/
│   └── prepare_dataset.py      # Dataset downloader and converter
├── training/
│   └── train_gesture_model.py  # Model training and validation script
├── inference/
│   └── live_gesture_control.py # Real-time webcam inference window
├── gestures.yaml               # YOLO class configuration file
└── README.md                   # Documentation and usage guide
```

---

## 🚀 Usage Instructions

### 1. Environment Setup
Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Dataset Preparation
Download, filter, and structure the 9 gesture classes into YOLO format:
```powershell
.\.venv\Scripts\python.exe scripts/prepare_dataset.py
```

### 3. Model Training & Validation
Train the YOLO11 model on local GPU:
```powershell
.\.venv\Scripts\python.exe training/train_gesture_model.py
```

### 4. Real-time Live Webcam Control
Run live inference using your webcam to test gesture recognition and vehicle command output:
```powershell
.\.venv\Scripts\python.exe inference/live_gesture_control.py
```
*(Press `q` or `ESC` to quit the live camera window.)*
