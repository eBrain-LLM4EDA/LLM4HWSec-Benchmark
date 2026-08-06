#!/usr/bin/env python3
"""
evaluate.py -- behavioral evaluator for task `hls_ift_crypto_kernel`.

Grades the submission living under inputs/ (crypto_kernel.cpp,
crypto_kernel.h, design_brief.md) IN PLACE. Nothing under inputs/ is
modified; nothing is copied out of it.

Grading strategy (per the compile_and_run evaluation contract):
  1. Compile inputs/crypto_kernel.cpp together with evaluation/harness_main.cpp
     using the pinned public signature. A build failure fails every
     behaviorally-graded requirement (FR1-FR4, SR1-SR4).
  2. Run the resulting binary in several file-driven modes ('kat',
     'random', 'timing', 'sr4_silent') and judge PASS/FAIL strictly from
     observed outputs (files the harness writes, or -- for the silence
     check -- the raw stdout/stderr bytes of the subprocess itself).

No requirement PASSes because of how the submission's source text is
written; source is never inspected to grant a PASS.

Harness I/O protocol implemented by evaluation/harness_main.cpp
(invoked as: ./harness <mode> <infile> <outfile>; infile/outfile are
plain text files, never stdout/stderr):

  kat <infile> <outfile>
      infile is ignored; harness runs the fixed FR1 known-answer vector
      (plaintext = bytes 0..15, key = 0xFF repeated 16 times -- as
      literally specified by FR1) through crypto_kernel and writes:
          CIPHERTEXT=<32 hex chars>
          STATUS=<2 hex chars>
      to outfile.

  random <infile> <outfile>
      infile:
          <N>
          <plaintext_hex_32> <key_hex_32>
          ... (N lines)
      outfile (N lines, same order):
          CT=<32 hex chars> ST=<2 hex chars>

  timing <infile> <outfile>
      infile:
          <repeat_count>
          <plaintext_hex_32>
          <countA>
          <keyA_hex_32> ... (countA lines)
          <countB>
          <keyB_hex_32> ... (countB lines)
      outfile:
          GROUPA_NS=<integer total elapsed ns over countA*repeat_count calls>
          GROUPB_NS=<integer total elapsed ns over countB*repeat_count calls>

  sr4_silent <infile> <outfile>
      Same infile/outfile format as 'random'. The harness itself must
      emit nothing on stdout/stderr in this mode; any bytes observed on
      the subprocess's actual stdout/stderr can only have originated
      from the submitted crypto_kernel implementation.

All test vectors, key distributions, repeat counts and tolerances are
generated deterministically by evaluation/private/harness_support.py
(fixed seed, no wall-clock dependence).
"""

import os
import sys
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INPUTS_DIR = os.path.join(ROOT, "inputs")
EVAL_DIR = HERE
PRIVATE_DIR = os.path.join(EVAL_DIR, "private")

sys.path.insert(0, PRIVATE_DIR)

REQUIRED_INPUT_FILES = [
    os.path.join(INPUTS_DIR, "crypto_kernel.cpp"),
    os.path.join(INPUTS_DIR, "crypto_kernel.h"),
    os.path.join(INPUTS_DIR, "design_brief.md"),
]

ALL_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

COMPILE_TIMEOUT_S = 30
DEFAULT_RUN_TIMEOUT_S = 30
TIMING_RUN_TIMEOUT_S = 60

results = {}


def report(rid, ok, reason=""):
    if rid in results:
        return
    if ok:
        results[rid] = True
        print(f"[TEST] PASS: {rid}")
    else:
        results[rid] = False
        print(f"[TEST] FAIL: {rid}: {reason}")


def fail_all(reason):
    for rid in ALL_IDS:
        report(rid, False, reason)


def finish():
    for rid in ALL_IDS:
        if rid not in results:
            report(rid, False, "requirement was not evaluated")
    ok = all(results.get(rid, False) for rid in ALL_IDS)
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------------------
# Harness invocation helpers
# ---------------------------------------------------------------------------

