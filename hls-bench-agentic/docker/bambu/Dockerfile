# =============================================================================
# HLS Bench Agentic — PandA-Bambu HLS execution environment
# =============================================================================
#
# PandA-Bambu ships as an x86_64 AppImage. We extract the embedded squashfs
# payload with Python + unsquashfs, avoiding AppImage execution during build.
#
# This Dockerfile is kept as an emergency local fallback. The normal
# hls-bench-agentic Compose/config path reuses:
#   hlssecbench-openrouter-bambu:latest
# built from agentic-hls/hlssecbench_openrouter, so it does not redownload the
# AppImage in this project.
#
# Run a single step manually:
#   docker run --rm \
#       --platform linux/amd64 \
#       -v /path/to/task/workspace:/workspace \
#       -w /workspace \
#       hlssecbench-openrouter-bambu:latest \
#       bash tests/run_synth.sh
# =============================================================================

FROM --platform=linux/amd64 ubuntu:22.04

LABEL maintainer="HLS Bench Agentic"
LABEL description="PandA-Bambu HLS execution container for hls_bench_agentic"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

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

ARG BAMBU_APPIMAGE_URL=https://release.bambuhls.eu/bambu-2024.10.AppImage
RUN wget --progress=dot:giga "${BAMBU_APPIMAGE_URL}" -O /tmp/bambu.AppImage \
    && echo "==> Downloaded: $(du -h /tmp/bambu.AppImage | cut -f1)"

COPY docker/bambu/find_sqfs_offset.py /usr/local/bin/find_sqfs_offset.py
RUN chmod +x /usr/local/bin/find_sqfs_offset.py

RUN cd /tmp \
    && OFFSET=$(python3 /usr/local/bin/find_sqfs_offset.py bambu.AppImage) \
    && echo "==> squashfs offset: ${OFFSET} bytes" \
    && mkdir -p /opt/bambu \
    && unsquashfs -o "${OFFSET}" -d /opt/bambu/squashfs bambu.AppImage \
    && rm -f bambu.AppImage \
    && echo "==> Installed: $(ls /opt/bambu/squashfs/usr/bin/bambu)"

RUN BAMBU_ROOT=/opt/bambu/squashfs \
    && echo '#!/bin/bash'                                                                                                                                                                                                              > /usr/local/bin/bambu \
    && echo "export APPDIR=${BAMBU_ROOT}"                                                                                                                                                                                             >> /usr/local/bin/bambu \
    && echo "export PATH=${BAMBU_ROOT}/usr/bin:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/bin:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/bin:\${PATH}"                                             >> /usr/local/bin/bambu \
    && echo "export LD_LIBRARY_PATH=${BAMBU_ROOT}/usr/lib:${BAMBU_ROOT}/usr/lib/x86_64-linux-gnu:${BAMBU_ROOT}/lib:${BAMBU_ROOT}/clang+llvm-16.0.0-x86_64-linux-gnu-ubuntu-18.04/lib:${BAMBU_ROOT}/clang+llvm-12.0.1-x86_64-linux-gnu-ubuntu-/lib:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:\${LD_LIBRARY_PATH}" >> /usr/local/bin/bambu \
    && echo "exec ${BAMBU_ROOT}/usr/bin/bambu \"\$@\""                                                                                                                                                                               >> /usr/local/bin/bambu \
    && chmod +x /usr/local/bin/bambu

RUN bambu --version 2>&1 | head -5 || echo "WARNING: bambu --version failed (OK if building under emulation)"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libc6-dev-i386 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
SHELL ["/bin/bash", "-lc"]

CMD ["bash", "-lc", \
     "bash tests/run_csim.sh && \
      bash tests/run_synth.sh && \
      bash tests/run_cosim.sh && \
      bash tests/run_rtl_security.sh"]
