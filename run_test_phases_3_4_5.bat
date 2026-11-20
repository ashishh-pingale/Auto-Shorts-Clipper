@echo off
echo ========================================================
echo Running Auto Shorts Pipeline Test (Phases 3, 4, 5)
echo ========================================================
echo.

:: Run inside isolated .venv
.venv\Scripts\python.exe test_phases_3_4_5.py %*

echo.
pause
