#!/usr/bin/env bash
# Script to download all Python dependencies for offline installation
# Run this on an internet-connected machine

set -e

echo "==================================="
echo "Download Offline Packages"
echo "==================================="
echo ""

# Detect platform
OS="$(uname -s)"
case "$OS" in
    Linux*)     
        PLATFORM="Linux"
        PIP_PLATFORM="manylinux2014_x86_64"
        ;;
    Darwin*)    
        PLATFORM="macOS"
        # Detect architecture
        ARCH="$(uname -m)"
        if [ "$ARCH" = "arm64" ]; then
            PIP_PLATFORM="macosx_11_0_arm64"
        else
            PIP_PLATFORM="macosx_10_9_x86_64"
        fi
        ;;
    *)          
        echo "Unsupported platform: $OS"
        exit 1
        ;;
esac

echo "Platform detected: $PLATFORM"
echo "Architecture: $PIP_PLATFORM"
echo ""

# Find Python
PYTHON_CMD=""
for cmd in python3.11 python3.12 python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "✗ Python not found!"
    echo "Please install Python first."
    exit 1
fi

echo "Using Python: $PYTHON_CMD ($($PYTHON_CMD --version))"
echo ""

# Create offline packages directory
echo "Creating offline_packages directory..."
if [ -d "offline_packages" ]; then
    echo "Directory already exists, cleaning..."
    rm -rf "offline_packages"
fi
mkdir -p "offline_packages"
echo ""

# Download packages
echo "Downloading Python packages for $PLATFORM..."
echo "This may take a few minutes..."
echo ""

"$PYTHON_CMD" -m pip download -r requirements.txt \
    -d offline_packages \
    --platform "$PIP_PLATFORM" \
    --python-version 3.11 \
    --only-binary=:all: || {
    echo ""
    echo "⚠ Some packages may not be available as binary wheels."
    echo "Attempting to download source distributions..."
    "$PYTHON_CMD" -m pip download -r requirements.txt \
        -d offline_packages \
        --python-version 3.11
}

echo ""
echo "Downloading pip, setuptools, and wheel..."
"$PYTHON_CMD" -m pip download pip setuptools wheel -d offline_packages

echo ""
echo "==================================="
echo "Download Complete!"
echo "==================================="
echo ""
echo "All packages saved to: offline_packages/"
echo ""

# Count files and size
FILE_COUNT=$(ls -1 offline_packages | wc -l)
SIZE_KB=$(du -sk offline_packages | cut -f1)
SIZE_MB=$((SIZE_KB / 1024))

echo "Total files: $FILE_COUNT"
echo "Total size: ~${SIZE_MB} MB"
echo ""
echo "Next steps:"
echo "1. Transfer the entire project folder to the offline machine"
echo "2. On the offline machine, run: ./setup_offline.sh"
echo ""
echo "See OFFLINE-SETUP.md for detailed instructions."
echo ""
