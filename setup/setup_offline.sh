#!/usr/bin/env bash
# Offline setup script for macOS and Linux
# Installs Python dependencies from local offline_packages folder

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo "Ship Plate Line Heating"
echo "Offline Installation"
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

# Check if offline_packages exists
if [ ! -d "offline_packages" ]; then
    echo "✗ offline_packages folder not found!"
    echo ""
    echo "This script requires the offline_packages folder with pre-downloaded Python packages."
    echo "Please follow the instructions in OFFLINE-SETUP.md"
    echo ""
    exit 1
fi

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
    echo "Python must be pre-installed on this machine."
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
    echo "C++ compiler must be pre-installed on this machine."
    exit 1
fi
echo ""

# Create virtual environment
echo "Creating virtual environment..."
VENV_DIR=".venv_lineheating"

if [ -d "$VENV_DIR" ]; then
    echo "⚠ Virtual environment already exists. Removing old one..."
    rm -rf "$VENV_DIR"
fi

"$PYTHON_CMD" -m venv "$VENV_DIR"
echo "✓ Virtual environment created: $VENV_DIR"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo ""

# Upgrade pip from offline packages
echo "Upgrading pip..."
python -m pip install --no-index --find-links=offline_packages --upgrade pip setuptools wheel || {
    echo "⚠ Warning: Could not upgrade pip (continuing anyway)"
}
echo ""

# Install dependencies from offline packages
echo "Installing dependencies from offline_packages..."
python -m pip install --no-index --find-links=offline_packages -r requirements.txt
echo "✓ Dependencies installed successfully"
echo ""

# Verify installation
echo "Verifying installation..."
python -c "import numpy, scipy, matplotlib, gmsh, pybind11, cmake" 2>/dev/null && {
    echo "✓ All core packages verified"
} || {
    echo "⚠ Warning: Some packages may not have been imported correctly"
}
echo ""

echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Virtual environment: $VENV_DIR"
echo ""
echo "Next steps:"
echo "1. Copy run_config.example.json to run_config.json"
echo "2. Edit run_config.json with your parameters"
echo "3. Run: python scripts/run_anywhere.py --config run_config.json"
echo ""
echo "To activate the environment manually:"
echo "  source $VENV_DIR/bin/activate"
echo ""
