# Setup Scripts

This folder contains all setup and installation scripts for the Ship Plate Line Heating project.

## 🚀 Quick Setup

### For Online Installation

**macOS / Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

### For Offline Installation

First, on an internet-connected machine, download packages:

**Windows:**
```cmd
download_offline_packages.bat
```

**macOS / Linux:**
```bash
chmod +x download_offline_packages.sh
./download_offline_packages.sh
```

Then, transfer the entire project folder to the offline machine and run:

**Windows:**
```cmd
setup_offline.bat
```

**macOS / Linux:**
```bash
chmod +x setup_offline.sh
./setup_offline.sh
```

---

## 📁 Files in This Folder

### Main Setup Scripts
- **`setup.sh`** - Main setup script for macOS/Linux (requires internet)
- **`setup.bat`** - Main setup script for Windows (requires internet)

### Offline Setup Scripts
- **`setup_offline.sh`** - Offline setup for macOS/Linux
- **`setup_offline.bat`** - Offline setup for Windows
- **`download_offline_packages.sh`** - Downloads Python packages for offline use (macOS/Linux)
- **`download_offline_packages.bat`** - Downloads Python packages for offline use (Windows)

### Troubleshooting Helper
- **`activate_vs_environment.bat`** - (Windows only) Finds and activates Visual Studio environment

---

## 🔧 What the Setup Scripts Do

1. ✅ Verify Python 3.11/3.12 is installed
2. ✅ Check for C++ compiler (required for building extension)
3. ✅ Check for CMake (optional, can use Python package)
4. ✅ Create virtual environment (`.venv_lineheating`)
5. ✅ Install Python dependencies locally
6. ⚠️ Check for optional tools (Gmsh, LaTeX)

**Nothing is installed globally** - all dependencies stay within the project folder.

---

## 📖 Detailed Documentation

- **Setup Guide:** [`/docs/guides/SETUP.md`](../docs/guides/SETUP.md)
- **Offline Setup:** [`/docs/guides/OFFLINE-SETUP.md`](../docs/guides/OFFLINE-SETUP.md)
- **Windows Issues:** [`/docs/guides/WINDOWS-VS-TROUBLESHOOTING.md`](../docs/guides/WINDOWS-VS-TROUBLESHOOTING.md)
- **Quick Reference:** [`/docs/guides/QUICK-REFERENCE.md`](../docs/guides/QUICK-REFERENCE.md)

---

## 🆘 Troubleshooting

### Windows: Visual Studio Build Tools Not Found

Run the helper script:
```cmd
activate_vs_environment.bat
```

Then re-run setup.

Or see detailed guide: [`/docs/guides/WINDOWS-VS-TROUBLESHOOTING.md`](../docs/guides/WINDOWS-VS-TROUBLESHOOTING.md)

### macOS: Command Line Tools Not Installed

```bash
xcode-select --install
```

### Linux: Missing Build Tools

**Ubuntu/Debian:**
```bash
sudo apt-get install build-essential python3.11-venv
```

**Fedora/RHEL:**
```bash
sudo dnf groupinstall 'Development Tools'
```

---

## 🐳 Alternative: Docker

Skip all setup complexity with Docker:

```bash
docker build -t ship-plate-lineheating .
docker run -v $(pwd)/results:/workspace/results ship-plate-lineheating
```

See main README.md for details.
