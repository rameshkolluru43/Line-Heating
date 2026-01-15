@echo off
REM Cross-platform setup script for Windows
REM Sets up the environment and verifies all dependencies

setlocal enabledelayedexpansion

echo ===================================
echo Ship Plate Line Heating Setup
echo ===================================
echo.

echo Platform detected: Windows
echo.

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
    echo Install from: https://www.python.org/downloads/
    echo Or use: winget install Python.Python.3.11
    exit /b 1
)
echo.

REM Check Visual Studio Build Tools
echo Checking C++ compiler...
set CXX_FOUND=0

REM Check for cl.exe (Visual Studio)
where cl.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [32m✓[0m Found Visual Studio C++ compiler
    set CXX_FOUND=1
) else (
    REM Check common VS installation paths
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
    echo Install from: https://visualstudio.microsoft.com/downloads/
    echo Select "Desktop development with C++" workload
    echo Or install Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    exit /b 1
)
echo.

REM Check CMake
echo Checking CMake...
where cmake >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=3" %%v in ('cmake --version 2^>^&1 ^| findstr /C:"version"') do (
        echo [32m✓[0m Found CMake %%v
    )
) else (
    echo [33m⚠[0m CMake not found on system (will use Python package version)
    echo   Install with: winget install Kitware.CMake
)
echo.

REM Check optional Gmsh
echo Checking optional dependencies...
where gmsh >nul 2>&1
if !errorlevel! equ 0 (
    echo [32m✓[0m Found Gmsh
) else (
    echo [33m⚠[0m Gmsh executable not found (optional - Python bindings will be used)
    echo   Install with: choco install gmsh
    echo   Or download from: https://gmsh.info/
)

where latexmk >nul 2>&1
if !errorlevel! equ 0 (
    echo [32m✓[0m Found LaTeX installation
) else (
    where pdflatex >nul 2>&1
    if !errorlevel! equ 0 (
        echo [32m✓[0m Found LaTeX installation
    ) else (
        echo [33m⚠[0m LaTeX not found (optional - for PDF report generation)
        echo   Install MiKTeX from: https://miktex.org/download
        echo   Or TeX Live from: https://www.tug.org/texlive/
    )
)
echo.

REM Create virtual environment and install dependencies
echo Setting up Python environment...
echo Running: !PYTHON_CMD! scripts\run_anywhere.py --help
!PYTHON_CMD! scripts\run_anywhere.py --help >nul 2>&1

echo.
echo ===================================
echo [32m✓[0m Setup complete!
echo ===================================
echo.
echo To run a simulation:
echo   1. Copy the example config:
echo      copy run_config.example.json run_config.json
echo.
echo   2. Edit run_config.json with your parameters
echo.
echo   3. Run the simulation:
echo      !PYTHON_CMD! scripts\run_anywhere.py --config run_config.json
echo.
echo All dependencies will be installed in a local virtual environment.
echo Nothing is installed globally on your system.
echo.

pause
