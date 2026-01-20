# Offline Installation Guide

This guide explains how to bundle all Python dependencies with the project for installation on machines without internet access.

## Overview

The offline setup allows you to:
- Package all Python dependencies as `.whl` files
- Transfer the project to an air-gapped machine
- Install everything without internet access

## Step 1: Download Dependencies (On Internet-Connected Machine)

### Windows

```cmd
REM Create dependencies folder
mkdir offline_packages

REM Download all packages with their dependencies
python -m pip download -r requirements.txt -d offline_packages --platform win_amd64 --python-version 3.11 --only-binary=:all:

REM Also download pip and setuptools
python -m pip download pip setuptools wheel -d offline_packages
```

### macOS/Linux

```bash
# Create dependencies folder
mkdir offline_packages

# Download all packages with their dependencies
python3 -m pip download -r requirements.txt -d offline_packages --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:

# Also download pip and setuptools
python3 -m pip download pip setuptools wheel -d offline_packages
```

### For Multiple Platforms

If you need to support multiple platforms, download for each:

```bash
# Create platform-specific folders
mkdir -p offline_packages/windows
mkdir -p offline_packages/linux
mkdir -p offline_packages/macos

# Windows (AMD64)
python -m pip download -r requirements.txt -d offline_packages/windows --platform win_amd64 --python-version 3.11 --only-binary=:all:

# Linux (x86_64)
python -m pip download -r requirements.txt -d offline_packages/linux --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:

# macOS (ARM64 - M1/M2)
python -m pip download -r requirements.txt -d offline_packages/macos --platform macosx_11_0_arm64 --python-version 3.11 --only-binary=:all:
```

## Step 2: Transfer to Offline Machine

Package the entire project folder including:
- All source code
- `offline_packages/` folder with downloaded `.whl` files
- Setup scripts

**Methods:**
- USB drive
- Shared network drive
- Zip and transfer: `zip -r project_offline.zip . -x "*.git*" -x "*.venv*" -x "*__pycache__*"`

## Step 3: Install on Offline Machine

### Prerequisites (Must be Pre-Installed)

These **cannot** be bundled and must be installed on the target machine:

1. **Python 3.11 or 3.12**
   - Windows: Download installer from python.org (can be copied to offline machine)
   - Linux: Use system package manager or pre-install
   - macOS: Pre-install from Homebrew or official installer

2. **C++ Compiler** ⚠️ **Common Issue on Windows**
   - **Windows:** Visual Studio Build Tools (download offline installer)
     - See [WINDOWS-VS-TROUBLESHOOTING.md](WINDOWS-VS-TROUBLESHOOTING.md) for detailed help
     - Use `activate_vs_environment.bat` if setup fails to find VS
   - **Linux:** `gcc/g++` (usually pre-installed)
   - **macOS:** Xcode Command Line Tools

**Option 1: Standard Installation**
```cmd
REM Navigate to project folder
cd Ship_Plate_Bending_LineHeating

REM Run offline setup
setup_offline.bat
```

**Option 2: If Visual Studio Build Tools not detected**
```cmd
REM First activate VS environment
activate_vs_environment.bat

REM Then run setup
setup_offline.bat
```

**Option 3: If C++ compilation keeps failing**
Use Docker (see section below) - no Visual Studio needed! Run offline setup
setup_offline.bat
```

### macOS/Linux Installation

```bash
# Navigate to project folder
cd Ship_Plate_Bending_LineHeating

# Make script executable
chmod +x setup_offline.sh

# Run offline setup
./setup_offline.sh
```

## Step 4: Verify Installation

```bash
# Validate setup
python scripts/validate_setup.py

# Run a test simulation
python scripts/run_anywhere.py --config run_config.example.json
```

---

## Alternative: Portable Python Distribution

For complete portability including Python itself:

### WinPython (Windows)

1. Download [WinPython](https://winpython.github.io/) (includes Python + packages)
2. Extract to project folder: `WinPython/`
3. Install additional packages from `offline_packages/`

### Conda/Miniforge (All Platforms)

1. Download [Miniforge installer](https://github.com/conda-forge/miniforge) for offline use
2. Create environment file:

```yaml
# environment.yml
name: lineheating
channels:
  - conda-forge
