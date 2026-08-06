import os
import re
import random
import tempfile

try:
    from evaluation.private import coverage_utils
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import coverage_utils


_KERNEL_SRC = os.path.join("inputs", "modexp_kernel.cpp")


def _coverage_exponents():
    """
    Fixed set of exponents used for the SR1/SR2 coverage-based
    structural-invariance checks: 0, 1, all-ones, and one seeded random
    32-bit value. Mirrors the set used for FR4 so the same 4-run
    evidence characterizes both functional and security invariance.
    """
    rng = random.Random(77)
    random_exp = rng.randint(0, 0xFFFFFFFF)
    return [0, 1, 0xFFFFFFFF, random_exp]


def _collect_runs(build_dir):
    """
    Compiles a coverage-instrumented binary and runs it for each of the
    four fixed exponents (fixed base=3, modulus=257), returning a list
    of per-run dicts as produced by coverage_utils.run_and_collect.

    Raises coverage_utils.CompileError / RunError on failure.
    """
    coverage_utils.compile_coverage_binary(build_dir)

    exponents = _coverage_exponents()
    base = 3
    modulus = 257

    runs = []
    for exponent in exponents:
        data = coverage_utils.run_and_collect(build_dir, base, exponent, modulus)
        runs.append((exponent, data))

    return runs


def check_sr1():
    """
    SR1: the operation-count-invariance proxy. Compares, across all four
    tested exponents, the full ordered list of executed-line hit-counts
    for every executable line of inputs/modexp_kernel.cpp. A secure,
    constant-schedule kernel must show byte-for-byte identical
    hit-counts on every line regardless of exponent value (e.g. the
    multiply-accumulate line must be hit exactly the same number of
    times whether the exponent is 0x00000000 or 0xFFFFFFFF). On the
    shipped baseline, the guarded multiply line inside
    `if ((exponent >> i) & 1u) { ... }` is executed 0 times for
    exponent=0 but 32 times for exponent=0xFFFFFFFF, which this check
    must catch.
    """
    build_dir = tempfile.mkdtemp(prefix="sr1_")
    try:
        runs = _collect_runs(build_dir)
    except coverage_utils.CompileError as e:
        return False, "compile failed: %s" % (e,)
    except coverage_utils.RunError as e:
        return False, "run crashed/timed out: %s" % (e,)

    # Build, for each run, a dict of line_no -> executed count, restricted
    # to executable lines only (count is not None).
    per_run_counts = []
    for exponent, data in runs:
        counts = {}
        for line_no, count, _source_text in data["lines"]:
            if count is None:
                continue
            counts[line_no] = count
        per_run_counts.append((exponent, counts))

    reference_exponent, reference_counts = per_run_counts[0]

    for line_no in sorted(reference_counts.keys()):
        ref_count = reference_counts[line_no]
        for exponent, counts in per_run_counts[1:]:
            if line_no not in counts:
                return False, (
                    "line %d present in exponent=%s coverage but missing for exponent=%s"
                    % (line_no, reference_exponent, exponent)
                )
            other_count = counts[line_no]
            if other_count != ref_count:
                all_counts = [c.get(line_no) for _e, c in per_run_counts]
                return False, (
                    "line %d hit-count differs across exponents %s: counts=%s"
                    % (line_no, [e for e, _c in per_run_counts], all_counts)
                )

    return True, ""


