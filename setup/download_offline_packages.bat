@echo off
REM Script to download all Python dependencies for offline installation
REM Run this on an internet-connected machine

setlocal enabledelayedexpansion

echo ===================================
echo Download Offline Packages
echo ===================================
echo.

REM Check Python
set PYTHON_CMD=
for %%p in (py python python3) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=%%p
        goto :python_found
    )
)

:python_found
if "!PYTHON_CMD!"=="" (
    echo [31m✗[0m Python not found!
    echo Please install Python first.
    pause
    exit /b 1
)

echo Using Python: !PYTHON_CMD!
echo.

REM Create offline packages directory
echo Creating offline_packages directory...
if exist "offline_packages" (
    echo Directory already exists, cleaning...
    rmdir /s /q "offline_packages"
)
mkdir "offline_packages"
echo.

REM Download packages for Windows (AMD64)
echo Downloading Python packages for Windows (AMD64)...
echo This may take a few minutes...
echo.

!PYTHON_CMD! -m pip download -r requirements.txt -d offline_packages --platform win_amd64 --python-version 3.11 --only-binary=:all:

if !errorlevel! neq 0 (
    echo.
    echo [33m⚠[0m Some packages may not be available as binary wheels.
    echo Attempting to download source distributions...
    !PYTHON_CMD! -m pip download -r requirements.txt -d offline_packages --python-version 3.11
)

echo.
echo Downloading pip, setuptools, and wheel...
!PYTHON_CMD! -m pip download pip setuptools wheel -d offline_packages

echo.
echo ===================================
echo Download Complete!
echo ===================================
echo.
echo All packages saved to: offline_packages\
echo.

REM Count files
for /f %%a in ('dir /b offline_packages ^| find /c /v ""') do set COUNT=%%a
echo Total files: !COUNT!

REM Calculate size
for /f "tokens=3" %%a in ('dir /s /-c offline_packages ^| findstr /C:"bytes"') do set SIZE=%%a
set /a SIZE_MB=!SIZE! / 1048576
echo Total size: ~!SIZE_MB! MB

echo.
echo Next steps:
echo 1. Transfer the entire project folder to the offline machine
echo 2. On the offline machine, run: setup_offline.bat
echo.
echo See OFFLINE-SETUP.md for detailed instructions.
echo.
pause
