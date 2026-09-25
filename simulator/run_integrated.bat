@echo off
REM ============================================================
REM Gesture Vehicle Control - Integrated Launcher
REM Launches Simulator (Part B) + Thumb Controller (Part A)
REM ============================================================

echo.
echo #############################################################
echo #  Gesture Vehicle Control - Full Stack Launcher           #
echo #  Part B: Pygame Simulator (UDP Receiver)                 #
echo #  Part A: MediaPipe Thumb Controller (UDP Sender)         #
echo #############################################################
echo.

REM Resolve Python executable across virtual environments
set "PYTHON_EXE="
REM Prefer the project .venv (has ultralytics + CUDA torch for YOLO gesture commands)
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"

if "%PYTHON_EXE%"=="" (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=python"
    ) else (
        echo ERROR: Python executable not found.
        pause
        exit /b 1
    )
)

echo Using Python: %PYTHON_EXE%

REM Check model file
set "MODEL_PATH=hand_landmarker.task"
if not exist "%MODEL_PATH%" (
    if exist "..\hand_landmarker.task" (
        set "MODEL_PATH=..\hand_landmarker.task"
    ) else (
        echo ERROR: hand_landmarker.task not found.
        pause
        exit /b 1
    )
)

echo Starting camera + simulator together (closed loop)...
"%PYTHON_EXE%" mediapipe_thumb_controller.py --model "%MODEL_PATH%" --ip 127.0.0.1 --port 5005 --camera 0 --width 1280 --height 720

echo.
echo #############################################################
echo #  Session ended.                                           #
echo #  - Simulator window: vehicle physics + HUD                #
echo #  - Thumb Controller window: webcam + telemetry overlay    #
echo #  Controls: thumb LEFT/RIGHT = steer, thumb UP/DOWN = gas/brake #
echo #  Q/ESC in camera or closing the game exits both.        #
echo #############################################################
echo.
pause