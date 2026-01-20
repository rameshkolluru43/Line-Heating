# PLATFORM-INDEPENDENT.md

## How This Project Achieves Cross-Platform Independence

This document explains the design decisions and mechanisms that make this project work seamlessly across macOS, Windows, and Linux without requiring global system modifications.

---

## 🎯 Core Principles

### 1. **Local Virtual Environment**
All Python dependencies are installed in a local virtual environment (`.venv_lineheating/`) within the project folder:
- ✅ No global pip packages required
- ✅ No conflicts with system Python or other projects
- ✅ Complete isolation and reproducibility
- ✅ Easy cleanup (just delete the `.venv_lineheating/` folder)

### 2. **Self-Contained Dependencies**
Everything needed to run the simulation is either:
- Included in the repository (source code)
- Installed locally via `requirements.txt` (Python packages)
- Built locally (C++ extension)
- Or clearly documented for manual installation (system compilers)

### 3. **Platform Detection**
The `run_anywhere.py` script automatically detects:
- Operating system (Windows/macOS/Linux)
- Python executable location
- Virtual environment structure (Windows: `Scripts/`, Unix: `bin/`)
- CMake availability (system or Python package)
- Available compilers

---

## 📦 Dependency Management

### Python Dependencies (`requirements.txt`)
```
numpy>=1.26          # Numerical computing
scipy>=1.11          # Scientific computing
matplotlib>=3.8      # Plotting
gmsh>=4.11           # Mesh generation (Python bindings)
pybind11>=2.11       # C++/Python interface
cmake>=3.26          # Build system (fallback if not system-installed)
```

**How it works:**
1. Runner creates a Python venv in `.venv_lineheating/`
2. Installs all packages using `pip install -r requirements.txt`
3. All packages live in `.venv_lineheating/lib/` (or `Lib/` on Windows)
4. No impact on system Python installation

### C++ Build System (CMake + pybind11)

**Source:** `thermo_fem/cpp/`
**Build output:** `thermo_fem/build/cpp/`

The C++ thermal/mechanical solver is compiled into a Python extension module:
- Uses pybind11 (installed via pip) for Python bindings
- CMake handles cross-platform compilation
- Output: `thermo_bindings.so` (Unix) or `thermo_bindings.pyd` (Windows)

**Platform-specific compiler requirements:**
| Platform | Compiler | How to Install |
|----------|----------|----------------|
| macOS | Clang (via Xcode CLT) | `xcode-select --install` |
| Linux | GCC/G++ | `sudo apt-get install build-essential` |
| Windows | MSVC (Visual Studio) | Install VS Build Tools |

**Why not vendored?** Compilers are large (GBs) and OS-dependent. We require them as a system prerequisite but use them locally.

---

## 🔧 Build Process

### What Happens When You Run `run_anywhere.py`:

1. **Environment Setup**
   ```
   Create .venv_lineheating/
   Install pip packages from requirements.txt
   ```

2. **C++ Extension Build**
   ```
   CMake configure:  thermo_fem/cpp/ → thermo_fem/build/cpp/
   CMake build:      Compile thermo_bindings module
   Output:           thermo_bindings.so/.pyd in build directory
   ```

3. **Simulation Execution**
   ```
   Import thermo_bindings from build directory
   Run thermo_fem/python/run_coupled_3d.py
   Write outputs to results/
   ```

4. **Report Generation** (if LaTeX available)
   ```
   Generate report.tex
   Compile to report.pdf
   ```

**Key:** Everything happens in the project directory. No global state is modified.

---

## 🐳 Docker: Ultimate Platform Independence

For environments where installing compilers is difficult or you need perfect reproducibility:

```bash
docker build -t ship-plate-lineheating .
docker run -v $(pwd)/results:/workspace/results \
           ship-plate-lineheating --config run_config.json
```

**What's in the Docker image:**
- Ubuntu 22.04 base
- Python 3.11
- GCC/G++ compiler
- CMake
- Gmsh (both binary and Python package)
- LaTeX (for reports)
- All Python dependencies pre-installed

**Advantages:**
- ✅ Identical environment on any platform that runs Docker
- ✅ No need to install compilers or Python on host
- ✅ Isolate from host system completely
- ✅ Share via Docker Hub for ultimate reproducibility

---

## 📁 File Organization

