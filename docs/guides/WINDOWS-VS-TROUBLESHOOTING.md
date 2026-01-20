# Windows Visual Studio Build Tools - Troubleshooting Guide

This guide helps resolve common issues with Visual Studio Build Tools on Windows, which are required to compile the C++ thermal/mechanical solver extension.

---

## Quick Solutions

### Solution 1: Use Pre-Built Docker Image (Recommended)

**Easiest option** - Skip all C++ compiler issues:

```cmd
docker build -t ship-plate-lineheating .
docker run -v %cd%\results:/workspace/results ship-plate-lineheating
```

No Visual Studio needed! Everything is pre-compiled in the container.

### Solution 2: Use Developer Command Prompt

If Visual Studio is installed but not detected:

1. **Open "Developer Command Prompt for VS 2022"** (or 2019/2017)
   - Search in Start Menu for "Developer Command Prompt"
   - Or find it at: `C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat`

2. **Navigate to project and run setup:**
   ```cmd
   cd path\to\Ship_Plate_Bending_LineHeating
   setup.bat
   ```

3. **Always use Developer Command Prompt** for running simulations

### Solution 3: Add VS to PATH

Permanently enable Visual Studio tools in any command prompt:

1. **Find vcvars64.bat:**
   - VS 2022: `C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat`
   - VS 2022 BuildTools: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat`
   - VS 2019: `C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat`

2. **Add to system environment:**
   - Run in Command Prompt:
   ```cmd
   setx VSINSTALLDIR "C:\Program Files\Microsoft Visual Studio\2022\Community\"
   setx VCToolsInstallDir "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\<version>\"
   ```

3. **Or create a batch file** (`run_with_vs.bat`):
   ```cmd
   @echo off
   call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
   cmd /k
   ```

---

## Installing Visual Studio Build Tools

### Option A: Visual Studio Build Tools Only (Lighter)

1. **Download:**
   - [Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
   - Direct link: `vs_BuildTools.exe`

2. **Install with these workloads:**
   - ✅ **Desktop development with C++**
   - ✅ **MSVC v143 - VS 2022 C++ x64/x86 build tools** (or latest)
   - ✅ **Windows 10/11 SDK**
   - ✅ **CMake tools for Windows** (optional, we use Python cmake)

3. **Size:** ~5-7 GB

4. **Offline installation:**
   ```cmd
   REM Download installer with packages
   vs_BuildTools.exe --layout C:\VSOffline --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --lang en-US
   
   REM On offline machine, install from C:\VSOffline
   C:\VSOffline\vs_BuildTools.exe --noweb
   ```

### Option B: Full Visual Studio (Heavier, includes IDE)

1. **Download:**
   - [Visual Studio 2022 Community](https://visualstudio.microsoft.com/vs/community/) (Free)

2. **Install with these workloads:**
   - ✅ **Desktop development with C++**

3. **Size:** ~10-15 GB

### Option C: Chocolatey (Package Manager)

```cmd
REM Install Chocolatey first
@"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"

REM Install Visual Studio Build Tools
choco install visualstudio2022buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

---

## Common Issues & Fixes

### Issue 1: "error: Microsoft Visual C++ 14.0 or greater is required"

**Cause:** Visual Studio Build Tools not installed or not in PATH.

**Fix:**
1. Install Visual Studio Build Tools (see above)
2. Use Developer Command Prompt
3. Or manually activate VS environment:
   ```cmd
   call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
   ```

### Issue 2: "cl.exe not found" during pip install

**Cause:** Compiler not in PATH.

**Fix:**
```cmd
REM Find your VS installation path
dir /s /b "C:\Program Files\Microsoft Visual Studio\vcvars64.bat"
dir /s /b "C:\Program Files (x86)\Microsoft Visual Studio\vcvars64.bat"

REM Activate it before setup
call "<path_to_vcvars64.bat>"
setup.bat
```

### Issue 3: "Cannot open include file: 'Windows.h'"

**Cause:** Windows SDK not installed.

**Fix:**
1. Run Visual Studio Installer
2. Modify installation
3. Add **Windows 10 SDK** or **Windows 11 SDK**

### Issue 4: Setup works but simulation fails with "DLL load failed"

**Cause:** Runtime libraries missing.

