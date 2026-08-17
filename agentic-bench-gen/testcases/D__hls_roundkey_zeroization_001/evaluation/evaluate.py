#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grader for the hls_roundkey_zeroization_001 task.

Compiles inputs/cipher_kernel.cpp together with evaluation/harness_main.cpp
at -O0, -O2, -O3 using g++ -std=c++17, runs the resulting binaries in
various modes, and derives PASS/FAIL for each functional (FR1-FR4) and
security (SR1-SR4) requirement from observed behavior only.

A pure-Python reference AES-128 implementation (S-box generated via GF(2^8)
inversion, not hardcoded) is used to independently verify ciphertext
correctness, so no cryptographic constant tables are hardcoded here.

Note on the SR1/SR2 probe mechanism: evaluation/harness_main.cpp performs,
internally, a sweep of N fixed key/plaintext pairs x M repeated probe
attempts per pair, immediately reading back the same-depth stack frame
after each encrypt_block call. It reports the worst-case (i.e. the
maximum-nonzero-byte-count) attempt observed across the whole sweep as a
single "PROBE:<hex>" line. This grader only needs to assert that reported
worst-case is all-zero: since it is the maximum over every attempt across
every key/plaintext pair, an all-zero worst case guarantees every single
attempt was all-zero, which is what makes this check robust against
stack-layout noise that caused a single-shot probe to produce false
failures on a correctly hardened submission.
"""

import os
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

REQUIRED_INPUT_FILES = [
    "cipher_kernel.h",
    "cipher_kernel.cpp",
    "design_brief.md",
]

HARNESS_SRC = os.path.join(EVAL_DIR, "harness_main.cpp")

COMPILE_TIMEOUT = 30
RUN_TIMEOUT = 20

results = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, message=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, message))
    results.append((req_id, passed, message))


# ---------------------------------------------------------------------------
# Reference AES-128 implementation (pure Python, GF(2^8)-derived S-box).
# ---------------------------------------------------------------------------

def _gf_mul_bit(a, b):
    """Multiply two GF(2^8) elements modulo AES's reduction polynomial."""
    p = 0
    a &= 0xFF
    b &= 0xFF
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def _gf_inverse(a):
    """Multiplicative inverse in GF(2^8) via brute-force search (a != 0)."""
    if a == 0:
        return 0
    for x in range(1, 256):
        if _gf_mul_bit(a, x) == 1:
            return x
    raise RuntimeError("no inverse found")


def _rotl8(x, n):
    return ((x << n) | (x >> (8 - n))) & 0xFF


def _build_sbox():
    sbox = [0] * 256
    for a in range(256):
        inv = _gf_inverse(a)
        s = inv
        s = s ^ _rotl8(inv, 1) ^ _rotl8(inv, 2) ^ _rotl8(inv, 3) ^ _rotl8(inv, 4) ^ 0x63
        sbox[a] = s & 0xFF
    return sbox


_SBOX = _build_sbox()

# Structural sanity: AES S-box must be a permutation of 0..255.
assert sorted(_SBOX) == list(range(256)), "generated S-box is not a permutation"

_RCON = [0x00]
_rc = 1
for _ in range(10):
    _RCON.append(_rc)
    _rc = _gf_mul_bit(_rc, 2)


def _key_expansion(key):
    # key: list of 16 ints -> returns list of 44 32-bit words (176 bytes)
    w = [list(key[4 * i:4 * i + 4]) for i in range(4)]
    for i in range(4, 44):
        temp = list(w[i - 1])
        if i % 4 == 0:
            temp = [temp[1], temp[2], temp[3], temp[0]]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // 4]
        new_word = [w[i - 4][j] ^ temp[j] for j in range(4)]
        w.append(new_word)
    round_keys = []
    for word in w:
        round_keys.extend(word)
    return round_keys  # 176 bytes


def _gmul(a, b):
    return _gf_mul_bit(a, b)


def _sub_bytes(state):
    return [_SBOX[b] for b in state]


