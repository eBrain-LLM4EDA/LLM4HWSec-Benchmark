import os
import re
import random
import shutil
import subprocess
import tempfile

try:
    from evaluation.private import coverage_utils
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import coverage_utils


_TIMEOUT_SECONDS = 30

_KERNEL_SRC = os.path.join("inputs", "modexp_kernel.cpp")
_HARNESS_SRC = os.path.join("evaluation", "harness_main.cpp")


def _compile_plain_binary(build_dir):
    """
    Compiles inputs/modexp_kernel.cpp + evaluation/harness_main.cpp into a
    plain (non-instrumented) binary under build_dir using g++ -O0.

    Returns (binary_path, None) on success, or (None, error_message) on
    any failure (missing source, timeout, or compiler error).
    """
    if not os.path.isfile(_KERNEL_SRC):
        return None, "inputs/modexp_kernel.cpp not found"
    if not os.path.isfile(_HARNESS_SRC):
        return None, "evaluation/harness_main.cpp not found"

    os.makedirs(build_dir, exist_ok=True)

    local_kernel = os.path.join(build_dir, "modexp_kernel.cpp")
    local_harness = os.path.join(build_dir, "harness_main.cpp")

    try:
        shutil.copyfile(_KERNEL_SRC, local_kernel)
        shutil.copyfile(_HARNESS_SRC, local_harness)
    except OSError as e:
        return None, "failed to stage sources into build dir: %s" % (e,)

    binary_name = "harness_plain"
    cmd = [
        "g++", "-O0", "-std=c++11",
        "-o", binary_name,
        "modexp_kernel.cpp", "harness_main.cpp",
    ]

    try:
        proc = subprocess.run(
            cmd, cwd=build_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS, text=True,
        )
    except subprocess.TimeoutExpired:
        return None, "g++ compilation timed out after %ds" % (_TIMEOUT_SECONDS,)
    except OSError as e:
        return None, "failed to invoke g++: %s" % (e,)

    if proc.returncode != 0:
        stderr_text = (proc.stderr or "").strip()
        stdout_text = (proc.stdout or "").strip()
        detail = stderr_text if stderr_text else stdout_text
        first_line = detail.splitlines()[0] if detail else "g++ compilation failed with no output"
        return None, first_line

    binary_path = os.path.join(build_dir, binary_name)
    if not os.path.isfile(binary_path):
        return None, "g++ reported success but binary %s was not produced" % (binary_path,)

    return binary_path, None


def _run_plain(binary_path, build_dir, base, exponent, modulus):
    """
    Runs the previously compiled plain binary with the given argv values.

    Returns (result_int, None) on success, or (None, error_message) on
    crash, timeout, or malformed output.
    """
    argv = ["./" + os.path.basename(binary_path), str(base), str(exponent), str(modulus)]

    try:
        proc = subprocess.run(
            argv, cwd=build_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS, text=True,
        )
    except subprocess.TimeoutExpired:
        return None, "run timed out after %ds (base=%s exponent=%s modulus=%s)" % (
            _TIMEOUT_SECONDS, base, exponent, modulus)
    except OSError as e:
        return None, "failed to execute binary: %s" % (e,)

    if proc.returncode != 0:
        return None, "binary exited with code %d (base=%s exponent=%s modulus=%s): %s" % (
            proc.returncode, base, exponent, modulus, (proc.stderr or "").strip())

    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("RESULT"):
            parts = line.split()
            if len(parts) == 2:
                try:
                    return int(parts[1]), None
                except ValueError:
                    pass

    return None, "no RESULT line found in harness output: %r" % (proc.stdout,)


def _build_fr1_vectors():
    """
    Builds the fixed deterministic vector set for FR1: an exponent=0 case,
    an exponent=1 case, a modulus=2 case, plus 6 vectors generated with a
    fixed random seed.
    """
    vectors = [
        (3, 0, 11),   # exponent = 0 case
        (3, 1, 11),   # exponent = 1 case
        (1, 5, 2),    # modulus = 2 case
    ]

    rng = random.Random(20240501)
    for _ in range(6):
        modulus = rng.randint(2, 65535)
        base = rng.randint(0, modulus - 1)
        exponent = rng.randint(0, 0xFFFFFFFF)
        vectors.append((base, exponent, modulus))

    return vectors


