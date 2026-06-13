# =============================================================================
# HLSSecBench Agentic — PandA-Bambu HLS execution environment
# =============================================================================
#
# PandA-Bambu ships as an x86_64 AppImage.  We extract the embedded squashfs
# payload with Python + unsquashfs (no AppImage execution needed, which avoids
# QEMU/Rosetta exec issues on Apple-Silicon during `docker build`).
#
# Build:
#   docker compose build bambu-runner
#   # or directly:
#   docker build -t hlssecbench-openrouter-bambu:latest \
#       -f docker/bambu/Dockerfile .
#
# Run a single step manually:
#   docker run --rm \
#       -v /path/to/task/workspace:/workspace \
#       -w /workspace \
#       hlssecbench-openrouter-bambu:latest \
#       bash tests/run_synth.sh
# =============================================================================

# The squashfs-extracted Bambu binaries are x86_64; keep amd64 so containers
# run correctly on any host (Rosetta 2 on Apple Silicon, native elsewhere).
FROM --platform=linux/amd64 ubuntu:22.04

LABEL maintainer="HLSSecBench Agentic"
LABEL description="PandA-Bambu HLS execution container for hlssecbench_openrouter"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ---- System packages ----
# squashfs-tools  — provides unsquashfs to unpack the AppImage payload.
# python3         — used below to locate the squashfs offset inside the binary.
# (fuse/libfuse2 and g++-multilib are NOT needed here.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        verilator \
        iverilog \
        bash \
        python3 \
        python3-pip \
        wget \
        file \
        ca-certificates \
        libtinfo5 \
        libstdc++6 \
        linux-libc-dev \
        squashfs-tools \
    && { ln -s /usr/include/x86_64-linux-gnu/asm /usr/include/asm 2>/dev/null || true; } \
    && rm -rf /var/lib/apt/lists/*

# ---- Download PandA-Bambu AppImage (own layer — cached across rebuilds) ----
ARG BAMBU_APPIMAGE_URL=https://release.bambuhls.eu/bambu-2024.10.AppImage
RUN wget --progress=dot:giga "${BAMBU_APPIMAGE_URL}" -O /tmp/bambu.AppImage \
    && echo "==> Downloaded: $(du -h /tmp/bambu.AppImage | cut -f1)"

# ---- Python helper: find the first valid SquashFS 4.x superblock in the AppImage ----
# Shipped as a file in the build context — no shell quoting tricks needed.
# Validates the superblock version field so ELF-embedded 'sqsh' strings are
# rejected, works regardless of alignment, and scans the full file.
COPY docker/bambu/find_sqfs_offset.py /usr/local/bin/find_sqfs_offset.py
RUN chmod +x /usr/local/bin/find_sqfs_offset.py

# ---- Extract squashfs payload without executing the AppImage ----
# unsquashfs -o <bytes> reads the squashfs directly from the AppImage at the
# byte offset the helper script prints.
RUN cd /tmp \
    && OFFSET=$(python3 /usr/local/bin/find_sqfs_offset.py bambu.AppImage) \
    && echo "==> squashfs offset: ${OFFSET} bytes" \
    && mkdir -p /opt/bambu \
    && unsquashfs -o "${OFFSET}" -d /opt/bambu/squashfs bambu.AppImage \
    && rm -f bambu.AppImage \
    && echo "==> Installed: $(ls /opt/bambu/squashfs/usr/bin/bambu)"

# ---- Wrapper — hard-codes PATH / LD_LIBRARY_PATH for the extracted AppImage ----
RUN BAMBU_ROOT=/opt/bambu/squashfs \
    && echo '#!/bin/bash'                                                                                                                                                                                                              > /usr/local/bin/bambu \
    && echo "export APPDIR=${BAMBU_ROOT}"                                                                                                                                                                                             >> /usr/local/bin/bambu \
    && echo "export PATH=${BAMBU_ROOT}/usr/bin:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/bin:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/bin:\${PATH}"                                             >> /usr/local/bin/bambu \
    && echo "export LD_LIBRARY_PATH=${BAMBU_ROOT}/usr/lib:${BAMBU_ROOT}/usr/lib/x86_64-linux-gnu:${BAMBU_ROOT}/lib:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/lib:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/lib:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:\${LD_LIBRARY_PATH}" >> /usr/local/bin/bambu \
    && echo "exec ${BAMBU_ROOT}/usr/bin/bambu \"\$@\""                                                                                                                                                                               >> /usr/local/bin/bambu \
    && chmod +x /usr/local/bin/bambu

# Smoke-test (harmless WARNING if emulation is unavailable at build time)
RUN bambu --version 2>&1 | head -5 || echo "WARNING: bambu --version failed (OK if building under emulation)"

# Bambu's bundled frontend uses 32-bit GCC compatibility headers for C++.
# Keep this late in the Dockerfile so dependency tweaks do not invalidate the
# large AppImage download/extraction layers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libc6-dev-i386 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
SHELL ["/bin/bash", "-lc"]

# Default: run all four harness scripts in sequence.
CMD ["bash", "-lc", \
     "bash tests/run_csim.sh && \
      bash tests/run_synth.sh && \
      bash tests/run_cosim.sh && \
      bash tests/run_rtl_security.sh"]
