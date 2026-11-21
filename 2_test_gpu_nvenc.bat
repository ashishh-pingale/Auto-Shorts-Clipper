@echo off
cd /d "%~dp0"
title Auto Shorts Clipper - Step 2: GPU and NVENC Verification
echo =====================================================================
echo    Auto Shorts Clipper - Step 2: Hardware Diagnostic Test
echo =====================================================================
echo.

if not exist .venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found!
    echo Please run '1_install_setup.bat' first.
    echo.
    pause
    exit /b 1
)

echo Running GPU, CUDA, and NVENC hardware encoding tests...
echo.
.venv\Scripts\python.exe test_nvenc.py

echo.
echo =====================================================================
echo    Verification complete! If NVENC is confirmed, run '3_run_app.bat'.
echo =====================================================================
echo.
pause
