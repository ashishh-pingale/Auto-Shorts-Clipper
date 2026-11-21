@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Auto Shorts Clipper - Step 1: Installation and Setup
echo =====================================================================
echo    Auto Shorts Clipper - Step 1: Automated Installation Setup
echo =====================================================================
echo.

echo [1/5] Detecting compatible Python installation...
set "PY_CMD="

py -3.11 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.11"
    goto :PYTHON_FOUND
)

py -3.10 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.10"
    goto :PYTHON_FOUND
)

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

py --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto :PYTHON_FOUND
)

:PYTHON_FOUND
if not defined PY_CMD (
    echo [ERROR] No compatible Python installation found!
    echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Using Python: !PY_CMD!
!PY_CMD! --version
echo.

echo [2/5] Setting up isolated Python virtual environment (.venv)...
if not exist .venv\Scripts\python.exe (
    echo Creating .venv...
    !PY_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment in .venv
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Virtual environment already exists (.venv).
)
echo.

echo [3/5] Installing core dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install -r requirements.txt
if !errorlevel! neq 0 (
    echo [WARNING] Some dependencies had issues. Retrying essentials...
    .venv\Scripts\pip.exe install faster-whisper yt-dlp opencv-python gradio torch
)
echo.

echo [4/5] Checking for NVIDIA GPU acceleration...
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (
    echo [NVIDIA GPU DETECTED]
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo.
    echo Installing official NVIDIA CUDA 12 and cuDNN acceleration libraries...
    .venv\Scripts\pip.exe install nvidia-cublas-cu12 nvidia-cudnn-cu12
    echo [OK] CUDA 12 acceleration libraries installed in .venv.
) else (
    echo [INFO] No NVIDIA GPU detected or driver not found. Running in CPU mode.
)
echo.

echo [5/5] Checking FFmpeg installation...
where ffmpeg >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] FFmpeg found in system PATH.
) else (
    set "LOCAL_FFMPEG="
    for /d %%D in (ffmpeg* tools\ffmpeg*) do (
        if exist "%%D\bin\ffmpeg.exe" set "LOCAL_FFMPEG=%%D\bin\ffmpeg.exe"
        if exist "%%D\ffmpeg.exe" set "LOCAL_FFMPEG=%%D\ffmpeg.exe"
    )
    if defined LOCAL_FFMPEG (
        echo [OK] Portable FFmpeg detected at: !LOCAL_FFMPEG!
    ) else (
        echo [WARNING] FFmpeg was not detected in system PATH or local folder.
        echo Please ensure FFmpeg is installed or download from:
        echo https://www.gyan.dev/ffmpeg/builds/
    )
)

echo.
echo =====================================================================
echo    STEP 1 COMPLETE: Setup finished successfully!
echo    You can now run '2_test_gpu_nvenc.bat' to verify hardware,
echo    or launch the dashboard directly with '3_run_app.bat'.
echo =====================================================================
echo.
pause
