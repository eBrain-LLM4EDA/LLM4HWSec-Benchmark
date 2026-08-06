import os
import re
import shutil
import subprocess


class CompileError(Exception):
    """Raised when compiling the coverage-instrumented binary fails."""
    pass


class RunError(Exception):
    """Raised when running the compiled binary or invoking gcov fails."""
    pass


_TIMEOUT_SECONDS = 30


def _require_file(path, what):
    if not os.path.isfile(path):
        raise CompileError("%s not found: %s" % (what, path))


def _first_line(text):
    if not text:
        return ""
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0]


def compile_coverage_binary(build_dir):
    """
    Compiles inputs/modexp_kernel.cpp + evaluation/harness_main.cpp into a
    coverage-instrumented binary under build_dir, using an explicit
    two-step compile-then-link with g++ --coverage.

    Both compile steps (producing modexp_kernel.o/.gcno and
    harness_main.o/.gcno) and the link step are run with cwd=build_dir so
    that the .gcno notes files are generated with relative paths that
    match the .o files, and later runs of the binary produce .gcda data
    files colocated with those .gcno files in the same directory. This
    avoids the "cannot open notes file" gcov failure that occurs when a
    single combined compile+link g++ invocation uses a hidden/temporary
    object file path that does not match the source's expected .gcno
    naming.

    Returns the path to the compiled binary (build_dir/harness_cov) on
    success.

    Raises CompileError(stderr) on any compilation, link failure, or
    timeout.
    """
    src_kernel = os.path.join("inputs", "modexp_kernel.cpp")
    harness_src = os.path.join("evaluation", "harness_main.cpp")

    _require_file(src_kernel, "inputs/modexp_kernel.cpp")
    _require_file(harness_src, "evaluation/harness_main.cpp")

    os.makedirs(build_dir, exist_ok=True)

    local_kernel = os.path.join(build_dir, "modexp_kernel.cpp")
    local_harness = os.path.join(build_dir, "harness_main.cpp")

    try:
        shutil.copyfile(src_kernel, local_kernel)
        shutil.copyfile(harness_src, local_harness)
    except OSError as e:
        raise CompileError("failed to stage sources into build dir: %s" % (e,))

    def _run_step(cmd, step_name):
        try:
            proc = subprocess.run(
                cmd, cwd=build_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=_TIMEOUT_SECONDS, text=True,
            )
        except subprocess.TimeoutExpired:
            raise CompileError("%s timed out after %ds" % (step_name, _TIMEOUT_SECONDS))
        except OSError as e:
            raise CompileError("failed to invoke %s: %s" % (step_name, e))

        if proc.returncode != 0:
            detail = _first_line(proc.stderr) or _first_line(proc.stdout)
            if not detail:
                detail = "%s failed with no output" % (step_name,)
            raise CompileError(detail)

        return proc

    # Step 1: compile each translation unit separately with --coverage,
    # so the .gcno notes files are named/located deterministically
    # relative to build_dir.
    _run_step(
        ["g++", "--coverage", "-O0", "-std=c++11",
         "-c", "modexp_kernel.cpp", "-o", "modexp_kernel.o"],
        "g++ --coverage compile (modexp_kernel.cpp)",
    )
    _run_step(
        ["g++", "--coverage", "-O0", "-std=c++11",
         "-c", "harness_main.cpp", "-o", "harness_main.o"],
        "g++ --coverage compile (harness_main.cpp)",
    )

    kernel_obj = os.path.join(build_dir, "modexp_kernel.o")
    harness_obj = os.path.join(build_dir, "harness_main.o")
    kernel_gcno = os.path.join(build_dir, "modexp_kernel.gcno")

    if not os.path.isfile(kernel_obj):
        raise CompileError("g++ reported success but %s was not produced" % (kernel_obj,))
    if not os.path.isfile(harness_obj):
        raise CompileError("g++ reported success but %s was not produced" % (harness_obj,))
    if not os.path.isfile(kernel_gcno):
        raise CompileError("g++ --coverage compile succeeded but %s was not produced" % (kernel_gcno,))

    # Step 2: link the two object files into the final coverage binary,
    # again with cwd=build_dir and --coverage so the runtime coverage
    # library is linked in.
    binary_name = "harness_cov"
    _run_step(
        ["g++", "--coverage", "-o", binary_name, "modexp_kernel.o", "harness_main.o"],
        "g++ --coverage link",
    )

    binary_path = os.path.join(build_dir, binary_name)
    if not os.path.isfile(binary_path):
        raise CompileError("g++ reported success but binary %s was not produced" % (binary_path,))

    return binary_path