def check_sr2():
    """
    SR2: the control-flow-path-invariance proxy. Compares, across the
    same four tested exponents, the full ordered list of `gcov -b`
    branch-taken annotations for inputs/modexp_kernel.cpp. A secure
    kernel that never branches on exponent-derived data must show
    identical branch-taken annotations regardless of exponent value,
    catching secret-dependent branches even in cases where aggregate
    per-line hit-counts might otherwise coincide.
    """
    build_dir = tempfile.mkdtemp(prefix="sr2_")
    try:
        runs = _collect_runs(build_dir)
    except coverage_utils.CompileError as e:
        return False, "compile failed: %s" % (e,)
    except coverage_utils.RunError as e:
        return False, "run crashed/timed out: %s" % (e,)

    reference_exponent, reference_data = runs[0]
    reference_branches = reference_data["branches"]

    for exponent, data in runs[1:]:
        branches = data["branches"]

        if len(branches) != len(reference_branches):
            return False, (
                "branch annotation count differs between exponent=%s (%d branches) and "
                "exponent=%s (%d branches)"
                % (reference_exponent, len(reference_branches), exponent, len(branches))
            )

        for idx in range(len(reference_branches)):
            ref_line_no, ref_text = reference_branches[idx]
            other_line_no, other_text = branches[idx]
            if ref_line_no != other_line_no or ref_text != other_text:
                return False, (
                    "branch annotation #%d differs: exponent=%s has (line %s: %r), "
                    "exponent=%s has (line %s: %r)"
                    % (idx, reference_exponent, ref_line_no, ref_text,
                       exponent, other_line_no, other_text)
                )

    return True, ""


# Keywords that can precede a "(...) {" construct without being a real
# function definition (control-flow statements). Used to filter false
# positives out of the lightweight function-body scanner below.
_CONTROL_KEYWORDS = {
    "if", "while", "for", "switch", "catch", "else", "do", "return",
    "sizeof", "new", "delete", "namespace", "struct", "class", "union",
    "enum", "typedef", "template",
}

# Matches "<one or more type tokens> <name>(<params>) {" anywhere in the
# text, regardless of what immediately precedes it (comments, blank
# lines, previous statements). Requires at least one type token
# separate from the captured name, which naturally excludes bare
# control-flow constructs like "if (...) {" or "for (...) {" (they have
# only a single keyword before the parenthesis, not a
# type-token-plus-name pair) except for compound cases like
# "else if (...) {", which are filtered via _CONTROL_KEYWORDS below.
_FUNC_SIG_RE = re.compile(
    r'\b(?:[\w:\*&<>]+\s+)+(\w+)\s*\(([^{};()]*)\)\s*\{'
)


def _find_function_bodies(text):
    """
    Scans `text` for function definitions and returns a list of dicts:
      {'name': <function name>, 'brace_start': idx of '{',
       'body_start': idx just after '{', 'body_end': idx of matching '}'}

    This is a best-effort lexical scanner (not a full C++ parser) but is
    sufficient for the constrained, template-free, class-free HLS C/C++
    subset this benchmark targets.
    """
    results = []
    n = len(text)
    for m in _FUNC_SIG_RE.finditer(text):
        name = m.group(1)
        if name in _CONTROL_KEYWORDS:
            continue

        brace_start = m.end() - 1  # index of the opening '{'
        depth = 1
        i = brace_start + 1
        while i < n and depth > 0:
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            i += 1

        if depth != 0:
            # Unbalanced braces (malformed source); skip this candidate.
            continue

        body_end = i - 1  # index of the matching '}'
        results.append({
            "name": name,
            "brace_start": brace_start,
            "body_start": brace_start + 1,
            "body_end": body_end,
        })

    return results


# Matches a namespace-scope (potentially) mutable scalar variable
# declaration, e.g. "static uint32_t g_last_exponent = 0;" or
# "uint32_t leak_state;". The negative lookahead skips any declaration
# whose remaining text on the statement still contains the "const"
# keyword, since a const-qualified variable cannot later be assigned the
# exponent parameter's value inside modexp()'s body anyway.
_GLOBAL_VAR_RE = re.compile(
    r'(?:static\s+)?(?!(?:[^;]*\bconst\b))'
    r'(?:uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t|'
    r'int|unsigned(?:\s+int)?|long|short|char|bool)\s+'
    r'(\w+)\s*(?:=\s*[^;]*)?;'
)


