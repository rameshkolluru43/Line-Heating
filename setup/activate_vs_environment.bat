@echo off
REM Helper script to launch command prompt with Visual Studio environment
REM Use this if setup.bat fails to find Visual Studio Build Tools

setlocal enabledelayedexpansion

echo ===================================
echo Visual Studio Environment Setup
echo ===================================
echo.

REM Try to find vcvars64.bat in common locations
set VCVARS_PATH=

REM Check VS 2022
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    set VCVARS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat
    set VS_VERSION=2022 Community
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
    set VCVARS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat
    set VS_VERSION=2022 Professional
)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
    set VCVARS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat
    set VS_VERSION=2022 Enterprise
)
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat
    set VS_VERSION=2022 BuildTools
)

REM Check VS 2019
if "!VCVARS_PATH!"=="" (
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
        set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat
        set VS_VERSION=2019 Community
    )
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat" (
        set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat
        set VS_VERSION=2019 Professional
    )
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
        set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat
        set VS_VERSION=2019 BuildTools
    )
)

REM Check VS 2017
if "!VCVARS_PATH!"=="" (
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat" (
        set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvars64.bat
        set VS_VERSION=2017 Community
    )
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
        set VCVARS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvars64.bat
        set VS_VERSION=2017 BuildTools
    )
)

if "!VCVARS_PATH!"=="" (
    echo [31m✗[0m Visual Studio Build Tools not found!
    echo.
    echo Searched in:
    echo   C:\Program Files\Microsoft Visual Studio\2022\
    echo   C:\Program Files (x86)\Microsoft Visual Studio\2019\
    echo   C:\Program Files (x86)\Microsoft Visual Studio\2017\
    echo.
    echo Please install Visual Studio Build Tools from:
    echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo.
    echo Select "Desktop development with C++" workload during installation.
    echo.
    pause
    exit /b 1
)

echo [32m✓[0m Found Visual Studio !VS_VERSION!
echo.
echo Location: !VCVARS_PATH!
echo.

REM Activate Visual Studio environment
echo Activating Visual Studio environment...
call "!VCVARS_PATH!"

if !errorlevel! neq 0 (
    echo [31m✗[0m Failed to activate Visual Studio environment!
    pause
    exit /b 1
)

echo.
echo [32m✓[0m Visual Studio environment activated!
echo.

REM Verify cl.exe is available
where cl.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [32m✓[0m C++ compiler (cl.exe) is available
    for /f "tokens=*" %%v in ('cl.exe 2^>^&1 ^| findstr /C:"Version"') do (
        echo     %%v
    )
) else (
    echo [31m✗[0m Warning: cl.exe still not found in PATH
)

echo.
echo ===================================
echo You can now run:
echo   setup.bat          - Initial setup
echo   setup_offline.bat  - Offline setup
echo   python scripts\run_anywhere.py --config run_config.json
echo ===================================
echo.

REM Keep command prompt open with VS environment
cmd /k