**Fix:**
Install [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist):
```cmd
REM Download and install
winget install Microsoft.VCRedist.2015+.x64
```

### Issue 5: "MSBuild not found"

**Cause:** Build tools incomplete.

**Fix:**
1. Run Visual Studio Installer
2. Modify installation
3. Add **MSBuild** under Individual Components

---

## Verification

Test your Visual Studio installation:

```cmd
REM Test 1: Check cl.exe
where cl.exe

REM Test 2: Check version
cl.exe

REM Test 3: Try compiling simple program
echo #include ^<iostream^> > test.cpp
echo int main() { std::cout ^<^< "Hello"; return 0; } >> test.cpp
cl.exe test.cpp
test.exe
del test.*
```

Expected output: "Hello"

---

## Alternative: Use Pre-Compiled Wheels

If C++ compilation keeps failing, you can use pre-built binary wheels:

### Step 1: Build on a working Windows machine

```cmd
REM On a machine with working Visual Studio
cd Ship_Plate_Bending_LineHeating
setup.bat

REM Build the C++ extension
cd thermo_fem
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . --config Release

REM The compiled module is at: thermo_fem/build/Release/thermo_bindings.pyd
```

### Step 2: Copy pre-built module

Copy `thermo_bindings.pyd` to the offline machine at:
```
Ship_Plate_Bending_LineHeating/thermo_fem/python/thermo_bindings.pyd
```

### Step 3: Skip building

Modify `run_anywhere.py` to skip the build step by adding `--skip-build` flag support, or manually edit the config:

```json
{
  "runner": {
    "do_build": false
  }
}
```

---

## VS Code Integration

If using VS Code on Windows:

### 1. Install C/C++ Extension
```
ext install ms-vscode.cpptools
```

### 2. Configure tasks.json

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "windows": {
    "options": {
      "shell": {
        "executable": "cmd.exe",
        "args": [
          "/C",
          "\"C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat\"",
          "&&"
        ]
      }
    }
  },
  "tasks": [
    {
      "label": "Build and Run",
      "type": "shell",
      "command": "python",
      "args": [
        "scripts\\run_anywhere.py",
        "--config",
        "run_config.json"
      ],
      "group": {
        "kind": "build",
        "isDefault": true
      }
    }
  ]
}
```

### 3. Configure c_cpp_properties.json

Create `.vscode/c_cpp_properties.json`:

```json
{
  "configurations": [
    {
      "name": "Win32",
      "includePath": [
        "${workspaceFolder}/**",
        "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/*/include",
        "C:/Program Files (x86)/Windows Kits/10/Include/*/ucrt"
      ],
      "defines": ["_DEBUG", "UNICODE", "_UNICODE"],
      "windowsSdkVersion": "10.0.22000.0",
      "compilerPath": "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe",
      "cStandard": "c17",
      "cppStandard": "c++17",
      "intelliSenseMode": "windows-msvc-x64"
    }
  ],
  "version": 4
}
```

---

## Still Not Working?

### Use Docker (100% Reliable)

Docker completely bypasses all Visual Studio issues:

```cmd
REM One-time setup
docker build -t ship-plate-lineheating .

REM Run simulations (no VS needed!)
docker run -v %cd%\results:/workspace/results ^
           -v %cd%\run_config.json:/workspace/run_config.json:ro ^
           ship-plate-lineheating --config run_config.json
```

### Or Use WSL2 (Windows Subsystem for Linux)

```cmd
REM Install WSL2
wsl --install

REM Inside WSL (Linux)
sudo apt-get update
sudo apt-get install build-essential python3.11 python3.11-venv

# Use Linux setup script
cd /mnt/c/path/to/Ship_Plate_Bending_LineHeating
./setup.sh
```

---

## Quick Reference

| Problem | Solution |
|---------|----------|
| cl.exe not found | Use Developer Command Prompt |
| Build fails | Run `vcvars64.bat` first |
| No Build Tools | Install from visualstudio.com |
| Offline install | Download with `--layout` flag |
| Can't fix it | Use Docker instead |

---

## Support

If issues persist:
1. Check [Visual Studio docs](https://docs.microsoft.com/en-us/visualstudio/)
2. Verify Python version: `python --version` (need 3.11 or 3.12)
3. Check disk space (VS needs ~7 GB)
4. Try Docker as fallback
