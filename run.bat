@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Master Launcher
REM ============================================================
REM Main menu for YOLO training AND MediaPipe+Simulator integration
REM ============================================================

REM Resolve Python Executable
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"
if exist "simulator\venv\Scripts\python.exe" set "PYTHON_EXE=simulator\venv\Scripts\python.exe"

if "%PYTHON_EXE%"=="" (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PYTHON_EXE=python"
    ) else (
        set "PYTHON_EXE=python"
    )
)

:MENU
cls
echo.
echo #############################################################
echo #  HAND GESTURE VEHICLE CONTROL - MASTER MENU               #
echo #  Part A: YOLO11 Static Gestures (9 classes)              #
echo #  Part B: MediaPipe Dynamic Thumb + 2D Simulator          #
echo #############################################################
echo.
echo === PART A: YOLO11 STATIC GESTURE PIPELINE ===
echo [1] Prepare Dataset (Download HaGRID from HuggingFace)
echo [2] Train Model (Fine-tune YOLO11n on 9 gestures)
echo [3] Run YOLO Live Inference (Webcam -^> 9 gesture commands + CSV log)
echo.
echo === PART B: MEDIAPIPE DYNAMIC THUMB + SIMULATOR ===
echo [4] Launch Simulator + Thumb Controller (Integrated - 2 windows)
echo [5] Launch Simulator Only (Part B - for keyboard/mock testing)
echo [6] Launch Thumb Controller Only (Part A - webcam -^> UDP)
echo [7] Run Mock Sender Tests (Slalom / Panic / Circle / Interactive)
echo.
echo [0] Exit
echo.
set /p CHOICE="Enter choice [0-7]: "

if "%CHOICE%"=="1" goto PREPARE
if "%CHOICE%"=="2" goto TRAIN
if "%CHOICE%"=="3" goto INFERENCE_YOLO
if "%CHOICE%"=="4" goto INTEGRATED
if "%CHOICE%"=="5" goto SIM_ONLY
if "%CHOICE%"=="6" goto THUMB_ONLY
if "%CHOICE%"=="7" goto MOCK_TEST
if "%CHOICE%"=="0" goto EXIT

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto MENU

:PREPARE
"%PYTHON_EXE%" scripts/prepare_dataset.py
pause
goto MENU

:TRAIN
"%PYTHON_EXE%" training/train_gesture_model.py
pause
goto MENU

:INFERENCE_YOLO
"%PYTHON_EXE%" inference/live_gesture_control.py
pause
goto MENU

:INTEGRATED
cd simulator
call run_integrated.bat
cd ..
goto MENU

:SIM_ONLY
cd simulator
start "Simulator Part B" cmd /k ""..\.venv\Scripts\python.exe" main.py --width 1280 --height 720"
cd ..
goto MENU

:THUMB_ONLY
cd simulator
start "Thumb Controller Part A" cmd /k ""..\.venv\Scripts\python.exe" mediapipe_thumb_controller.py --model hand_landmarker.task --ip 127.0.0.1 --port 5005 --camera 0 --no-simulator"
cd ..
goto MENU

:MOCK_TEST
cd simulator
echo.
echo Mock Sender Scenarios:
echo [1] Slalom (continuous steering)
echo [2] Panic Stop (accel + emergency brake)
echo [3] Circle (constant steer + throttle)
echo [4] Interactive (keyboard WASD)
echo.
set /p MOCK="Choose scenario [1-4]: "
if "%MOCK%"=="1" "..\.venv\Scripts\python.exe" mock_sender.py --scenario slalom --rate 30
if "%MOCK%"=="2" "..\.venv\Scripts\python.exe" mock_sender.py --scenario panic --rate 30
if "%MOCK%"=="3" "..\.venv\Scripts\python.exe" mock_sender.py --scenario circle --rate 30
if "%MOCK%"=="4" "..\.venv\Scripts\python.exe" mock_sender.py --scenario interactive --rate 30
cd ..
pause
goto MENU

:EXIT
echo Goodbye!
timeout /t 1 >nul
exit /b 0