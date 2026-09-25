@echo off
REM ============================================================
REM Hand Gesture Vehicle Control - MediaPipe Hand Landmarker
REM ============================================================

echo.
echo #############################################################
echo #  MediaPipe Hand Landmarker - Dynamic Thumb Control        #
echo #  Direction: LEFT/RIGHT/UP/DOWN  |  Intensity: 0-100%     #
echo #############################################################
echo.

set "PYTHON_EXE="
REM Prefer the project .venv (has ultralytics + CUDA torch for YOLO gesture commands)
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"

set "MODEL_PATH=hand_landmarker.task"
if not exist "%MODEL_PATH%" (
    if exist "..\hand_landmarker.task" (
        set "MODEL_PATH=..\hand_landmarker.task"
    )
)

echo Using Python: %PYTHON_EXE%
echo Starting MediaPipe dynamic hand control...
echo Press 'q' or ESC to quit camera window.
echo.

"%PYTHON_EXE%" mediapipe_thumb_controller.py --model "%MODEL_PATH%" --ip 127.0.0.1 --port 5005 --camera 0

echo.
echo Session ended.
pause