def _shift_rows(state):
    # state is column-major 4x4: index = col*4 + row
    out = list(state)
    # row 0 unchanged
    for row in range(1, 4):
        vals = [state[col * 4 + row] for col in range(4)]
        rotated = vals[row:] + vals[:row]
        for col in range(4):
            out[col * 4 + row] = rotated[col]
    return out


def _mix_columns(state):
    out = list(state)
    for c in range(4):
        a0 = state[c * 4 + 0]
        a1 = state[c * 4 + 1]
        a2 = state[c * 4 + 2]
        a3 = state[c * 4 + 3]
        out[c * 4 + 0] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
        out[c * 4 + 1] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
        out[c * 4 + 2] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
        out[c * 4 + 3] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
    return [b & 0xFF for b in out]


def _add_round_key(state, round_key_slice):
    return [state[i] ^ round_key_slice[i] for i in range(16)]


def aes128_encrypt(key_bytes, plaintext_bytes):
    """Reference AES-128 single block encryption. key/plaintext: bytes-like of len 16."""
    key = list(key_bytes)
    pt = list(plaintext_bytes)
    round_keys = _key_expansion(key)  # 176 bytes

    state = list(pt)
    state = _add_round_key(state, round_keys[0:16])

    for rnd in range(1, 10):
        state = _sub_bytes(state)
        state = _shift_rows(state)
        state = _mix_columns(state)
        state = _add_round_key(state, round_keys[rnd * 16:(rnd + 1) * 16])

    state = _sub_bytes(state)
    state = _shift_rows(state)
    state = _add_round_key(state, round_keys[10 * 16:11 * 16])

    return bytes(state)


# Fixed vectors matching the harness's hardcoded literals.
K1 = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f])
P1 = bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
            0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff])
K2 = bytes([0x00] * 16)
P2 = bytes([0x00] * 16)
KB = bytes([0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88,
            0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x00])
PB = bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
            0x90, 0xa0, 0xb0, 0xc0, 0xd0, 0xe0, 0xf0, 0x01])

REF_CT1 = aes128_encrypt(K1, P1).hex()
REF_CT2 = aes128_encrypt(K2, P2).hex()


# ---------------------------------------------------------------------------
# Setup checks
# ---------------------------------------------------------------------------

def check_setup():
    for fname in REQUIRED_INPUT_FILES:
        path = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(path):
            print("[TEST] FAIL: SETUP: {} not found".format(path))
            return False
    if not os.path.isfile(HARNESS_SRC):
        print("[TEST] FAIL: SETUP: {} not found".format(HARNESS_SRC))
        return False
    return True


# ---------------------------------------------------------------------------
# Compilation helper
# ---------------------------------------------------------------------------

def compile_binary(opt_level, workdir):
    src = os.path.join(INPUTS_DIR, "cipher_kernel.cpp")
    out_bin = os.path.join(workdir, "harness_{}".format(opt_level.strip("-")))
    cmd = ["g++", "-std=c++17", opt_level, "-I", INPUTS_DIR,
           "-o", out_bin, src, HARNESS_SRC]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=COMPILE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "compile timed out"
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace")
        return None, err[-2000:]
    return out_bin, None


