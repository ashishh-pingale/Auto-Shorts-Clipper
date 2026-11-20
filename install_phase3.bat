@echo off
echo ========================================================
echo Installing Phase 3: Transcription Engine (faster-whisper)
echo ========================================================
echo.
echo Installing into isolated .venv on D: drive...
echo All packages and caches are restricted to D: drive.
echo.

:: Ensure pip is up to date inside .venv
.venv\Scripts\python.exe -m pip install --upgrade pip

:: Install official faster-whisper and yt-dlp from PyPI
echo.
echo Installing faster-whisper and yt-dlp...
.venv\Scripts\pip.exe install faster-whisper yt-dlp

echo.
echo ========================================================
echo Phase 3 Dependencies Installed Successfully!
echo ========================================================
pause
