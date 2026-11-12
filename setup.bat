@echo off
REM ============================================================
REM Hand Gesture Vehicle Control - ONE-TIME SETUP
REM Creates .venv and installs everything. Needs internet.
REM Run this once on a new machine, then use run.bat.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

echo ============================================================
echo  Hand Gesture Vehicle Control - Setup
echo ============================================================
echo.

REM ---- 1. Find Python (3.11 preferred, the version the project was built on) ----
set "BASEPY="
py -3.11 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 set "BASEPY=py -3.11"
if not defined BASEPY (
    py -3.10 -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 set "BASEPY=py -3.10"
)
if not defined BASEPY (
    python -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 set "BASEPY=python"
)
if not defined BASEPY (
    echo ERROR: Python not found.
    echo Install Python 3.11 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
)
for /f "delims=" %%v in ('!BASEPY! -c "import sys; print(*sys.version_info[:2], sep='.')"') do set "PYVER=%%v"
echo [1/5] Using Python !PYVER! ^(!BASEPY!^)
if not "!PYVER!"=="3.11" if not "!PYVER!"=="3.10" (
    echo       WARNING: the project is tested on Python 3.11. Other versions may fail to install
    echo       mediapipe / torch. If setup fails, install Python 3.11 and run setup.bat again.
)

REM ---- 2. Create the virtual environment ----
if exist "%PY%" (
    "%PY%" -c "import sys" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [2/5] Existing .venv is broken ^(copied from another PC?^) - recreating it...
        rmdir /s /q .venv
    )
)
if not exist "%PY%" (
    echo [2/5] Creating virtual environment ^(.venv^)...
    !BASEPY! -m venv .venv
    if !errorlevel! neq 0 (
        echo ERROR: could not create .venv
        pause
        exit /b 1
    )
) else (
    echo [2/5] Virtual environment ^(.venv^) already exists.
)
"%PY%" -m pip install --upgrade pip --quiet

REM ---- 3. PyTorch: CUDA build only if an NVIDIA GPU is present ----
"%PY%" -c "import torch" >nul 2>&1
if !errorlevel! equ 0 (
    echo [3/5] PyTorch already installed.
) else (
    where nvidia-smi >nul 2>&1
    if !errorlevel! equ 0 (
        echo [3/5] NVIDIA GPU found - installing PyTorch with CUDA 12.1 ^(large download^)...
        "%PY%" -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
        if !errorlevel! neq 0 (
            echo       CUDA build failed - installing the CPU build instead.
            "%PY%" -m pip install torch==2.5.1 torchvision==0.20.1
        )
    ) else (
        echo [3/5] No NVIDIA GPU - installing the CPU build of PyTorch...
        "%PY%" -m pip install torch==2.5.1 torchvision==0.20.1
    )
    if !errorlevel! neq 0 (
        echo ERROR: PyTorch install failed.
        pause
        exit /b 1
    )
)

REM ---- 4. Project dependencies ----
echo [4/5] Installing project dependencies ^(requirements.txt^)...
"%PY%" -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo ERROR: dependency install failed - see the messages above.
    pause
    exit /b 1
)

REM ---- 5. Verify ----
echo [5/5] Checking the installation...
set "OK=1"
"%PY%" -c "import cv2, mediapipe, pygame, ultralytics, torch; print('      Packages OK - torch', torch.__version__, '| GPU:', torch.cuda.is_available())" 2>nul
if !errorlevel! neq 0 (
    echo       ERROR: a package failed to import.
    set "OK=0"
)
if not exist "hand_landmarker.task" (
    echo       ERROR: hand_landmarker.task is missing.
    set "OK=0"
)
if not exist "models\gesture_yolo11n_best.pt" (
    echo       ERROR: models\gesture_yolo11n_best.pt is missing.
    set "OK=0"
)

echo.
if "!OK!"=="1" (
    echo ============================================================
    echo  Setup complete. Start the project with run.bat
    echo ============================================================
) else (
    echo Setup finished with errors - fix the items above and run setup.bat again.
)
pause
exit /b 0
