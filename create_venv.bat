@echo off
echo ========================================================
echo Creating Python 3.11 Virtual Environment on D: Drive
echo ========================================================
echo.

echo Checking Python 3.11 via Windows Launcher...
py -3.11 --version
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11 not detected via 'py -3.11'.
    pause
    exit /b 1
)

echo.
echo Creating isolated virtual environment in .venv...
py -3.11 -m venv .venv

echo.
echo Verifying isolated environment...
.venv\Scripts\python.exe --version
if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo SUCCESS! Python 3.11 virtual environment ready in .venv
    echo System Python 3.13 remains completely untouched.
    echo ========================================================
) else (
    echo [ERROR] Failed to verify .venv.
)
pause