### What Stays in the Repo (Version Controlled)
```
✓ Source code         (thermo_fem/cpp/, python_prototype/)
✓ Requirements        (requirements.txt)
✓ CMake configs       (CMakeLists.txt)
✓ Scripts             (scripts/run_anywhere.py)
✓ Documentation       (README.md, SETUP.md)
✓ Example configs     (run_config.example.json)
```

### What's Generated Locally (Not Tracked)
```
✗ Virtual environment  (.venv_lineheating/)
✗ Build artifacts      (thermo_fem/build/)
✗ Simulation results   (results/*)
✗ Python cache         (__pycache__/)
✗ User configs         (run_config.json)
```

**See [.gitignore](.gitignore) for complete list**

---

## 🌐 Platform-Specific Adaptations

### Path Handling
```python
# Cross-platform path construction
from pathlib import Path
repo_root = Path(__file__).resolve().parents[1]  # Works everywhere

# Platform-specific venv binary
if platform.system().startswith("win"):
    python_exe = venv_dir / "Scripts" / "python.exe"
else:
    python_exe = venv_dir / "bin" / "python"
```

### Line Endings
- **Windows:** CRLF (`\r\n`)
- **Unix:** LF (`\n`)
- **Python:** Opens files in text mode → auto-converts
- **Git:** Configure `.gitattributes` if needed

### Executable Permissions
```bash
# Unix: Make scripts executable
chmod +x setup.sh

# Windows: Not needed (.bat files are executable by default)
```

---

## 🔍 Verification

### Check Your Setup
```bash
python3 scripts/validate_setup.py
```

This validates:
- ✓ Python version (3.11+)
- ✓ C++ compiler available
- ✓ CMake available (system or pip)
- ✓ Project structure intact
- ⚠ Optional tools (Gmsh, LaTeX)
- ⚠ Virtual environment packages (if exists)

### Manual Verification
```bash
# Check Python
python3 --version

# Check compiler
gcc --version        # Linux/macOS
clang++ --version    # macOS
cl.exe               # Windows (in VS Developer Command Prompt)

# Check CMake
cmake --version

# Check venv (after first run)
ls .venv_lineheating/        # Unix
dir .venv_lineheating\       # Windows
```

---

## 🧹 Cleanup

### Remove Generated Files
```bash
# Safe cleanup (preserves source)
python3 scripts/clean_generated.py --apply

# Thorough cleanup (includes builds and caches)
python3 scripts/clean_generated.py --apply \
    --include-build \
    --include-caches \
    --include-latex-aux
```

### What Gets Removed:
- Virtual environment (`.venv_lineheating/`)
- Build artifacts (`thermo_fem/build/`)
- Results (`results/*/`)
- Python cache (`__pycache__/`)
- LaTeX intermediate files (`.aux`, `.log`, etc.)

**Source code is never touched!**

---

## 🚀 Best Practices

### 1. Use the Provided Scripts
```bash
# ✅ Good: Use run_anywhere.py
python3 scripts/run_anywhere.py --config run_config.json

# ❌ Avoid: Manual steps (error-prone)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd thermo_fem/cpp && cmake ...
```

### 2. Keep Results Separate
```json
{
  "out": "results/my_simulation"  // ✅ Under results/
}
```
```json
{
  "out": "thermo_fem/python/outputs"  // ❌ Mixes with source
}
```

### 3. Use Version Control
```bash
# ✅ Track your configs (if you want)
git add run_config.json

# ✅ Track changes to source
git add thermo_fem/cpp/src/

# ❌ Don't track generated files
# (They're already in .gitignore)
```

### 4. Docker for Collaboration
```bash
# Build once
docker build -t myproject:v1 .

# Share via Docker Hub
docker tag myproject:v1 username/myproject:v1
docker push username/myproject:v1

# Collaborators pull and run
docker pull username/myproject:v1
docker run -v $(pwd)/results:/workspace/results \
           username/myproject:v1 --config config.json
```

---

## 📚 Summary

This project is cross-platform because:

1. **Self-contained:** All dependencies in project folder
2. **Scripted setup:** Automated detection and configuration
3. **Virtual environment:** Isolated Python packages
4. **Local builds:** C++ compiled in-place
5. **Clear separation:** Source vs. generated files
6. **Docker option:** Complete environment portability
7. **Documented:** Clear instructions for each platform

**Result:** Clone, run setup, and go. No global changes needed! 🎉