def run_harness_file_mode(harness_path, mode, infile_text, timeout=DEFAULT_RUN_TIMEOUT_S):
    """Run the harness in a mode that communicates solely via files.
    Returns the outfile text, or raises RuntimeError on crash/timeout."""
    with tempfile.TemporaryDirectory(prefix="crypto_kernel_run_") as td:
        infile = os.path.join(td, "in.txt")
        outfile = os.path.join(td, "out.txt")
        with open(infile, "w") as f:
            f.write(infile_text)
        try:
            proc = subprocess.run(
                [harness_path, mode, infile, outfile],
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("run crashed/timed out")
        if proc.returncode != 0:
            raise RuntimeError("run crashed/timed out")
        if not os.path.isfile(outfile):
            raise RuntimeError("run crashed/timed out")
        with open(outfile, "r") as f:
            return f.read()


def run_harness_capture_stdio(harness_path, mode, infile_text, timeout=DEFAULT_RUN_TIMEOUT_S):
    """Run the harness and return (outfile_text, stdout_bytes, stderr_bytes,
    returncode) without treating a non-empty stdout/stderr as an error --
    the caller decides. Raises RuntimeError only on an actual timeout."""
    with tempfile.TemporaryDirectory(prefix="crypto_kernel_run_") as td:
        infile = os.path.join(td, "in.txt")
        outfile = os.path.join(td, "out.txt")
        with open(infile, "w") as f:
            f.write(infile_text)
        try:
            proc = subprocess.run(
                [harness_path, mode, infile, outfile],
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("run crashed/timed out")
        out_text = ""
        if os.path.isfile(outfile):
            with open(outfile, "r") as f:
                out_text = f.read()
        return out_text, proc.stdout, proc.stderr, proc.returncode


# ---------------------------------------------------------------------------
# Encoding / parsing helpers
# ---------------------------------------------------------------------------

def encode_pairs_infile(pairs):
    lines = [str(len(pairs))]
    for pt, key in pairs:
        lines.append(f"{pt.hex()} {key.hex()}")
    return "\n".join(lines) + "\n"


def encode_timing_infile(plaintext, repeat_count, group_a, group_b):
    lines = [str(repeat_count), plaintext.hex(), str(len(group_a))]
    lines += [k.hex() for k in group_a]
    lines.append(str(len(group_b)))
    lines += [k.hex() for k in group_b]
    return "\n".join(lines) + "\n"


def parse_kv(text):
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def parse_batch(text, expected_n):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) != expected_n:
        raise ValueError(f"expected {expected_n} result lines, got {len(lines)}")
    out = []
    for line in lines:
        vals = {}
        for tok in line.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                vals[k] = v
        if "CT" not in vals or "ST" not in vals:
            raise ValueError(f"malformed result line: {line!r}")
        try:
            ct = bytes.fromhex(vals["CT"])
            st = bytes.fromhex(vals["ST"])
        except ValueError:
            raise ValueError(f"non-hex data in line: {line!r}")
        if len(ct) != 16 or len(st) != 1:
            raise ValueError(f"unexpected field length in line: {line!r}")
        out.append((ct, st[0]))
    return out


def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Per-requirement probes
# ---------------------------------------------------------------------------

def run_fr1(harness_path, hs):
    try:
        out_text = run_harness_file_mode(harness_path, "kat", "")
        kv = parse_kv(out_text)
        if "CIPHERTEXT" not in kv or "STATUS" not in kv:
            report("FR1", False, f"malformed kat output: {out_text!r}")
            return
        ct = bytes.fromhex(kv["CIPHERTEXT"])
        st = bytes.fromhex(kv["STATUS"])
        expected_ct = xor_bytes(hs.FR1_PLAINTEXT, hs.FR1_KEY)
        if len(ct) != 16 or ct != expected_ct:
            report("FR1", False, f"ciphertext mismatch: got {ct.hex()} expected {expected_ct.hex()}")
            return
        if len(st) != 1 or st[0] != 0x00:
            report("FR1", False, f"status != 0x00, got {kv.get('STATUS')}")
            return
        report("FR1", True)
    except RuntimeError as exc:
        report("FR1", False, str(exc))
    except Exception as exc:
        report("FR1", False, f"unexpected error: {exc}")


def run_fr2(harness_path, hs):
    try:
        pairs = list(hs.random_pairs(120))
        infile_text = encode_pairs_infile(pairs)
        out_text = run_harness_file_mode(harness_path, "random", infile_text)
        batch = parse_batch(out_text, len(pairs))
        for idx, ((pt, key), (ct, _st)) in enumerate(zip(pairs, batch)):
            expected_ct = xor_bytes(pt, key)
            if ct != expected_ct:
                report(
                    "FR2", False,
                    f"pair #{idx}: ciphertext mismatch, got {ct.hex()} expected {expected_ct.hex()}",
                )
                return
        report("FR2", True)
    except RuntimeError as exc:
        report("FR2", False, str(exc))
    except Exception as exc:
        report("FR2", False, f"unexpected error: {exc}")


def run_fr3(harness_path, hs):
    try:
        pairs = list(hs.random_pairs(120))
        pairs += list(hs.edge_case_pairs())
        sr1_pt, sr1_keys = hs.sr1_vectors(200)
        pairs += [(sr1_pt, k) for k in sr1_keys]
        infile_text = encode_pairs_infile(pairs)
        out_text = run_harness_file_mode(harness_path, "random", infile_text)
        batch = parse_batch(out_text, len(pairs))
        for idx, (_ct, st) in enumerate(batch):
            if st != 0x00:
                report("FR3", False, f"pair #{idx}: status=0x{st:02x} (expected 0x00)")
                return
        report("FR3", True)
    except RuntimeError as exc:
        report("FR3", False, str(exc))
    except Exception as exc:
        report("FR3", False, f"unexpected error: {exc}")


def run_sr1(harness_path, hs):
    try:
        pt, keys = hs.sr1_vectors(200)
        pairs = [(pt, k) for k in keys]
        infile_text = encode_pairs_infile(pairs)
        out_text = run_harness_file_mode(harness_path, "random", infile_text)
        batch = parse_batch(out_text, len(pairs))
        statuses = {st for (_ct, st) in batch}
        if statuses != {0x00}:
            observed = ", ".join(f"0x{v:02x}" for v in sorted(statuses))
            report("SR1", False, f"status varied across {len(keys)} distinct keys: observed {{{observed}}}")
            return
        report("SR1", True)
    except RuntimeError as exc:
        report("SR1", False, str(exc))
    except Exception as exc:
        report("SR1", False, f"unexpected error: {exc}")


def run_sr2(harness_path, hs):
    try:
        plaintext, group_a, group_b, repeat_count = hs.timing_vectors()
        infile_text = encode_timing_infile(plaintext, repeat_count, group_a, group_b)
        out_text = run_harness_file_mode(harness_path, "timing", infile_text, timeout=TIMING_RUN_TIMEOUT_S)
        kv = parse_kv(out_text)
        if "GROUPA_NS" not in kv or "GROUPB_NS" not in kv:
            report("SR2", False, f"malformed timing output: {out_text!r}")
            return
        try:
            ns_a = int(kv["GROUPA_NS"])
            ns_b = int(kv["GROUPB_NS"])
        except ValueError:
            report("SR2", False, f"non-integer timing output: {out_text!r}")
            return
        n_a = repeat_count * len(group_a)
        n_b = repeat_count * len(group_b)
        if n_a <= 0 or n_b <= 0:
            report("SR2", False, "malformed timing vectors: empty group")
            return
        avg_a = ns_a / n_a
        avg_b = ns_b / n_b
        denom = max(avg_a, avg_b, hs.TIMING_ABS_FLOOR_NS)
        rel_diff = abs(avg_a - avg_b) / denom
        if rel_diff > hs.TIMING_TOLERANCE_RATIO:
            report(
                "SR2", False,
                f"timing diverges with key content: avgA={avg_a:.1f}ns avgB={avg_b:.1f}ns "
                f"rel_diff={rel_diff:.3f} > tol={hs.TIMING_TOLERANCE_RATIO}",
            )
            return
        report("SR2", True)
    except RuntimeError as exc:
        report("SR2", False, str(exc))
    except Exception as exc:
        report("SR2", False, f"unexpected error: {exc}")


def run_sr3(harness_path, hs):
    try:
        pairs = list(hs.random_pairs(120))
        pairs += list(hs.edge_case_pairs())
        sr1_pt, sr1_keys = hs.sr1_vectors(200)
        pairs += [(sr1_pt, k) for k in sr1_keys]
        infile_text = encode_pairs_infile(pairs)
        out_text = run_harness_file_mode(harness_path, "random", infile_text)
        batch = parse_batch(out_text, len(pairs))
        for idx, ((pt, key), (ct, st)) in enumerate(zip(pairs, batch)):
            expected_ct = xor_bytes(pt, key)
            if ct != expected_ct:
                report(
                    "SR3", False,
                    f"pair #{idx}: ciphertext depends on more than plaintext^key, "
                    f"got {ct.hex()} expected {expected_ct.hex()}",
                )
                return
            if st != 0x00:
                report(
                    "SR3", False,
                    f"pair #{idx}: status=0x{st:02x} correlates with key content (expected constant 0x00)",
                )
                return
        report("SR3", True)
    except RuntimeError as exc:
        report("SR3", False, str(exc))
    except Exception as exc:
        report("SR3", False, f"unexpected error: {exc}")


def run_sr4(harness_path, hs):
    try:
        pairs = list(hs.sr4_pairs())
        infile_text = encode_pairs_infile(pairs)
        out_text, stdout_bytes, stderr_bytes, rc = run_harness_capture_stdio(
            harness_path, "sr4_silent", infile_text,
        )
        if rc != 0:
            report("SR4", False, "run crashed/timed out")
            return
        if stdout_bytes or stderr_bytes:
            report(
                "SR4", False,
                f"unexpected output on stdout/stderr: stdout={stdout_bytes!r} stderr={stderr_bytes!r}",
            )
            return
        batch = parse_batch(out_text, len(pairs))
        if len(batch) != len(pairs):
            report("SR4", False, "unexpected result count in sr4_silent output")
            return
        report("SR4", True)
    except RuntimeError as exc:
        report("SR4", False, str(exc))
    except Exception as exc:
        report("SR4", False, f"unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # --- setup checks ------------------------------------------------
    for path in REQUIRED_INPUT_FILES:
        if not os.path.isfile(path):
            rel = os.path.relpath(path, ROOT)
            print(f"[TEST] FAIL: SETUP: {rel} not found")
            sys.exit(1)

    harness_main = os.path.join(EVAL_DIR, "harness_main.cpp")
    if not os.path.isfile(harness_main):
        print("[TEST] FAIL: SETUP: evaluation/harness_main.cpp not found")
        sys.exit(1)

    try:
        import harness_support as hs
    except Exception as exc:
        print(f"[TEST] FAIL: SETUP: could not import evaluation/private/harness_support.py: {exc}")
        sys.exit(1)

    # --- compile -------------------------------------------------------
    tmpdir = tempfile.mkdtemp(prefix="crypto_kernel_eval_")
    harness_path = os.path.join(tmpdir, "harness")
    cpp_path = os.path.join(INPUTS_DIR, "crypto_kernel.cpp")

    compile_cmd = [
        "g++", "-std=c++11", "-O2", "-Wall",
        "-I", INPUTS_DIR,
        "-o", harness_path,
        cpp_path, harness_main,
    ]

    try:
        proc = subprocess.run(
            compile_cmd, capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        fail_all("compile failed: compiler timed out after 30s")
        finish()
        return
    except FileNotFoundError as exc:
        fail_all(f"compile failed: toolchain unavailable ({exc})")
        finish()
        return

    if proc.returncode != 0:
        stderr_lines = [l for l in proc.stderr.splitlines() if l.strip()]
        first_line = stderr_lines[0] if stderr_lines else "unknown compiler error"
        fail_all(f"compile failed: {first_line}")
        finish()
        return

    # Compilation succeeded: the submission links against the pinned
    # signature and compiles cleanly under -Wall.
    report("FR4", True)

    # --- behavioral probes ----------------------------------------------
    run_fr1(harness_path, hs)
    run_fr2(harness_path, hs)
    run_fr3(harness_path, hs)
    run_sr1(harness_path, hs)
    run_sr2(harness_path, hs)
    run_sr3(harness_path, hs)
    run_sr4(harness_path, hs)

    finish()


if __name__ == "__main__":
    main()