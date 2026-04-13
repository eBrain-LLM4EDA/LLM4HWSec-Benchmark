# =============================================================================
# HLS Security-Aware Code Generation Benchmark (Arda)
# Docker image with PandA-bambu, Verilator, Clang, and evaluation framework
# =============================================================================
#
# Build:
#   docker build -t hls-security-benchmark .
#
# Run evaluation:
#   docker run --rm -v $(pwd)/llm_outputs:/data/submissions \
#       hls-security-benchmark --mode simulate
#
# Interactive shell:
#   docker run --rm -it hls-security-benchmark bash
#
# Run a single bambu synthesis:
#   docker run --rm -v $(pwd)/my_code:/data/submissions \
#       hls-security-benchmark bambu /data/submissions/secure.cpp \
#       --top-fname=aes_encrypt --simulate --simulator=VERILATOR
# =============================================================================

FROM ubuntu:22.04

LABEL maintainer="HLS Security Benchmark"
LABEL description="Evaluation environment for HLS security-aware code generation"
LABEL version="1.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ---- System packages ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    g++ \
    g++-multilib \
    gcc-multilib \
    # Bambu build dependencies
    autoconf \
    autoconf-archive \
    automake \
    bison \
    flex \
    libtool \
    libxml2-dev \
    libicu-dev \
    libmpfr-dev \
    libglpk-dev \
    liblzma-dev \
    zlib1g-dev \
    # Simulation
    verilator \
    iverilog \
    # Clang for AST analysis
    clang \
    libclang-dev \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # Utilities
    wget \
    curl \
    git \
    ca-certificates \
    fuse \
    libfuse2 \
    file \
    && rm -rf /var/lib/apt/lists/*

# ---- Install PandA-bambu via AppImage ----
# The AppImage is the easiest way to get a working bambu binary.
# We extract it since AppImage FUSE mounting doesn't work in Docker.
# Direct download URL from: https://github.com/ferrandi/PandA-bambu/releases
ARG BAMBU_APPIMAGE_URL=https://release.bambuhls.eu/bambu-2024.10.AppImage
RUN cd /tmp && \
    echo "Downloading bambu AppImage (this may take several minutes)..." && \
    wget --progress=dot:giga "${BAMBU_APPIMAGE_URL}" -O bambu.AppImage && \
    echo "Extracting AppImage..." && \
    chmod +x bambu.AppImage && \
    ./bambu.AppImage --appimage-extract && \
    mkdir -p /opt/bambu && \
    mv squashfs-root /opt/bambu/squashfs && \
    rm -f bambu.AppImage && \
    echo "bambu binary: $(ls -la /opt/bambu/squashfs/usr/bin/bambu)"

# Create a wrapper script that sets up the AppImage environment properly
# The actual binary is at /opt/bambu/squashfs/usr/bin/bambu
# It needs its bundled GCC-8 and Clang compilers on PATH, and bundled libs
RUN BAMBU_ROOT=/opt/bambu/squashfs && \
    echo '#!/bin/bash' > /usr/local/bin/bambu && \
    echo "export APPDIR=${BAMBU_ROOT}" >> /usr/local/bin/bambu && \
    echo "export PATH=${BAMBU_ROOT}/usr/bin:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/bin:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/bin:\${PATH}" >> /usr/local/bin/bambu && \
    echo "export LD_LIBRARY_PATH=${BAMBU_ROOT}/usr/lib:${BAMBU_ROOT}/usr/lib/x86_64-linux-gnu:${BAMBU_ROOT}/lib:${BAMBU_ROOT}/lib/x86_64-linux-gnu:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/lib:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/lib:\${LD_LIBRARY_PATH}" >> /usr/local/bin/bambu && \
    echo "exec ${BAMBU_ROOT}/usr/bin/bambu \"\$@\"" >> /usr/local/bin/bambu && \
    chmod +x /usr/local/bin/bambu && \
    echo "=== Wrapper script ===" && \
    cat /usr/local/bin/bambu

# Verify bambu runs
RUN bambu --version 2>&1 | head -5 || echo "WARNING: bambu --version failed"

# ---- HLS simulation headers (Xilinx open-source ap_int/ap_uint) ----
# Use Xilinx's official open-source arbitrary precision types instead of
# custom stubs. Apache 2.0 licensed, tested with g++ and clang.
# https://github.com/Xilinx/HLS_arbitrary_Precision_Types
RUN cd /opt && \
    git clone --depth 1 https://github.com/Xilinx/HLS_arbitrary_Precision_Types.git && \
    echo "Xilinx HLS types installed at /opt/HLS_arbitrary_Precision_Types/include"

# ---- Python dependencies ----
RUN pip3 install --no-cache-dir libclang || \
    pip3 install --no-cache-dir --break-system-packages libclang

# ---- Copy benchmark into image ----
WORKDIR /benchmark
COPY . /benchmark/

# Make evaluation scripts executable
RUN chmod +x /benchmark/evaluation/run_evaluation_v2.py \
             /benchmark/evaluation/sim_backend/bambu_backend.py \
             /benchmark/evaluation/analysis/ast_analyzer.py 2>/dev/null || true

# ---- Create mount point for submissions ----
RUN mkdir -p /data/submissions /data/output

# ---- Entrypoint script ----
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["--mode", "simulate"]
