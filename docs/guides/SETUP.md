# Cross-Platform Setup Guide

This project is designed to run seamlessly on **macOS**, **Windows**, and **Linux** with all dependencies contained within the project folder.

## Quick Setup

### macOS / Linux

```bash
# Make setup script executable
chmod +x setup/setup.sh

# Run setup
./setup/setup.sh
```

### Windows

```cmd
REM Run setup
setup\setup.bat
```

The setup scripts will:
- ✓ Verify Python 3.11/3.12 is installed
- ✓ Check for C++ compiler
- ✓ Check for CMake
- ✓ Create a local virtual environment (`.venv_lineheating`)
- ✓ Install all Python dependencies locally
- ⚠ Notify about optional dependencies (Gmsh, LaTeX)

**Nothing is installed globally** - all dependencies stay within the project folder.

---

## System Requirements

### Python (Required)
- **Version:** Python 3.11 or 3.12 (recommended: 3.11)
- **macOS:** `brew install python@3.11`
- **Linux:** `sudo apt-get install python3.11` (Ubuntu/Debian)
- **Windows:** Download from [python.org](https://www.python.org/downloads/)

### C++ Compiler (Required)
Needed to build the C++ thermal/mechanical solver extension.

- **macOS:** 
  ```bash
  xcode-select --install
  ```

- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt-get install build-essential
  ```

- **Linux (Fedora/RHEL):**
  ```bash
  sudo dnf groupinstall 'Development Tools'
  ```

- **Windows:**
  - Visual Studio 2019/2022 with "Desktop development with C++" workload
  - Or [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

### CMake (Optional - included in requirements.txt)
- **macOS:** `brew install cmake`
- **Linux:** `sudo apt-get install cmake`
- **Windows:** `winget install Kitware.CMake`

If not installed system-wide, the Python `cmake` package will be used automatically.

### Gmsh (Optional - Python bindings included)
The Python `gmsh` package (installed automatically) provides the meshing functionality. The system executable is optional but recommended.

- **macOS:** `brew install gmsh`
- **Linux:** `sudo apt-get install gmsh`
- **Windows:** `choco install gmsh` or download from [gmsh.info](https://gmsh.info/)

### LaTeX (Optional - for PDF reports)
- **macOS:** `brew install --cask mactex-no-gui`
- **Linux:** `sudo apt-get install texlive-latex-extra latexmk`
- **Windows:** Install [MiKTeX](https://miktex.org/) or [TeX Live](https://www.tug.org/texlive/)

Without LaTeX, the simulation still generates `.tex` files; you just won't get PDF reports.

---

## Usage

### 1. Create Configuration

```bash
# Copy example config
cp run_config.example.json run_config.json

# Edit with your parameters
```

### 2. Run Simulation

**macOS / Linux:**
```bash
python3 scripts/run_anywhere.py --config run_config.json
```

**Windows:**
```cmd
python scripts\run_anywhere.py --config run_config.json
```

### 3. View Results

Results are written to the directory specified in your config (default: `results/run_from_json/`):
- `results.vtk` - ParaView visualization
- `summary.json` - Simulation summary
- `report.pdf` - Auto-generated report (if LaTeX available)
- `*.npy` - NumPy arrays for post-processing

---

## Docker Alternative (Fully Self-Contained)

For complete isolation and reproducibility across all platforms:

### Build and Run

```bash
# Build the Docker image
docker build -t ship-plate-lineheating .

# Run simulation
docker run -v $(pwd)/results:/workspace/results \
           -v $(pwd)/run_config.json:/workspace/run_config.json:ro \
           ship-plate-lineheating --config run_config.json
```

### Using Docker Compose

```bash
# Run production simulation
docker-compose up simulation

# Or use interactive development environment
docker-compose run --rm dev /bin/bash
```

Docker includes **all dependencies** (Python, C++, CMake, Gmsh, LaTeX) in a consistent environment.

---

## Project Structure

```
Ship_Plate_Bending_LineHeating/
├── setup.sh                    # macOS/Linux setup script
├── setup.bat                   # Windows setup script
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Docker orchestration
├── requirements.txt            # Python dependencies
├── run_config.example.json     # Example configuration
│
├── scripts/
│   ├── run_anywhere.py        # Main cross-platform runner
│   └── clean_generated.py     # Cleanup utility
│
├── thermo_fem/                # C++/Python thermal-mechanical solver
│   ├── cpp/                   # C++ source code
│   ├── python/                # Python simulation scripts
│   └── CMakeLists.txt         # Build configuration
│
├── python_prototype/          # Prototype/demo implementations
│   ├── line_heating/          # Core heating models
│   └── examples/              # Example scripts
│
├── .venv_lineheating/         # Local virtual environment (auto-created)
└── results/                   # Simulation outputs (auto-created)
```

---

## Troubleshooting

### Python Version Issues

```bash
# Check your Python version
python3 --version

# If you have multiple versions, specify explicitly:
python3.11 scripts/run_anywhere.py --config run_config.json
```

### C++ Build Errors

**macOS:** Ensure Xcode Command Line Tools are installed:
```bash
xcode-select --install
```

**Windows:** Ensure you're running from a "Developer Command Prompt for VS" or have Visual Studio Build Tools installed.

**Linux:** Install build essentials:
```bash
sudo apt-get install build-essential cmake
```

### Virtual Environment Issues

Delete and recreate:
```bash
rm -rf .venv_lineheating
python3 scripts/run_anywhere.py --config run_config.json
```

### Output Directory Issues

By default, outputs under code folders (like `thermo_fem/`) are redirected to `results/`. To override:

```bash
python3 scripts/run_anywhere.py --allow-code-out --config run_config.json
```

---

## Platform-Specific Notes

### macOS
- Apple Silicon (M1/M2/M3): Everything works natively with ARM builds
- Rosetta not required
- Homebrew recommended for optional dependencies

### Windows
- Use PowerShell or Command Prompt (not Git Bash for setup.bat)
- Path separators: use `\` in batch files, `/` works in Python
- Visual Studio 2019+ recommended (2017 minimum)

### Linux
- Tested on Ubuntu 20.04+, Debian 11+, Fedora 35+
- WSL2 fully supported
- ARM64 (Raspberry Pi, etc.) requires compilation from source

---

## Cleaning Up

Remove generated files:

```bash
# Dry run (see what would be deleted)
python3 scripts/clean_generated.py

# Actually delete
python3 scripts/clean_generated.py --apply

# Delete everything including build artifacts
python3 scripts/clean_generated.py --apply --include-build --include-caches
```

---

## Advanced: Manual Setup

If automated scripts don't work:

```bash
# 1. Create virtual environment
python3.11 -m venv .venv_lineheating

# 2. Activate it
# macOS/Linux:
source .venv_lineheating/bin/activate
# Windows:
.venv_lineheating\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Build C++ extension
cd thermo_fem/cpp
cmake -S . -B ../build/cpp -DPYBIND11_FINDPYTHON=ON
cmake --build ../build/cpp --config Release
cd ../..

# 5. Run simulation
python thermo_fem/python/run_coupled_3d.py --help
```

---

## Getting Help

1. Check that all system requirements are installed
2. Run the setup script for your platform
3. Review error messages - they often include install hints
4. Try the Docker approach for a known-good environment

For issues, provide:
- Operating system and version
- Python version (`python3 --version`)
- Full error message
- Output of setup script
