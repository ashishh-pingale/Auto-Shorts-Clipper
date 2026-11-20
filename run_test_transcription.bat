@echo off
echo ========================================================
echo Running Phase 3 Transcription Engine Test
echo ========================================================
echo.

:: Run test inside .venv
.venv\Scripts\python.exe test_transcription.py

echo.
pause
