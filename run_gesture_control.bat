@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Live Inference Launcher
REM ============================================================
REM This script activates the virtual environment and runs the
REM real-time gesture recognition using your webcam.
REM ============================================================

echo.
echo #############################################################
echo #  Hand Gesture Vehicle Control System - Live Inference     #
echo #  YOLO11 Nano Model - Real-time Webcam Detection           #
echo #############################################################
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\
    echo Please run setup first or check the repository structure.
    pause
    exit /b 1
)

REM Check if trained model exists
if not exist "models\gesture_yolo11n_best.pt" (
    echo WARNING: Trained model not found at models\gesture_yolo11n_best.pt
    echo The system will use the base YOLO11n model (untrained for gestures).
    echo.
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Starting live gesture control...
echo Press 'q' or ESC in the camera window to quit.
echo Logging active gestures to logs\gesture_control_log.csv
echo.

REM Run the live inference script
python inference\live_gesture_control.py

echo.
echo Session ended.
pause