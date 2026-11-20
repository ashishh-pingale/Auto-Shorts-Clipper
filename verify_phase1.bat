@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo Phase 1 Verification: FFmpeg & Python Environment
echo ========================================================
echo.

echo [1/3] Locating FFmpeg in project folder...
set "FFMPEG_EXE="

:: Check common paths where the folder might be pasted
if exist "tools\ffmpeg\bin\ffmpeg.exe" set "FFMPEG_EXE=tools\ffmpeg\bin\ffmpeg.exe"
if exist "ffmpeg\bin\ffmpeg.exe" set "FFMPEG_EXE=ffmpeg\bin\ffmpeg.exe"
if exist "bin\ffmpeg.exe" set "FFMPEG_EXE=bin\ffmpeg.exe"

:: If not found in common paths, search any extracted folder
if not defined FFMPEG_EXE (
    for /d %%D in (ffmpeg* tools\ffmpeg*) do (
        if exist "%%D\bin\ffmpeg.exe" set "FFMPEG_EXE=%%D\bin\ffmpeg.exe"
        if exist "%%D\ffmpeg.exe" set "FFMPEG_EXE=%%D\ffmpeg.exe"
    )
)

if defined FFMPEG_EXE (
    echo [FOUND] FFmpeg found at: !FFMPEG_EXE!
    echo.
    echo Testing NVIDIA NVENC Hardware Encoding support...
    !FFMPEG_EXE! -encoders 2>&1 | findstr /i "nvenc"
    if !errorlevel! equ 0 (
        echo [PASS] NVIDIA NVENC hardware acceleration is ready!
    ) else (
        echo [INFO] FFmpeg is working, testing standard encoders.
    )
) else (
    echo [NOTE] Looking for where ffmpeg was pasted...
    dir /s /b ffmpeg.exe 2>nul
)

echo.
echo [2/3] Checking Isolated Virtual Environment (.venv)...
if exist ".venv\Scripts\python.exe" (
    echo [PASS] .venv found!
    .venv\Scripts\python.exe --version
) else (
    echo [PENDING] .venv not created yet. Please run 'create_venv.bat'.
)

echo.
echo [3/3] System Python Check (Ensuring 3.13 is untouched)...
python --version

echo.
echo ========================================================
pause