def check_sr3():
    """
    SR3: static fail-on-presence scan of inputs/modexp_kernel.cpp for:

      (a) banned I/O calls that would leak the exponent (or any computed
          state) through an unintended output channel, and

      (b) the CWE-200 exponent-leakage pattern the repair notes
          identified as previously undetected: a file-scope (namespace-
          scope, non-const) mutable variable that is (i) assigned the
          raw `exponent` parameter's value somewhere inside modexp()'s
          body, and (ii) exposed outside the pinned return value via an
          additional externally-visible function (any function
          definition other than `modexp`) whose body returns that same
          variable.

    All three sub-conditions of (b) -- a qualifying global variable, an
    in-function assignment from `exponent`, and an accessor function
    returning it -- must co-occur for a FAIL, so a hardened submission
    that merely happens to declare an unrelated global or an unrelated
    helper function is never falsely rejected. Neither (a) nor (b) is
    present in the shipped baseline (which leaks nothing through any
    side channel other than SR1/SR2's timing/branch structure), so this
    check is expected to PASS on both the baseline and any correct
    hardened submission; it exists purely to catch a submission that
    reintroduces the exponent-leakage vulnerability.
    """
    if not os.path.isfile(_KERNEL_SRC):
        return False, "inputs/modexp_kernel.cpp not found"

    try:
        with open(_KERNEL_SRC, "r", errors="replace") as f:
            source_text = f.read()
    except OSError as e:
        return False, "could not read inputs/modexp_kernel.cpp: %s" % (e,)

    # Banned I/O calls that would leak the exponent (or any secret-derived
    # state) through an output channel other than the function's return
    # value.
    banned_io_tokens = ["printf(", "std::cout", "fprintf("]
    for token in banned_io_tokens:
        if token in source_text:
            return False, "banned I/O call '%s' found in inputs/modexp_kernel.cpp" % (token,)

    functions = _find_function_bodies(source_text)

    modexp_func = None
    other_funcs = []
    for func in functions:
        if func["name"] == "modexp":
            modexp_func = func
        else:
            other_funcs.append(func)

    if modexp_func is None or not other_funcs:
        # No extra externally-visible function exists at all, so the
        # required accessor half of the CWE-200 pattern cannot be
        # present; nothing further to check.
        return True, ""

    # Collect namespace-scope (file-scope) mutable variable declarations:
    # any match of _GLOBAL_VAR_RE whose declared-name position does not
    # fall inside any function's body span.
    global_var_names = []
    for m in _GLOBAL_VAR_RE.finditer(source_text):
        name_pos = m.start(1)
        inside_any_function = False
        for func in functions:
            if func["body_start"] <= name_pos <= func["body_end"]:
                inside_any_function = True
                break
        if not inside_any_function:
            global_var_names.append(m.group(1))

    if not global_var_names:
        return True, ""

    modexp_body = source_text[modexp_func["body_start"]:modexp_func["body_end"]]

    for varname in global_var_names:
        # Vulnerable pattern to catch: inside modexp()'s body, the
        # file-scope variable is assigned the raw exponent parameter
        # (optionally through a direct cast), e.g.
        #   "g_last_exponent = exponent;"
        #   "g_last_exponent = (uint32_t)exponent;"
        assign_re = re.compile(
            r'\b' + re.escape(varname) + r'\s*=\s*(?:\([^)]*\)\s*)?exponent\b'
        )
        if not assign_re.search(modexp_body):
            continue

        # Vulnerable pattern to catch: some additional externally-visible
        # function returns that same file-scope variable, e.g.
        #   "uint32_t get_last_exponent() { return g_last_exponent; }"
        return_re = re.compile(
            r'return\s*\(?\s*' + re.escape(varname) + r'\s*\)?\s*;'
        )
        for func in other_funcs:
            other_body = source_text[func["body_start"]:func["body_end"]]
            if return_re.search(other_body):
                return False, (
                    "exponent leaked via file-scope variable '%s' assigned inside modexp() "
                    "and exposed by accessor function '%s' in inputs/modexp_kernel.cpp"
                    % (varname, func["name"])
                )

    return True, ""