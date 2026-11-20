@echo off
echo ========================================================
echo Installing NVIDIA CUDA 12 Libraries for GTX 1650
echo ========================================================
echo.
echo Installing official NVIDIA cuBLAS and cuDNN DLLs into .venv...
echo (Keeps your system clean, 100%% contained in .venv on D: drive)
echo.

.venv\Scripts\pip.exe install nvidia-cublas-cu12 nvidia-cudnn-cu12

echo.
echo ========================================================
echo NVIDIA CUDA Libraries Installed!
echo ========================================================
pause