def run_binary(binary_path, mode):
    try:
        proc = subprocess.run([binary_path, mode], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "run timed out"
    except Exception as e:
        return None, "run crashed: {}".format(e)
    if proc.returncode != 0:
        return None, "run crashed/timed out (exit code {})".format(proc.returncode)
    return proc.stdout.decode(errors="replace"), None


def parse_prefixed_line(output, prefix):
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


# ---------------------------------------------------------------------------
# Main grading logic
# ---------------------------------------------------------------------------

def main():
    if not check_setup():
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        dir_o0 = os.path.join(tmpdir, "o0")
        dir_o2 = os.path.join(tmpdir, "o2")
        dir_o3 = os.path.join(tmpdir, "o3")
        os.makedirs(dir_o0, exist_ok=True)
        os.makedirs(dir_o2, exist_ok=True)
        os.makedirs(dir_o3, exist_ok=True)

        bin_o0, err_o0 = compile_binary("-O0", dir_o0)
        bin_o2, err_o2 = compile_binary("-O2", dir_o2)
        bin_o3, err_o3 = compile_binary("-O3", dir_o3)

        # ---------------- FR1 / FR2 (compiled at -O0) ----------------
        if bin_o0 is None:
            record("FR1", False, "compile failed: {}".format(err_o0))
            record("FR2", False, "compile failed: {}".format(err_o0))
        else:
            out1, run_err1 = run_binary(bin_o0, "vec0")
            if out1 is None:
                record("FR1", False, run_err1)
            else:
                cipher1 = parse_prefixed_line(out1, "CIPHER:")
                if cipher1 is None:
                    record("FR1", False, "no CIPHER: line in output: {!r}".format(out1))
                elif cipher1.lower() != REF_CT1:
                    record("FR1", False,
                           "ciphertext mismatch: got {} expected {}".format(cipher1, REF_CT1))
                else:
                    record("FR1", True)

            out2, run_err2 = run_binary(bin_o0, "vec1")
            if out2 is None:
                record("FR2", False, run_err2)
            else:
                cipher2 = parse_prefixed_line(out2, "CIPHER:")
                if cipher2 is None:
                    record("FR2", False, "no CIPHER: line in output: {!r}".format(out2))
                elif cipher2.lower() != REF_CT2:
                    record("FR2", False,
                           "ciphertext mismatch: got {} expected {}".format(cipher2, REF_CT2))
                else:
                    record("FR2", True)

        # ---------------- FR3 (compile at -O2 + FR1/FR2 rerun) ----------------
        if bin_o2 is None:
            record("FR3", False, "compile failed: {}".format(err_o2))
        else:
            out1_o2, run_err1_o2 = run_binary(bin_o2, "vec0")
            out2_o2, run_err2_o2 = run_binary(bin_o2, "vec1")
            problems = []
            if out1_o2 is None:
                problems.append(run_err1_o2)
            else:
                c1 = parse_prefixed_line(out1_o2, "CIPHER:")
                if c1 is None or c1.lower() != REF_CT1:
                    problems.append("vec0 mismatch at -O2: got {}".format(c1))
            if out2_o2 is None:
                problems.append(run_err2_o2)
            else:
                c2 = parse_prefixed_line(out2_o2, "CIPHER:")
                if c2 is None or c2.lower() != REF_CT2:
                    problems.append("vec1 mismatch at -O2: got {}".format(c2))
            if problems:
                record("FR3", False, "; ".join(problems))
            else:
                record("FR3", True)

        # ---------------- FR4 (sequence, uses -O0 binary) ----------------
        if bin_o0 is None:
            record("FR4", False, "compile failed: {}".format(err_o0))
        else:
            out_seq, run_err_seq = run_binary(bin_o0, "seq")
            if out_seq is None:
                record("FR4", False, run_err_seq)
            else:
                seq1 = parse_prefixed_line(out_seq, "SEQ1:")
                seq2 = parse_prefixed_line(out_seq, "SEQ2:")
                seq3 = parse_prefixed_line(out_seq, "SEQ3:")
                if seq1 is None or seq2 is None or seq3 is None:
                    record("FR4", False, "missing SEQ lines in output: {!r}".format(out_seq))
                else:
                    ref_seq1 = aes128_encrypt(K1, P1).hex()
                    ref_seq2 = aes128_encrypt(KB, PB).hex()
                    ref_seq3 = aes128_encrypt(K1, P1).hex()
                    problems = []
                    if seq1.lower() != ref_seq1:
                        problems.append("SEQ1 mismatch: got {} expected {}".format(seq1, ref_seq1))
                    if seq2.lower() != ref_seq2:
                        problems.append("SEQ2 mismatch: got {} expected {}".format(seq2, ref_seq2))
                    if seq3.lower() != ref_seq3:
                        problems.append("SEQ3 mismatch: got {} expected {}".format(seq3, ref_seq3))
                    if seq1.lower() != seq3.lower():
                        problems.append("SEQ1 and SEQ3 differ (state carried over between calls)")
                    if problems:
                        record("FR4", False, "; ".join(problems))
                    else:
                        record("FR4", True)

        # ---------------- SR1 (multi-attempt multi-vector probe at -O0) ----------------
        if bin_o0 is None:
            record("SR1", False, "compile failed: {}".format(err_o0))
        else:
            out_probe0, run_err_probe0 = run_binary(bin_o0, "probe")
            if out_probe0 is None:
                record("SR1", False, run_err_probe0)
            else:
                probe0 = parse_prefixed_line(out_probe0, "PROBE:")
                if probe0 is None or len(probe0) != 352:
                    record("SR1", False,
                           "no valid PROBE: line (176 bytes hex) in output: {!r}".format(out_probe0))
                else:
                    try:
                        probe_bytes0 = bytes.fromhex(probe0)
                    except ValueError:
                        record("SR1", False, "PROBE: line not valid hex: {}".format(probe0))
                        probe_bytes0 = None
                    if probe_bytes0 is not None:
                        nonzero_count = sum(1 for b in probe_bytes0 if b != 0)
                        if nonzero_count != 0:
                            record("SR1", False,
                                   "worst-case attempt across {} key/plaintext pairs x repeated "
                                   "probes shows {} of 176 probed bytes nonzero at -O0 "
                                   "(round_keys not reliably cleared before return)".format(
                                       "N", nonzero_count))
                        else:
                            record("SR1", True)

        # ---------------- SR2 (same probe methodology at -O2 and -O3) ----------------
        sr2_problems = []
        if bin_o2 is None:
            sr2_problems.append("compile failed at -O2: {}".format(err_o2))
        else:
            out_probe2, run_err_probe2 = run_binary(bin_o2, "probe")
            if out_probe2 is None:
                sr2_problems.append("run failed at -O2: {}".format(run_err_probe2))
            else:
                probe2 = parse_prefixed_line(out_probe2, "PROBE:")
                if probe2 is None or len(probe2) != 352:
                    sr2_problems.append("no valid PROBE: line at -O2: {!r}".format(out_probe2))
                else:
                    try:
                        probe_bytes2 = bytes.fromhex(probe2)
                        nz = sum(1 for b in probe_bytes2 if b != 0)
                        if nz != 0:
                            sr2_problems.append(
                                "worst-case attempt across repeated multi-key probes shows {} of "
                                "176 probed bytes nonzero at -O2 "
                                "(clearing eliminated as dead store)".format(nz))
                    except ValueError:
                        sr2_problems.append("PROBE: line not valid hex at -O2: {}".format(probe2))

        if bin_o3 is None:
            sr2_problems.append("compile failed at -O3: {}".format(err_o3))
        else:
            out_probe3, run_err_probe3 = run_binary(bin_o3, "probe")
            if out_probe3 is None:
                sr2_problems.append("run failed at -O3: {}".format(run_err_probe3))
            else:
                probe3 = parse_prefixed_line(out_probe3, "PROBE:")
                if probe3 is None or len(probe3) != 352:
                    sr2_problems.append("no valid PROBE: line at -O3: {!r}".format(out_probe3))
                else:
                    try:
                        probe_bytes3 = bytes.fromhex(probe3)
                        nz = sum(1 for b in probe_bytes3 if b != 0)
                        if nz != 0:
                            sr2_problems.append(
                                "worst-case attempt across repeated multi-key probes shows {} of "
                                "176 probed bytes nonzero at -O3 "
                                "(clearing eliminated as dead store)".format(nz))
                    except ValueError:
                        sr2_problems.append("PROBE: line not valid hex at -O3: {}".format(probe3))

        if sr2_problems:
            record("SR2", False, "; ".join(sr2_problems))
        else:
            record("SR2", True)

        # ---------------- SR3 (correctness preserved at -O2/-O3) ----------------
        sr3_problems = []
        if bin_o2 is None:
            sr3_problems.append("compile failed at -O2: {}".format(err_o2))
        else:
            o2v0, e0 = run_binary(bin_o2, "vec0")
            o2v1, e1 = run_binary(bin_o2, "vec1")
            if o2v0 is None:
                sr3_problems.append("vec0 run failed at -O2: {}".format(e0))
            else:
                c = parse_prefixed_line(o2v0, "CIPHER:")
                if c is None or c.lower() != REF_CT1:
                    sr3_problems.append("vec0 mismatch at -O2: got {} expected {}".format(c, REF_CT1))
            if o2v1 is None:
                sr3_problems.append("vec1 run failed at -O2: {}".format(e1))
            else:
                c = parse_prefixed_line(o2v1, "CIPHER:")
                if c is None or c.lower() != REF_CT2:
                    sr3_problems.append("vec1 mismatch at -O2: got {} expected {}".format(c, REF_CT2))

        if bin_o3 is None:
            sr3_problems.append("compile failed at -O3: {}".format(err_o3))
        else:
            o3v0, e2 = run_binary(bin_o3, "vec0")
            o3v1, e3 = run_binary(bin_o3, "vec1")
            if o3v0 is None:
                sr3_problems.append("vec0 run failed at -O3: {}".format(e2))
            else:
                c = parse_prefixed_line(o3v0, "CIPHER:")
                if c is None or c.lower() != REF_CT1:
                    sr3_problems.append("vec0 mismatch at -O3: got {} expected {}".format(c, REF_CT1))
            if o3v1 is None:
                sr3_problems.append("vec1 run failed at -O3: {}".format(e3))
            else:
                c = parse_prefixed_line(o3v1, "CIPHER:")
                if c is None or c.lower() != REF_CT2:
                    sr3_problems.append("vec1 mismatch at -O3: got {} expected {}".format(c, REF_CT2))

        if sr3_problems:
            record("SR3", False, "; ".join(sr3_problems))
        else:
            record("SR3", True)

        # ---------------- SR4 (lenient best-effort dual-key leak heuristic) ----------------
        # This check is intentionally lenient: it only fails if the adjacent
        # scratch memory captured after two calls with different keys (same
        # plaintext) reproduces distinguishable, nonzero, differing content
        # that looks like leaked key-dependent material. Since a correct
        # submission clears round_keys (making both captures all-zero or at
        # least not key-schedule-shaped), this should never false-fail a
        # secure implementation. We treat "both captures all zero" or "both
        # captures identical" as PASS. We only FAIL if both captures are
        # nonzero AND differ from each other (suggesting the two calls left
        # behind distinguishable, key-dependent residue in adjacent working
        # storage beyond round_keys itself).
        if bin_o2 is None:
            record("SR4", False, "compile failed at -O2: {}".format(err_o2))
        else:
            out_dk, run_err_dk = run_binary(bin_o2, "dualkey")
            if out_dk is None:
                record("SR4", False, run_err_dk)
            else:
                dk1 = parse_prefixed_line(out_dk, "DK1:")
                dk2 = parse_prefixed_line(out_dk, "DK2:")
                if dk1 is None or dk2 is None:
                    record("SR4", False, "missing DK1:/DK2: lines in output: {!r}".format(out_dk))
                else:
                    try:
                        b1 = bytes.fromhex(dk1)
                        b2 = bytes.fromhex(dk2)
                    except ValueError:
                        record("SR4", False, "DK lines not valid hex")
                        b1 = None
                        b2 = None
                    if b1 is not None and b2 is not None:
                        b1_allzero = all(x == 0 for x in b1)
                        b2_allzero = all(x == 0 for x in b2)
                        if b1_allzero or b2_allzero or (b1 == b2):
                            record("SR4", True)
                        else:
                            # Both nonzero and differing: potential
                            # key-dependent residue distinguishable across
                            # calls in adjacent scratch storage.
                            record("SR4", False,
                                   "adjacent scratch buffer shows distinguishable "
                                   "nonzero, differing content across different-key "
                                   "calls with identical plaintext")

    all_passed = all(passed for (_id, passed, _msg) in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()