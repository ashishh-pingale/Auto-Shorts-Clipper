@echo off
echo ========================================================
echo Checking System Environment for Auto Shorts Clipper
echo ========================================================
echo.
echo [1/5] Checking Python Versions...
python --version > env_report.txt 2>&1
echo --- Python Launcher versions --- >> env_report.txt
py --list >> env_report.txt 2>&1

echo [2/5] Checking Git...
echo --- Git --- >> env_report.txt
git --version >> env_report.txt 2>&1

echo [3/5] Checking Node.js...
echo --- Node.js --- >> env_report.txt
node --version >> env_report.txt 2>&1

echo [4/5] Checking FFmpeg & NVENC...
echo --- FFmpeg --- >> env_report.txt
ffmpeg -version >> env_report.txt 2>&1

echo [5/5] Checking NVIDIA GPU...
echo --- NVIDIA-SMI --- >> env_report.txt
nvidia-smi >> env_report.txt 2>&1

echo.
echo ========================================================
echo Environment check complete! Saved to env_report.txt
echo ========================================================
pause
