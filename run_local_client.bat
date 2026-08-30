@echo off
setlocal
cd /d "%~dp0"

echo [VIUStudio] Starting local client...
python ui\gui.py

if errorlevel 1 (
    echo.
    echo [VIUStudio] Local client exited with an error.
    pause
)
