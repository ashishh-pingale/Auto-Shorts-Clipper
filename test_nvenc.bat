@echo off
echo ========================================================
echo Testing NVIDIA GTX 1650 NVENC Hardware Acceleration
echo ========================================================
echo.

.venv\Scripts\python.exe test_nvenc.py

echo.
pause
