# Quick Reference - Cross-Platform Commands

## Setup Commands

### Initial Setup

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `chmod +x setup.sh && ./setup.sh` |
| **Windows** | `setup.bat` |

### Validate Setup

| Platform | Command |
|----------|---------|
| **All** | `python3 scripts/validate_setup.py` |

---

## Running Simulations

### Basic Usage

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `python3 scripts/run_anywhere.py --config run_config.json` |
| **Windows** | `python scripts\run_anywhere.py --config run_config.json` |

### Alternative: Python Module

| Platform | Command |
|----------|---------|
| **All** | `python -m scripts.run_anywhere --config run_config.json` |

---

## Common Tasks

### Copy Example Config

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `cp run_config.example.json run_config.json` |
| **Windows** | `copy run_config.example.json run_config.json` |

### Edit Config

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `nano run_config.json` or `vim run_config.json` |
| **Windows** | `notepad run_config.json` |
| **VS Code** | `code run_config.json` |

### View Results

| Platform | Command |
|----------|---------|
| **All** | Open `results/<your_run>/report.pdf` |
| **ParaView** | Load `results/<your_run>/results.vtk` |

---

## Cleanup

### Remove Generated Files

| Platform | Command |
|----------|---------|
| **All** | `python3 scripts/clean_generated.py --apply` |

### Remove Everything (Including Build)

| Platform | Command |
|----------|---------|
| **All** | `python3 scripts/clean_generated.py --apply --include-build --include-caches` |

### Manual Cleanup

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `rm -rf .venv_lineheating results/ thermo_fem/build/` |
| **Windows** | `rmdir /s /q .venv_lineheating results thermo_fem\build` |

---

## Docker Commands

### Build Image

| Platform | Command |
|----------|---------|
| **All** | `docker build -t ship-plate-lineheating .` |

### Run Simulation

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `docker run -v $(pwd)/results:/workspace/results -v $(pwd)/run_config.json:/workspace/run_config.json:ro ship-plate-lineheating --config run_config.json` |
| **Windows (PowerShell)** | `docker run -v ${PWD}/results:/workspace/results -v ${PWD}/run_config.json:/workspace/run_config.json:ro ship-plate-lineheating --config run_config.json` |
| **Windows (CMD)** | `docker run -v %cd%\results:/workspace/results -v %cd%\run_config.json:/workspace/run_config.json:ro ship-plate-lineheating --config run_config.json` |

### Interactive Shell

| Platform | Command |
|----------|---------|
| **All** | `docker run -it --rm ship-plate-lineheating /bin/bash` |

### Docker Compose

| Platform | Command |
|----------|---------|
| **All (Production)** | `docker-compose up simulation` |
| **All (Development)** | `docker-compose run --rm dev /bin/bash` |

---

## Troubleshooting

### Check Python Version

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `python3 --version` |
| **Windows** | `python --version` or `py --version` |

### Check Compiler

| Platform | Command |
|----------|---------|
| **macOS** | `clang++ --version` or `g++ --version` |
| **Linux** | `g++ --version` |
| **Windows** | `cl.exe` (in VS Developer Command Prompt) |

### Check CMake

| Platform | Command |
|----------|---------|
| **All** | `cmake --version` |

