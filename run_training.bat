@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Model Training
REM ============================================================
REM Trains YOLO11n on the HaGRID gesture dataset (9 classes).
REM Requires dataset to be prepared first (run prepare_dataset.bat).
REM ============================================================

echo.
echo #############################################################
echo #  Hand Gesture Vehicle Control System - Model Training     #
echo #  YOLO11 Nano - 9 Gesture Classes                          #
echo #############################################################
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\
    pause
    exit /b 1
)

if not exist "dataset\images\train" (
    echo WARNING: Dataset not found. Run prepare_dataset.bat first.
    echo.
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Starting model training (41 epochs, batch size 16->8 fallback)...
echo Results will be saved to runs\detect\gestureModelV1\
echo Best model copied to models\gesture_yolo11n_best.pt
echo.

python training\train_gesture_model.py

echo.
echo Training complete.
pause