def _coverage_exponents():
    """
    Fixed set of exponents used for the FR4/SR1/SR2 coverage-based
    structural-invariance checks: 0, 1, all-ones, and one seeded random
    32-bit value.
    """
    rng = random.Random(77)
    random_exp = rng.randint(0, 0xFFFFFFFF)
    return [0, 1, 0xFFFFFFFF, random_exp]


def check_fr1():
    build_dir = tempfile.mkdtemp(prefix="fr1_")
    binary_path, err = _compile_plain_binary(build_dir)
    if binary_path is None:
        return False, "compile failed: %s" % (err,)

    vectors = _build_fr1_vectors()
    for base, exponent, modulus in vectors:
        expected = pow(base, exponent, modulus)
        result, run_err = _run_plain(binary_path, build_dir, base, exponent, modulus)
        if result is None:
            return False, "run crashed/timed out: %s" % (run_err,)
        if result != expected:
            return False, "mismatch for base=%d exponent=%d modulus=%d: expected %d got %d" % (
                base, exponent, modulus, expected, result)

    return True, ""


def check_fr2():
    build_dir = tempfile.mkdtemp(prefix="fr2_")
    binary_path, err = _compile_plain_binary(build_dir)
    if binary_path is None:
        return False, "compile failed: %s" % (err,)

    vectors = [
        (0, 7, 13, 0),   # base=0, exponent>0, modulus>1 => expect 0
        (5, 0, 13, 1),   # base>0, exponent=0, modulus>1 => expect 1
    ]

    for base, exponent, modulus, expected in vectors:
        result, run_err = _run_plain(binary_path, build_dir, base, exponent, modulus)
        if result is None:
            return False, "run crashed/timed out: %s" % (run_err,)
        if result != expected:
            return False, "mismatch for base=%d exponent=%d modulus=%d: expected %d got %d" % (
                base, exponent, modulus, expected, result)

    return True, ""


def check_fr3():
    build_dir = tempfile.mkdtemp(prefix="fr3_")
    binary_path, err = _compile_plain_binary(build_dir)
    if binary_path is None:
        return False, "compile failed: %s" % (err,)

    if not os.path.isfile(_KERNEL_SRC):
        return False, "inputs/modexp_kernel.cpp not found"

    try:
        with open(_KERNEL_SRC, "r", errors="replace") as f:
            source_text = f.read()
    except OSError as e:
        return False, "could not read inputs/modexp_kernel.cpp: %s" % (e,)

    banned_tokens = ["malloc(", "new ", "std::vector", "std::map", "printf(", "exit(", "abort("]
    for token in banned_tokens:
        if token in source_text:
            return False, "banned construct '%s' found in inputs/modexp_kernel.cpp" % (token,)

    return True, ""


def check_fr4():
    build_dir = tempfile.mkdtemp(prefix="fr4_")
    try:
        coverage_utils.compile_coverage_binary(build_dir)
    except coverage_utils.CompileError as e:
        return False, "compile failed: %s" % (e,)

    exponents = _coverage_exponents()
    base = 3
    modulus = 257

    per_run_loop_counts = []
    for exponent in exponents:
        try:
            data = coverage_utils.run_and_collect(build_dir, base, exponent, modulus)
        except coverage_utils.RunError as e:
            return False, "run crashed/timed out: %s" % (e,)

        loop_counts = {}
        for line_no, count, source_text in data["lines"]:
            if count is None:
                continue
            if re.search(r'\bfor\b', source_text) or re.search(r'\bwhile\b', source_text):
                loop_counts[line_no] = count
        per_run_loop_counts.append(loop_counts)

    common_lines = set(per_run_loop_counts[0].keys())
    for loop_counts in per_run_loop_counts[1:]:
        common_lines &= set(loop_counts.keys())

    if not common_lines:
        return False, "no common for/while loop lines found across coverage runs"

    found_32_or_33 = False
    for line_no in sorted(common_lines):
        counts = [loop_counts[line_no] for loop_counts in per_run_loop_counts]
        if len(set(counts)) != 1:
            return False, "loop line %d hit-count differs across exponents: %s" % (line_no, counts)
        if counts[0] in (32, 33):
            found_32_or_33 = True

    if not found_32_or_33:
        return False, "no for/while loop line exhibited a 32 or 33 hit-count across all tested exponents"

    return True, ""