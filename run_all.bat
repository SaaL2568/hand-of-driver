@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Unified Launcher
REM Sets up everything and runs the project
REM ============================================================

setlocal enabledelayedexpansion

REM Get script directory (handles running from anywhere)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ============================================================
echo Hand Gesture Vehicle Control - Unified Setup & Run
echo ============================================================
echo.

REM ---- 1. CHECK PYTHON ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.10+ from https://python.org and ensure "Add to PATH" is checked.
    pause
    exit /b 1
)

REM ---- 2. CREATE MAIN VENV ----
if not exist ".venv" (
    echo [1/4] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Failed to create .venv
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment (.venv) already exists.
)

REM ---- 3. INSTALL MAIN DEPENDENCIES ----
echo [2/4] Installing main project dependencies...
".venv\Scripts\pip.exe" install --upgrade pip >nul 2>&1
".venv\Scripts\pip.exe" install ultralytics opencv-python pandas pillow huggingface-hub mediapipe
if %errorlevel% neq 0 (
    echo Failed to install main dependencies
    pause
    exit /b 1
)

REM ---- 4. INSTALL SIMULATOR DEPENDENCIES ----
echo [3/4] Installing simulator dependencies...
if exist "simulator\requirements.txt" (
    ".venv\Scripts\pip.exe" install -r simulator\requirements.txt
    if %errorlevel% neq 0 (
        echo Failed to install simulator dependencies
        pause
        exit /b 1
    )
) else (
    echo WARNING: simulator\requirements.txt not found, skipping
)

echo [4/4] Setup complete!
echo.
echo ============================================================
echo Choose what to run:
echo ============================================================
echo.
echo [1] Train YOLO Model (requires dataset - runs prepare first if needed)
echo [2] Run YOLO Live Inference (webcam -> gesture commands)
echo [3] Run Simulator Only (keyboard control, no webcam needed)
echo [4] Run Full Integration: Simulator + YOLO Live (2 windows)
echo [5] Run Simulator + Mock Sender Test (slalom/panic/circle)
echo [6] Prepare Dataset Only (download HaGRID from HuggingFace)
echo [0] Exit
echo.
set /p CHOICE="Enter choice [0-6]: "

if "%CHOICE%"=="1" goto TRAIN
if "%CHOICE%"=="2" goto INFERENCE
if "%CHOICE%"=="3" goto SIM_ONLY
if "%CHOICE%"=="4" goto INTEGRATED
if "%CHOICE%"=="5" goto MOCK_TEST
if "%CHOICE%"=="6" goto PREPARE
if "%CHOICE%"=="0" goto EXIT

echo Invalid choice.
pause
goto EXIT

:PREPARE
echo.
echo Preparing dataset (downloads HaGRID from HuggingFace)...
".venv\Scripts\python.exe" scripts\prepare_dataset.py
pause
goto EXIT

:TRAIN
echo.
echo Checking for dataset...
if not exist "dataset\images\train" (
    echo Dataset not found. Preparing first...
    ".venv\Scripts\python.exe" scripts\prepare_dataset.py
    if %errorlevel% neq 0 (
        echo Dataset preparation failed.
        pause
        goto EXIT
    )
)
echo Training YOLO11n model...
".venv\Scripts\python.exe" training\train_gesture_model.py
pause
goto EXIT

:INFERENCE
echo.
echo Running YOLO Live Inference...
echo Press 'q' or ESC in the webcam window to quit.
".venv\Scripts\python.exe" inference\live_gesture_control.py
pause
goto EXIT

:SIM_ONLY
echo.
echo Starting Simulator (keyboard fallback mode)...
echo Controls: WASD/Arrows=drive, SPACE=brake, P=panic, TAB=toggle network/keyboard, R=reset, ESC=quit
cd simulator
".venv\Scripts\python.exe" main.py --width 1280 --height 720
cd ..
pause
goto EXIT

:INTEGRATED
echo.
echo Starting FULL INTEGRATION (2 windows will open):
echo   Window 1: Simulator (receives UDP on port 5005)
echo   Window 2: YOLO Live Inference (sends gestures via UDP)
echo.
echo Make sure webcam is available.
echo Press 'q' or ESC in YOLO window to quit both.
echo.
start "Simulator" cmd /k "cd /d "%SCRIPT_DIR%simulator" && "..\.venv\Scripts\python.exe" main.py --width 1280 --height 720"
timeout /t 2 >nul
".venv\Scripts\python.exe" inference\live_gesture_control.py
pause
goto EXIT

:MOCK_TEST
echo.
echo Mock Sender Test Scenarios:
echo [1] Slalom (continuous steering)
echo [2] Panic Stop (accel + emergency brake)
echo [3] Circle (constant steer + throttle)
echo [4] Interactive (keyboard WASD -> UDP)
echo.
set /p MOCK="Choose scenario [1-4]: "
cd simulator
if "%MOCK%"=="1" "..\.venv\Scripts\python.exe" mock_sender.py --scenario slalom --rate 30
if "%MOCK%"=="2" "..\.venv\Scripts\python.exe" mock_sender.py --scenario panic --rate 30
if "%MOCK%"=="3" "..\.venv\Scripts\python.exe" mock_sender.py --scenario circle --rate 30
if "%MOCK%"=="4" "..\.venv\Scripts\python.exe" mock_sender.py --scenario interactive --rate 30
cd ..
pause
goto EXIT

:EXIT
echo.
echo Done.