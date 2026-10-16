@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Unified Launcher
REM Sets up everything and runs the project
REM ============================================================

setlocal enabledelayedexpansion

REM Get script directory (handles running from anywhere)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "PY=%SCRIPT_DIR%.venv\Scripts\python.exe"

echo ============================================================
echo Hand Gesture Vehicle Control - Unified Setup ^& Run
echo ============================================================
echo.

REM ---- 1. CHECK PYTHON ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.11 from https://python.org and ensure "Add to PATH" is checked.
    pause
    exit /b 1
)

REM ---- 2. CREATE MAIN VENV ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment ^(.venv^)...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo Failed to create .venv
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment ^(.venv^) already exists.
)

REM ---- 3. INSTALL DEPENDENCIES ----
REM PyTorch first: the CUDA 12.1 build if no torch is installed yet (falls back to CPU build).
"%PY%" -c "import torch" >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/3] Installing PyTorch ^(CUDA 12.1 build^)...
    "%PY%" -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
    if !errorlevel! neq 0 (
        echo CUDA build unavailable - installing the CPU build instead.
        "%PY%" -m pip install torch==2.5.1 torchvision==0.20.1
    )
) else (
    echo [2/3] PyTorch already installed.
)
echo [3/3] Installing project dependencies ^(requirements.txt^)...
"%PY%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

echo Setup complete!
echo.
echo ============================================================
echo Choose what to run:
echo ============================================================
echo.
echo [1] Run Full System: Gesture Controller ^(MediaPipe + YOLO^) + Simulator
echo [2] Run YOLO Live Inference only ^(standalone demo, logs to CSV^)
echo [3] Run Simulator Only ^(keyboard control, no webcam needed^)
echo [4] Run Simulator + Mock Sender Test ^(slalom/panic/circle^)
echo [5] Train YOLO Model ^(prepares the dataset first if needed^)
echo [6] Prepare Dataset Only ^(download HaGRID from HuggingFace^)
echo [0] Exit
echo.
set /p CHOICE="Enter choice [0-6]: "

if "%CHOICE%"=="1" goto FULL
if "%CHOICE%"=="2" goto INFERENCE
if "%CHOICE%"=="3" goto SIM_ONLY
if "%CHOICE%"=="4" goto MOCK_TEST
if "%CHOICE%"=="5" goto TRAIN
if "%CHOICE%"=="6" goto PREPARE
if "%CHOICE%"=="0" goto EXIT

echo Invalid choice.
pause
goto EXIT

:FULL
echo.
set /p GUSER="Your name for the calibration profile (Enter = default): "
if "%GUSER%"=="" set "GUSER=default"
echo.
echo Starting the gesture controller - it opens the simulator automatically.
echo   New user: a 20-second calibration runs first ^(follow the on-screen steps^).
echo   Drive: thumbs-up; tilt thumb = steer, raise/lower hand = throttle/brake.
echo   Commands: open palm = emergency stop, peace = gear D/R, call = horn.
echo   Keys in the camera window: Q/ESC quit, C recalibrate, P screenshot.
"%PY%" simulator\mediapipe_thumb_controller.py --user "%GUSER%"
pause
goto EXIT

:INFERENCE
echo.
echo Running YOLO Live Inference ^(standalone - does not drive the simulator^)...
echo Press 'q' or ESC in the webcam window to quit.
"%PY%" inference\live_gesture_control.py
pause
goto EXIT

:SIM_ONLY
echo.
echo Starting Simulator ^(keyboard fallback mode^)...
echo Controls: WASD/Arrows=drive, S=reverse, SPACE=brake, P=panic, TAB=network/keyboard, R=reset, ESC=quit
pushd simulator
"%PY%" main.py --width 1280 --height 720
popd
pause
goto EXIT

:MOCK_TEST
echo.
echo Mock Sender Test Scenarios:
echo [1] Slalom ^(continuous steering^)
echo [2] Panic Stop ^(accel + emergency brake^)
echo [3] Circle ^(constant steer + throttle^)
echo [4] Interactive ^(keyboard WASD to UDP^)
echo.
set /p MOCK="Choose scenario [1-4]: "
pushd simulator
start "Simulator" "%PY%" main.py --width 1280 --height 720
timeout /t 2 >nul
if "%MOCK%"=="1" "%PY%" mock_sender.py --scenario slalom --rate 30
if "%MOCK%"=="2" "%PY%" mock_sender.py --scenario panic --rate 30
if "%MOCK%"=="3" "%PY%" mock_sender.py --scenario circle --rate 30
if "%MOCK%"=="4" "%PY%" mock_sender.py --scenario interactive --rate 30
popd
pause
goto EXIT

:TRAIN
echo.
echo Checking for dataset...
if not exist "dataset\images\train" (
    echo Dataset not found. Preparing first...
    "%PY%" scripts\prepare_dataset.py
    if !errorlevel! neq 0 (
        echo Dataset preparation failed.
        pause
        goto EXIT
    )
)
echo Training YOLO11n model...
"%PY%" training\train_gesture_model.py
pause
goto EXIT

:PREPARE
echo.
echo Preparing dataset ^(downloads HaGRID from HuggingFace^)...
"%PY%" scripts\prepare_dataset.py
pause
goto EXIT

:EXIT
echo.
echo Done.
