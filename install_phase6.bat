@echo off
echo ========================================================
echo Installing Phase 6: Vision & Face Tracking (MediaPipe & OpenCV)
echo ========================================================
echo.

:: Install mediapipe and opencv-python into isolated .venv on D: drive
.venv\Scripts\pip.exe install opencv-python mediapipe

echo.
echo ========================================================
echo Phase 6 Vision Dependencies Installed Successfully!
echo ========================================================
pause
