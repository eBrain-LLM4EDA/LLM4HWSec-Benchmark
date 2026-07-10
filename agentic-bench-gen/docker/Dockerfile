# Shared evaluation runner image for agentic-bench-gen.
#
# One image is reused for every benchmark case and every mutant run. The case
# workspace is bind-mounted at /work at runtime and executed as:
#   python3 evaluation/evaluate.py
# Nothing case-specific is baked into the image.
#
# Build once:
#   docker build -t agentic-bench-gen-runner:latest docker/
#
# Add hardware-security analysis tooling below as the benchmark grows
# (e.g. yosys, iverilog, verilator, sympy, z3) — evaluators will pick them up
# automatically; no runner code changes are required.
FROM python:3.11-slim

# Toolchain for behavioral (compile-and-run / simulate) grading:
#   gcc/g++  — HLS C/C++ kernels: evaluators compile the submission against a
#              generated test harness and execute it (functional KATs plus
#              behavioral security probes such as secret-invariance of outputs).
#   iverilog — RTL domains: compile + vvp-simulate submissions/testbenches.
#   yosys    — netlist domains: structural analysis, synth checks, equivalence.
# NOTE (HLS): a real HLS synthesis flow (Bambu / Vitis HLS) is intentionally
# NOT included — those tools are heavyweight and not apt-installable. HLS
# synthesizability is enforced as static subset checks (no malloc/recursion/
# STL/exceptions); functional and security properties are graded by compiling
# with g++ and executing. Add Bambu's AppImage below if true HLS synthesis
# grading becomes a requirement.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        iverilog \
        yosys \
    && rm -rf /var/lib/apt/lists/*

# Python analysis libraries available to every evaluator can be added here:
# RUN pip install --no-cache-dir z3-solver sympy

WORKDIR /work

# The runner overrides this with `python3 evaluation/evaluate.py`; the default
# just makes a bare `docker run <image>` print the interpreter version.
CMD ["python3", "--version"]
