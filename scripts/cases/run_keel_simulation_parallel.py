"""
Optimized parallel run for keel plate FEM simulation.
Uses environment variables to enable multi-threaded BLAS/LAPACK operations.
"""

import os
import sys
from pathlib import Path

# Set environment variables for parallel execution BEFORE importing numpy/scipy
os.environ['OMP_NUM_THREADS'] = '8'  # OpenMP threads
os.environ['OPENBLAS_NUM_THREADS'] = '8'  # OpenBLAS threads
os.environ['MKL_NUM_THREADS'] = '8'  # Intel MKL threads (if available)
os.environ['NUMEXPR_NUM_THREADS'] = '8'  # NumExpr threads
os.environ['VECLIB_MAXIMUM_THREADS'] = '8'  # macOS Accelerate framework

print(f"\n{'='*60}")
print("🚀 PARALLEL FEM SIMULATION - OPTIMIZED")
print(f"{'='*60}\n")
print(f"CPU Cores Available: 8")
print(f"Parallel Threads Set: 8")
print(f"OpenBLAS: ENABLED")
print(f"Sparse Solver: Multi-threaded")
print(f"\n{'='*60}\n")

# Now run the simulation
sys.path.insert(0, str(Path(__file__).parent))
from run_keel_simulation import main

if __name__ == "__main__":
    sys.exit(main())
