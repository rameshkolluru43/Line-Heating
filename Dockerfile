# Multi-stage Dockerfile for Ship Plate Line Heating simulation
# Provides a fully self-contained cross-platform environment

# Base stage with system dependencies
FROM ubuntu:22.04 as base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    # Build tools
    build-essential \
    cmake \
    ninja-build \
    # Gmsh
    gmsh \
    libgmsh-dev \
    # LaTeX (for report generation)
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    latexmk \
    # Utilities
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -s /bin/bash simuser && \
    mkdir -p /workspace && \
    chown -R simuser:simuser /workspace

USER simuser
WORKDIR /workspace

# Python dependencies stage
FROM base as python-deps

# Copy only requirements first for better caching
COPY --chown=simuser:simuser requirements.txt /workspace/

# Create virtual environment and install Python dependencies
RUN python3.11 -m venv /workspace/.venv_lineheating && \
    /workspace/.venv_lineheating/bin/pip install --upgrade pip setuptools wheel && \
    /workspace/.venv_lineheating/bin/pip install -r requirements.txt

# Application stage
FROM python-deps as app

# Copy the entire project
COPY --chown=simuser:simuser . /workspace/

# Build the C++ extension
RUN /workspace/.venv_lineheating/bin/python scripts/run_anywhere.py --no-report --config run_config.example.json || true

# Set up environment
ENV PATH="/workspace/.venv_lineheating/bin:${PATH}"
ENV PYTHONPATH="/workspace:${PYTHONPATH}"

# Create results directory
RUN mkdir -p /workspace/results

# Default command
CMD ["/bin/bash"]

# Production stage with healthcheck
FROM app as production

# Add labels
LABEL maintainer="Ship Plate Bending Team"
LABEL description="Ship Plate Line Heating 3D Simulation Environment"
LABEL version="1.0"

# Volume for results
VOLUME ["/workspace/results"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /workspace/.venv_lineheating/bin/python -c "import gmsh, numpy, scipy, matplotlib; print('OK')" || exit 1

ENTRYPOINT ["/workspace/.venv_lineheating/bin/python", "scripts/run_anywhere.py"]
