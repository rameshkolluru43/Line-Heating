#!/usr/bin/env bash
# Cross-platform setup script for macOS and Linux
# Sets up the environment and verifies all dependencies

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo "Ship Plate Line Heating Setup"
echo "==================================="
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Linux*)     PLATFORM="Linux";;
    Darwin*)    PLATFORM="macOS";;
    *)          PLATFORM="Unknown";;
esac

echo "Platform detected: $PLATFORM"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_CMD=""
for cmd in python3.11 python3.12 python3 python; do
    if command -v "$cmd" &> /dev/null; then
        VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ] && [ "$MINOR" -le 12 ]; then
            PYTHON_CMD="$cmd"
            echo "✓ Found Python $VERSION at $(which "$cmd")"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "✗ Python 3.11 or 3.12 not found!"
    echo ""
    case "$PLATFORM" in
        macOS)
            echo "Install with: brew install python@3.11"
            ;;
        Linux)
            echo "Install with: sudo apt-get install python3.11  (Debian/Ubuntu)"
            echo "         or: sudo dnf install python3.11       (Fedora/RHEL)"
            ;;
    esac
    exit 1
fi
echo ""

# Check C++ compiler
echo "Checking C++ compiler..."
CXX_FOUND=false
if command -v g++ &> /dev/null; then
    echo "✓ Found g++ at $(which g++)"
    CXX_FOUND=true
elif command -v clang++ &> /dev/null; then
    echo "✓ Found clang++ at $(which clang++)"
    CXX_FOUND=true
fi

if [ "$CXX_FOUND" = false ]; then
    echo "✗ C++ compiler not found!"
    echo ""
    case "$PLATFORM" in
        macOS)
            echo "Install with: xcode-select --install"
            ;;
        Linux)
            echo "Install with: sudo apt-get install build-essential  (Debian/Ubuntu)"
            echo "         or: sudo dnf groupinstall 'Development Tools'  (Fedora/RHEL)"
            ;;
    esac
    exit 1
fi
echo ""

# Check CMake
echo "Checking CMake..."
if command -v cmake &> /dev/null; then
    CMAKE_VERSION=$(cmake --version | head -n1 | awk '{print $3}')
    echo "✓ Found CMake $CMAKE_VERSION at $(which cmake)"
else
    echo "⚠ CMake not found on system (will use Python package version)"
fi
echo ""

# Check optional Gmsh
echo "Checking optional dependencies..."
if command -v gmsh &> /dev/null; then
    echo "✓ Found Gmsh at $(which gmsh)"
else
    echo "⚠ Gmsh executable not found (optional - Python bindings will be used)"
    case "$PLATFORM" in
        macOS)
            echo "  Install with: brew install gmsh"
            ;;
        Linux)
            echo "  Install with: sudo apt-get install gmsh  (Debian/Ubuntu)"
            ;;
    esac
fi

if command -v latexmk &> /dev/null || command -v pdflatex &> /dev/null; then
    echo "✓ Found LaTeX installation"
else
    echo "⚠ LaTeX not found (optional - for PDF report generation)"
    case "$PLATFORM" in
        macOS)
            echo "  Install with: brew install --cask mactex-no-gui"
            ;;
        Linux)
            echo "  Install with: sudo apt-get install texlive-latex-extra  (Debian/Ubuntu)"
            ;;
    esac
fi
echo ""

# Create virtual environment and install dependencies
echo "Setting up Python environment..."
echo "Running: $PYTHON_CMD scripts/run_anywhere.py --help"
"$PYTHON_CMD" scripts/run_anywhere.py --help > /dev/null 2>&1 || true
echo ""

echo "==================================="
echo "✓ Setup complete!"
echo "==================================="
echo ""
echo "To run a simulation:"
echo "  1. Copy the example config:"
echo "     cp run_config.example.json run_config.json"
echo ""
echo "  2. Edit run_config.json with your parameters"
echo ""
echo "  3. Run the simulation:"
echo "     $PYTHON_CMD scripts/run_anywhere.py --config run_config.json"
echo ""
echo "All dependencies will be installed in a local virtual environment."
echo "Nothing is installed globally on your system."
echo ""