### Check Virtual Environment

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `ls -la .venv_lineheating/` |
| **Windows** | `dir .venv_lineheating\` |

### Rebuild C++ Extension

| Platform | Command |
|----------|---------|
| **All** | `python3 scripts/run_anywhere.py --config run_config.json` |
| **Skip Simulation** | Add `"no_simulation": true` to `run_config.json` |

---

## Path Conventions

### In Commands

| Platform | Separator | Example |
|----------|-----------|---------|
| **macOS/Linux** | `/` | `scripts/run_anywhere.py` |
| **Windows** | `\` or `/` | `scripts\run_anywhere.py` or `scripts/run_anywhere.py` |

### In JSON Config

| Platform | Format | Example |
|----------|--------|---------|
| **All** | Forward slash `/` | `"out": "results/my_run"` |

**Note:** Python and JSON accept `/` on all platforms, including Windows.

---

## Environment Variables

### Set Python Path (if needed)

| Platform | Command |
|----------|---------|
| **macOS/Linux (bash/zsh)** | `export PYTHONPATH=/path/to/project:$PYTHONPATH` |
| **Windows (CMD)** | `set PYTHONPATH=C:\path\to\project;%PYTHONPATH%` |
| **Windows (PowerShell)** | `$env:PYTHONPATH="C:\path\to\project;$env:PYTHONPATH"` |

### Activate Virtual Environment (Manual)

| Platform | Command |
|----------|---------|
| **macOS/Linux** | `source .venv_lineheating/bin/activate` |
| **Windows (CMD)** | `.venv_lineheating\Scripts\activate.bat` |
| **Windows (PowerShell)** | `.venv_lineheating\Scripts\Activate.ps1` |

**Note:** The `run_anywhere.py` script handles this automatically!

---

## File Locations

### Important Files

| File | Purpose | Track in Git? |
|------|---------|---------------|
| `run_config.example.json` | Template configuration | ✅ Yes |
| `run_config.json` | Your configuration | ⚠️ Optional |
| `requirements.txt` | Python dependencies | ✅ Yes |
| `SETUP.md` | Setup instructions | ✅ Yes |
| `.gitignore` | Ignored files | ✅ Yes |

### Generated Directories

| Directory | Purpose | Track in Git? |
|-----------|---------|---------------|
| `.venv_lineheating/` | Python virtual environment | ❌ No |
| `results/` | Simulation outputs | ❌ No |
| `thermo_fem/build/` | C++ build artifacts | ❌ No |
| `__pycache__/` | Python bytecode cache | ❌ No |

---

## Getting Help

### Documentation Files

| File | Contents |
|------|----------|
| [README.md](README.md) | Project overview and quick start |
| [SETUP.md](SETUP.md) | Detailed platform-specific setup |
| [PLATFORM-INDEPENDENT.md](PLATFORM-INDEPENDENT.md) | How cross-platform support works |
| **QUICK-REFERENCE.md** | This file - command cheat sheet |

### Run Commands

| Task | Command |
|------|---------|
| **Runner help** | `python3 scripts/run_anywhere.py --help` |
| **Simulator help** | `python3 thermo_fem/python/run_coupled_3d.py --help` |
| **Validate setup** | `python3 scripts/validate_setup.py` |

---

## Tips & Tricks

### 1. Report Only (Skip Simulation)

Edit `run_config.json`:
```json
{
  "runner": {
    "report_only": true
  }
}
```

Or use flag:
```bash
python3 scripts/run_anywhere.py --report-only --out results/existing_run
```

### 2. Skip C++ Build (Already Built)

```json
{
  "runner": {
    "no_build": true
  }
}
```

### 3. Skip Report Generation

```json
{
  "runner": {
    "no_report": true
  }
}
```

### 4. Dry-Run Cleanup

```bash
# See what would be deleted
python3 scripts/clean_generated.py

# Actually delete
python3 scripts/clean_generated.py --apply
```

### 5. Custom Output Directory

```json
{
  "out": "results/my_custom_run"
}
```

Or command line:
```bash
python3 scripts/run_anywhere.py --out results/my_run --config run_config.json
```

### 6. Allow Output in Code Directories (Not Recommended)

```bash
python3 scripts/run_anywhere.py --allow-code-out --config run_config.json
```

---

## Common Patterns

### Full Workflow

```bash
# 1. Setup (first time only)
./setup.sh  # or setup.bat on Windows

# 2. Validate
python3 scripts/validate_setup.py

# 3. Configure
cp run_config.example.json run_config.json
# Edit run_config.json as needed

# 4. Run
python3 scripts/run_anywhere.py --config run_config.json

# 5. View results
open results/run_from_json/report.pdf  # macOS
# or: xdg-open results/run_from_json/report.pdf  # Linux
# or: start results\run_from_json\report.pdf  # Windows
```

### Development Workflow

```bash
# Make changes to C++ code
# ...

# Rebuild and test
python3 scripts/run_anywhere.py --config run_config.json

# Clean up between runs
python3 scripts/clean_generated.py --apply --include-build
```

### Docker Workflow

```bash
# Build once
docker build -t ship-plate .

# Run multiple times
docker run -v $(pwd)/results:/workspace/results \
           -v $(pwd)/run_config.json:/workspace/run_config.json:ro \
           ship-plate --config run_config.json
```

---

**For more details, see [SETUP.md](SETUP.md) and [PLATFORM-INDEPENDENT.md](PLATFORM-INDEPENDENT.md)**
