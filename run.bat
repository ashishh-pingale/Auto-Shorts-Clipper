@echo off
cd /d "%~dp0"
title AutoClipper Dashboard
echo ========================================================
echo Launching AutoClipper Web Dashboard
echo ========================================================
echo.

:: Automatically free space on C: drive from previous Gradio temp files
if exist "%LOCALAPPDATA%\Temp\gradio" (
    echo Freeing stray Gradio cache from C: drive...
    rd /s /q "%LOCALAPPDATA%\Temp\gradio" 2>nul
)

:: Lock ALL temporary and staging directories 100% to D: drive
set "TEMP=%~dp0temp"
set "TMP=%~dp0temp"
set "TMPDIR=%~dp0temp"
set "GRADIO_TEMP_DIR=%~dp0temp\gradio"
set "HF_HOME=%~dp0cache\huggingface"
set "TORCH_HOME=%~dp0cache\torch"

if not exist "%~dp0temp\gradio" mkdir "%~dp0temp\gradio"

echo Temp and Cache Location: %TEMP%
echo.

.venv\Scripts\python.exe app.py

echo.
pause
