@echo off
REM ============================================================
REM Hand Gesture Vehicle Control - RUN
REM Run setup.bat once first. Works offline after setup.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

"%PY%" -c "import ultralytics, mediapipe, pygame" >nul 2>&1
if !errorlevel! neq 0 (
    echo The project is not set up on this machine yet.
    echo Run setup.bat first ^(one time, needs internet^).
    pause
    exit /b 1
)

:MENU
cls
echo ============================================================
echo  Hand Gesture Vehicle Control
echo ============================================================
echo.
echo  [1] Full System - gesture controller ^(webcam^) + simulator   ^<-- demo
echo  [2] Full System, force re-calibration
echo  [3] Simulator only ^(keyboard driving, no webcam^)
echo  [4] Simulator + scripted test driver ^(no webcam^)
echo  [5] YOLO gesture recognition demo ^(webcam, no simulator^)
echo  [6] Train the YOLO model ^(downloads dataset if missing, slow^)
echo  [0] Exit
echo.
set "CHOICE="
set /p CHOICE="Choose [0-6]: "

if "%CHOICE%"=="1" goto FULL
if "%CHOICE%"=="2" goto FULL
if "%CHOICE%"=="3" goto SIM_ONLY
if "%CHOICE%"=="4" goto MOCK_TEST
if "%CHOICE%"=="5" goto INFERENCE
if "%CHOICE%"=="6" goto TRAIN
if "%CHOICE%"=="0" exit /b 0
goto MENU

:FULL
echo.
set "GUSER="
set /p GUSER="Name for the calibration profile (Enter = default): "
if "%GUSER%"=="" set "GUSER=default"
set "EXTRA="
if "%CHOICE%"=="2" set "EXTRA=--calibrate"
echo.
echo Starting... the first start can take 20-30 seconds while the models load.
echo   New name: a 20-second calibration runs first ^(follow the on-screen steps^).
echo   Drive  : thumbs-up; tilt thumb = steer, raise/lower hand = throttle/brake.
echo   Command: open palm = emergency stop, peace = gear D/R, call sign = horn.
echo   Keys in the camera window: Q/ESC quit, C recalibrate, S skip calibration, P screenshot.
echo   Closing either window closes both.
"%PY%" simulator\mediapipe_thumb_controller.py --user "%GUSER%" %EXTRA%
pause
goto MENU

:SIM_ONLY
echo.
echo Controls: WASD/Arrows drive, S reverse, SPACE brake, P panic, H help, R reset, ESC quit
pushd simulator
"%PY%" main.py --keyboard-only
popd
goto MENU

:MOCK_TEST
echo.
echo  [1] Slalom   [2] Panic stop   [3] Circle   [4] Interactive ^(WASD in this window^)
set "MOCK="
set /p MOCK="Choose scenario [1-4]: "
set "SCEN=slalom"
if "%MOCK%"=="2" set "SCEN=panic"
if "%MOCK%"=="3" set "SCEN=circle"
if "%MOCK%"=="4" set "SCEN=interactive"
pushd simulator
start "Simulator" "%PY%" main.py
timeout /t 3 >nul
echo Sending %SCEN% packets - press Ctrl+C here to stop, then close the simulator window.
"%PY%" mock_sender.py --scenario %SCEN% --rate 30
popd
pause
goto MENU

:INFERENCE
echo.
echo YOLO-only demo: shows and logs gestures, does NOT drive the simulator. Press Q/ESC to quit.
"%PY%" inference\live_gesture_control.py
pause
goto MENU

:TRAIN
echo.
if not exist "dataset\images\train" (
    echo Dataset not found - downloading HaGRID subset first ^(needs internet, ~GBs^)...
    "%PY%" scripts\prepare_dataset.py
    if !errorlevel! neq 0 (
        echo Dataset preparation failed.
        pause
        goto MENU
    )
)
"%PY%" training\train_gesture_model.py
pause
goto MENU