dependencies:
  - python=3.11
  - numpy>=1.26
  - scipy>=1.11
  - matplotlib>=3.8
  - gmsh>=4.11
  - pybind11>=2.11
  - cmake>=3.26
```

3. Download packages:
```bash
conda env create -f environment.yml
conda list --explicit > spec-file.txt
conda create --name lineheating_offline --file spec-file.txt --offline
```

---

## Docker Alternative (Recommended for Air-Gapped Systems)

The Docker image is the most reliable offline solution:

### On Internet-Connected Machine

```bash
# Build the image
docker build -t ship-plate-lineheating .

# Save image to file
docker save ship-plate-lineheating -o ship-plate-lineheating.tar

# Compress for transfer (optional)
gzip ship-plate-lineheating.tar
```

### On Offline Machine

```bash
# Load the image
docker load -i ship-plate-lineheating.tar

# Or if compressed
gunzip ship-plate-lineheating.tar.gz
docker load -i ship-plate-lineheating.tar

# Run simulation
docker run -v $(pwd)/results:/workspace/results \
           -v $(pwd)/run_config.json:/workspace/run_config.json:ro \
           Visual Studio Build Tools (Windows Only)

**Symptoms:**
- "error: Microsoft Visual C++ 14.0 or greater is required"
- "cl.exe not found"
- Build fails during pip install

**Solutions:**

1. **Use the helper script:**
   ```cmd
   activate_vs_environment.bat
   ```
   This automatically finds and activates Visual Studio environment.

2. **Use Developer Command Prompt:**
   - Search for "Developer Command Prompt" in Start Menu
   - Navigate to project and run `setup_offline.bat`

3. **Use Docker (easiest):**
   ```cmd
   docker load -i ship-plate-lineheating.tar
   docker run -v %cd%\results:/workspace/results ship-plate-lineheating
   ```

4. **Read detailed guide:**
   See [WINDOWS-VS-TROUBLESHOOTING.md](WINDOWS-VS-TROUBLESHOOTING.md) for complete solutions.

### Issue: ship-plate-lineheating --config run_config.json
```

**Advantages:**
- ✓ Includes ALL dependencies (Python, C++, CMake, Gmsh, LaTeX)
- ✓ Works identically on Windows, Linux, and macOS
- ✓ No system dependencies required except Docker
- ✓ Fully reproducible environment

---

## Troubleshooting

### Issue: "No matching distribution found"

**Cause:** Package not available as binary wheel for your platform.

**Solution:** 
1. Build from source on internet-connected machine
2. Use `--no-deps` flag to skip dependencies
3. Manually download source distributions (`.tar.gz`)

### Issue: C++ Extension Fails to Build

**Cause:** Missing compiler or build tools.

**Solution:**
- Ensure Visual Studio Build Tools are installed (Windows)
- Ensure `build-essential` is installed (Linux)
- Ensure Xcode CLT is installed (macOS)

### Issue: Permission Denied

**Solution:**
```bash
# Linux/macOS
chmod +x setup_offline.sh

# Windows: Run as Administrator
```

---

## Size Estimates

Typical sizes for `offline_packages/`:
- **Python packages only:** ~200-300 MB
- **With all dependencies:** ~400-500 MB
- **Docker image:** ~2-3 GB (includes entire runtime)

---

## Quick Reference

| Task | Command |
|------|---------|
| **Download packages** | `pip download -r requirements.txt -d offline_packages` |
| **Install offline (Windows)** | `setup_offline.bat` |
| **Install offline (Linux/macOS)** | `./setup_offline.sh` |
| **Validate** | `python scripts/validate_setup.py` |
| **Docker save** | `docker save ship-plate-lineheating -o image.tar` |
| **Docker load** | `docker load -i image.tar` |
