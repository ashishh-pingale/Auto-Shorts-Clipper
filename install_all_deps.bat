@echo off
echo ========================================================
echo Installing Vision & UI Dependencies (OpenCV, MediaPipe, Gradio)
echo ========================================================
echo.

:: Install into isolated .venv on D: drive
.venv\Scripts\pip.exe install opencv-python mediapipe gradio

echo.
echo ========================================================
echo All Dependencies Installed Successfully!
echo ========================================================
pause
