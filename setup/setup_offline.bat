@echo off
REM Offline setup script for Windows
REM Installs Python dependencies from local offline_packages folder

setlocal enabledelayedexpansion

echo ===================================
echo Ship Plate Line Heating
echo Offline Installation (Windows)
echo ===================================
echo.

REM Check if offline_packages exists
if not exist "offline_packages" (
    echo [31m✗[0m offline_packages folder not found!
    echo.
    echo This script requires the offline_packages folder with pre-downloaded Python packages.
    echo Please follow the instructions in OFFLINE-SETUP.md
    echo.
    pause
    exit /b 1
)

REM Check Python version
echo Checking Python version...
set PYTHON_CMD=
for %%p in (py python python3) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%v in ('%%p --version 2^>^&1') do (
            set VERSION=%%v
            for /f "tokens=1,2 delims=." %%a in ("!VERSION!") do (
                set MAJOR=%%a
                set MINOR=%%b
                if !MAJOR! equ 3 (
                    if !MINOR! geq 11 (
                        if !MINOR! leq 12 (
                            set PYTHON_CMD=%%p
                            echo [32m✓[0m Found Python !VERSION! at %%p
                            goto :python_found
                        )
                    )
                )
            )
        )
    )
)

:python_found
if "!PYTHON_CMD!"=="" (
    echo [31m✗[0m Python 3.11 or 3.12 not found!
    echo.
    echo Python must be pre-installed on this machine.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo.

REM Check Visual Studio Build Tools
echo Checking C++ compiler...
set CXX_FOUND=0

where cl.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [32m✓[0m Found Visual Studio C++ compiler
    set CXX_FOUND=1
) else (
    for %%v in (2022 2019 2017) do (
        if exist "C:\Program Files\Microsoft Visual Studio\%%v" (
            echo [32m✓[0m Found Visual Studio %%v installation
            set CXX_FOUND=1
            goto :cxx_found
        )
        if exist "C:\Program Files (x86)\Microsoft Visual Studio\%%v" (
            echo [32m✓[0m Found Visual Studio %%v installation
            set CXX_FOUND=1
            goto :cxx_found
        )
    )
)

:cxx_found
if !CXX_FOUND! equ 0 (
    echo [31m✗[0m Visual Studio Build Tools not found!
    echo.
    echo C++ compiler must be pre-installed on this machine.
    echo Install Visual Studio Build Tools with "Desktop development with C++" workload
    pause
    exit /b 1
)
echo.

REM Create virtual environment
echo Creating virtual environment...
set VENV_DIR=.venv_lineheating

if exist "!VENV_DIR!" (
    echo [33m⚠[0m Virtual environment already exists. Removing old one...
    rmdir /s /q "!VENV_DIR!"
)

!PYTHON_CMD! -m venv "!VENV_DIR!"
if !errorlevel! neq 0 (
    echo [31m✗[0m Failed to create virtual environment!
    pause
    exit /b 1
)
echo [32m✓[0m Virtual environment created: !VENV_DIR!
echo.

REM Activate virtual environment
echo Activating virtual environment...
call "!VENV_DIR!\Scripts\activate.bat"
if !errorlevel! neq 0 (
    echo [31m✗[0m Failed to activate virtual environment!
    pause
    exit /b 1
)
echo.

REM Upgrade pip from offline packages
echo Upgrading pip...
python -m pip install --no-index --find-links=offline_packages --upgrade pip setuptools wheel
if !errorlevel! neq 0 (
    echo [33m⚠[0m Warning: Could not upgrade pip (continuing anyway)
)
echo.

REM Install dependencies from offline packages
echo Installing dependencies from offline_packages...
python -m pip install --no-index --find-links=offline_packages -r requirements.txt
if !errorlevel! neq 0 (
    echo [31m✗[0m Failed to install dependencies!
    echo.
    echo Make sure all required packages are in offline_packages folder.
    pause
    exit /b 1
)
echo [32m✓[0m Dependencies installed successfully
echo.

REM Verify installation
echo Verifying installation...
python -c "import numpy, scipy, matplotlib, gmsh, pybind11, cmake" 2>nul
if !errorlevel! neq 0 (
    echo [33m⚠[0m Warning: Some packages may not have been imported correctly
) else (
    echo [32m✓[0m All core packages verified
)
echo.

echo ===================================
echo Setup Complete!
echo ===================================
echo.
echo Virtual environment: !VENV_DIR!
echo.
echo Next steps:
echo 1. Copy run_config.example.json to run_config.json
echo 2. Edit run_config.json with your parameters
echo 3. Run: python scripts\run_anywhere.py --config run_config.json
echo.
echo To activate the environment manually:
echo   !VENV_DIR!\Scripts\activate.bat
echo.
pause
