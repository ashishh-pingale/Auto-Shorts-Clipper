@echo off
echo ========================================================
echo Stopping all active Auto Shorts Clipper background tasks...
echo ========================================================
echo.

taskkill /F /IM ffmpeg.exe 2>nul
taskkill /F /IM yt-dlp.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq Auto YouTube to Shorts Clipper*" 2>nul

echo.
echo All background processing stopped and RAM/GPU freed!
echo.
pause
