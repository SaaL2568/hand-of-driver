@echo off
REM ============================================================
REM Hand Gesture Vehicle Control System - Dataset Preparation
REM ============================================================
REM Downloads HaGRID subset from HuggingFace and converts to
REM YOLO format (9 gesture classes, train/val/test splits).
REM ============================================================

echo.
echo #############################################################
echo #  Hand Gesture Vehicle Control System - Dataset Prep       #
echo #  Downloads HaGRID subset from HuggingFace                 #
echo #############################################################
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\
    pause
    exit /b 1
)

echo NOTE: Set HF_TOKEN environment variable for faster downloads:
echo   set HF_TOKEN=hf_your_token_here
echo.

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Starting dataset download and conversion...
echo This may take several minutes depending on connection.
echo Output: dataset\images\{train,val,test}\
echo         dataset\labels\{train,val,test}\
echo.

python scripts\prepare_dataset.py

echo.
echo Dataset preparation complete.
pause