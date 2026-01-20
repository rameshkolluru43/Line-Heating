# Documentation Index

Welcome to the Ship Plate Line Heating simulation documentation.

## 📖 Quick Links

### For New Users
1. **[Getting Started](../README.md)** - Project overview and quick start
2. **[Quick Start Guide](reference/QUICK-START-USE-CASES.md)** - Step-by-step tutorials
3. **[Setup Instructions](guides/SETUP.md)** - Installation guide

### For Specific Use Cases
- **[Use Cases Overview](reference/USE-CASES.md)** - Forward and inverse problem workflows
- **[Example Configs](../config/)** - Ready-to-use configuration files

### Setup & Installation
- **[Standard Setup](guides/SETUP.md)** - Regular installation
- **[Offline Setup](guides/OFFLINE-SETUP.md)** - For air-gapped environments
- **[Quick Reference](guides/QUICK-REFERENCE.md)** - Command cheat sheet

### Troubleshooting
- **[Windows Issues](guides/WINDOWS-VS-TROUBLESHOOTING.md)** - Detailed Visual Studio troubleshooting
- **[Windows Quick Fix](guides/WINDOWS-QUICK-FIX.md)** - Fast solutions for common Windows issues
- **[Cross-Platform Tips](guides/CROSS-PLATFORM-SUMMARY.md)** - Platform-specific notes

---

## 📁 Documentation Structure

```
docs/
├── README.md (this file)
├── guides/              # Setup and installation guides
│   ├── SETUP.md
│   ├── OFFLINE-SETUP.md
│   ├── QUICK-REFERENCE.md
│   ├── WINDOWS-VS-TROUBLESHOOTING.md
│   ├── WINDOWS-QUICK-FIX.md
│   ├── CROSS-PLATFORM-SUMMARY.md
│   └── PLATFORM-INDEPENDENT.md
└── reference/           # Technical reference and use cases
    ├── USE-CASES.md
    ├── QUICK-START-USE-CASES.md
    └── FILE-STRUCTURE.md
```

---

## 🎯 Choose Your Path

### I want to validate curvature from a given temperature (Forward Problem)
→ Read [Quick Start - Use Case A](reference/QUICK-START-USE-CASES.md#use-case-a-forward-problem---validate-curvature-profile)

### I want to optimize heating pattern for target curvature (Inverse Problem)
→ Read [Quick Start - Use Case B](reference/QUICK-START-USE-CASES.md#use-case-b-inverse-problem---optimize-heating-pattern)

### I'm having installation issues
→ Check [Setup Guide](guides/SETUP.md) or [Windows Troubleshooting](guides/WINDOWS-VS-TROUBLESHOOTING.md)

### I need to install without internet
→ Follow [Offline Setup Guide](guides/OFFLINE-SETUP.md)

### I just want a command reference
→ See [Quick Reference](guides/QUICK-REFERENCE.md)

---

## 📂 Related Folders

- **[`/setup/`](../setup/)** - Setup and installation scripts
- **[`/config/`](../config/)** - Example configuration files
- **[`/scripts/`](../scripts/)** - Utility scripts for running simulations
- **[`/results/`](../results/)** - Output directory for simulation results

---

## 🆘 Getting Help

1. **Check the guides** in this folder first
2. **Review example configs** in `/config/`
3. **Look at example scripts** in `/python_prototype/examples/`
4. **Check the solver README** in `/thermo_fem/README.md`

---

## 📚 Additional Resources

- **Theory:** See `inherent_strain_models.tex` in this folder
- **Literature:** Check `/LiteratureDocs/` for references
- **Examples:** Browse `/python_prototype/examples/` for sample scripts