def _clean_stale_coverage_artifacts(build_dir):
    for name in (
        "modexp_kernel.gcda",
        "harness_main.gcda",
        "modexp_kernel.cpp.gcov",
        "harness_main.cpp.gcov",
    ):
        path = os.path.join(build_dir, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


_LINE_RE = re.compile(r'^\s*([^:]+):\s*(\d+):(.*)$')


def _parse_count_field(field):
    """
    Parses a gcov count field.

    Returns None for non-executable lines ('-'), 0 for lines that were
    never executed ('#####' or similar), or an integer execution count
    otherwise.
    """
    stripped = field.strip()
    if stripped == "-":
        return None
    if "#" in stripped:
        return 0
    digits = re.sub(r'[^0-9]', '', stripped)
    if digits == "":
        return None
    return int(digits)


def _parse_gcov_file(gcov_path):
    """
    Parses a .gcov file (produced with `gcov -b`) into:
      - lines_info: ordered list of (line_no, count_or_None, source_text)
      - branches_info: ordered list of raw 'branch N taken ...' strings,
        each paired with the most recently seen source line number, as
        (line_no, branch_text) tuples, preserving file order.
    """
    lines_info = []
    branches_info = []
    current_line_no = None

    with open(gcov_path, "r", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("branch"):
                branches_info.append((current_line_no, stripped))
                continue
            if stripped.startswith("call") or stripped.startswith("function"):
                # Not needed for our comparisons; skip.
                continue

            m = _LINE_RE.match(line)
            if not m:
                continue

            count_field, line_no_str, source_text = m.groups()
            line_no = int(line_no_str)
            current_line_no = line_no

            if line_no == 0:
                # Header/metadata line (e.g. "Source:modexp_kernel.cpp").
                continue

            count = _parse_count_field(count_field)
            lines_info.append((line_no, count, source_text))

    return lines_info, branches_info


def run_and_collect(build_dir, base, exponent, modulus):
    """
    Runs the previously compiled coverage binary in build_dir with the
    given (base, exponent, modulus) argv values, then invokes
    `gcov -b modexp_kernel.cpp` inside build_dir (matching the cwd used
    during compilation, so relative .gcno/.gcda paths resolve) and parses
    the resulting modexp_kernel.cpp.gcov file.

    Note: the `-n`/`--no-output` gcov flag must NOT be used here, since it
    explicitly suppresses writing the per-source .gcov report file to
    disk (gcov then only prints a percentage summary to stdout), which
    was the actual root cause of the previous "gcov did not produce
    expected file" failure.

    Returns a dict:
      {
        "result": <int RESULT value printed by the harness>,
        "lines": [(line_no, count_or_None, source_text), ...],
        "branches": [(line_no, "branch N taken ..."), ...],
      }

    Raises RunError(stderr) on crash, timeout, or gcov failure.
    """
    binary_path = os.path.join(build_dir, "harness_cov")
    if not os.path.isfile(binary_path):
        raise RunError("coverage binary not found at %s (was it compiled?)" % (binary_path,))

    _clean_stale_coverage_artifacts(build_dir)

    argv = ["./harness_cov", str(base), str(exponent), str(modulus)]

    try:
        proc = subprocess.run(
            argv, cwd=build_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS, text=True,
        )
    except subprocess.TimeoutExpired:
        raise RunError("harness execution timed out after %ds (base=%s exponent=%s modulus=%s)"
                        % (_TIMEOUT_SECONDS, base, exponent, modulus))
    except OSError as e:
        raise RunError("failed to execute harness binary: %s" % (e,))

    if proc.returncode != 0:
        raise RunError(
            "harness exited with code %d (base=%s exponent=%s modulus=%s): %s"
            % (proc.returncode, base, exponent, modulus, (proc.stderr or "").strip())
        )

    result_value = None
    for out_line in (proc.stdout or "").splitlines():
        out_line = out_line.strip()
        if out_line.startswith("RESULT"):
            parts = out_line.split()
            if len(parts) == 2:
                try:
                    result_value = int(parts[1])
                except ValueError:
                    pass

    if result_value is None:
        raise RunError("no RESULT line found in harness output: %r" % (proc.stdout,))

    # Deliberately do NOT pass -n/--no-output: that flag suppresses the
    # on-disk .gcov report entirely (only a summary is printed to
    # stdout), which was the root cause of the prior failure.
    gcov_cmd = ["gcov", "-b", "modexp_kernel.cpp"]
    try:
        gcov_proc = subprocess.run(
            gcov_cmd, cwd=build_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS, text=True,
        )
    except subprocess.TimeoutExpired:
        raise RunError("gcov timed out after %ds" % (_TIMEOUT_SECONDS,))
    except OSError as e:
        raise RunError("failed to invoke gcov: %s" % (e,))

    if gcov_proc.returncode != 0:
        raise RunError("gcov failed: %s" % ((gcov_proc.stderr or gcov_proc.stdout or "").strip()))

    gcov_path = os.path.join(build_dir, "modexp_kernel.cpp.gcov")
    if not os.path.isfile(gcov_path):
        raise RunError(
            "gcov did not produce expected file %s (stdout=%r stderr=%r)"
            % (gcov_path, (gcov_proc.stdout or "").strip(), (gcov_proc.stderr or "").strip())
        )

    try:
        lines_info, branches_info = _parse_gcov_file(gcov_path)
    except OSError as e:
        raise RunError("failed to read gcov output %s: %s" % (gcov_path, e))

    return {
        "result": result_value,
        "lines": lines_info,
        "branches": branches_info,
    }