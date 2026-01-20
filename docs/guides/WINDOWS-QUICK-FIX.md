# Windows Setup - Quick Solutions

Having trouble with Visual Studio Build Tools on Windows? Here are your options:

## 🚀 Fastest Solution: Docker (Recommended)

**No Visual Studio needed!** Docker includes everything pre-compiled.

```cmd
docker build -t ship-plate-lineheating .
docker run -v %cd%\results:/workspace/results ship-plate-lineheating
```

---

## 🔧 Fix Visual Studio Issues

### Option 1: Use Helper Script

```cmd
activate_vs_environment.bat
```

This finds and activates Visual Studio automatically, then run:

```cmd
setup.bat
```

### Option 2: Use Developer Command Prompt

1. Search "Developer Command Prompt" in Start Menu
2. Navigate to project folder
3. Run `setup.bat`

### Option 3: Manual Activation

```cmd
REM Find vcvars64.bat location:
dir /s /b "C:\Program Files\Microsoft Visual Studio\vcvars64.bat"

REM Activate it:
call "C:\Path\To\vcvars64.bat"

REM Then run setup:
setup.bat
```

---

## 📥 Install Visual Studio Build Tools

### Download:
[Build Tools for Visual Studio 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)

### During Installation:
- ✅ Select "Desktop development with C++"
- ✅ Select "MSVC v143 - VS 2022 C++ build tools"
- ✅ Select "Windows 10/11 SDK"

### Size: ~7 GB

### Offline Installation:
```cmd
REM On internet machine - download installer with packages
vs_BuildTools.exe --layout C:\VSOffline --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --lang en-US

REM Transfer C:\VSOffline to offline machine, then:
C:\VSOffline\vs_BuildTools.exe --noweb
```

---

## 🧪 Verify Installation

```cmd
REM Check if compiler is available
where cl.exe

REM Check version
cl.exe

REM Test compile
echo #include ^<iostream^> > test.cpp
echo int main() { std::cout ^<^< "OK"; } >> test.cpp
cl.exe test.cpp
test.exe
```

If you see "OK", you're ready!

---

## 📚 Detailed Help

For complete troubleshooting, see:
- [WINDOWS-VS-TROUBLESHOOTING.md](WINDOWS-VS-TROUBLESHOOTING.md) - Detailed solutions
- [OFFLINE-SETUP.md](OFFLINE-SETUP.md) - Offline installation
- [SETUP.md](SETUP.md) - General setup guide

---

## ❓ Common Errors

| Error | Solution |
|-------|----------|
| "Microsoft Visual C++ 14.0 required" | Run `activate_vs_environment.bat` |
| "cl.exe not found" | Use Developer Command Prompt |
| "Cannot open Windows.h" | Install Windows SDK |
| Still failing? | Use Docker instead |

---

## 💡 Pro Tips

1. **Always use Developer Command Prompt** if VS is installed
2. **Keep VS updated** through Visual Studio Installer
3. **Check disk space** (need ~7 GB for VS Build Tools)
4. **When in doubt, use Docker** - it's the most reliable option
