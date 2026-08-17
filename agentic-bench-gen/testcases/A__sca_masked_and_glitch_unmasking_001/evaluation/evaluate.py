#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grades submission/vulnerability_report.json against the input artifacts:
  inputs/masked_and.v
  inputs/fault_model.json
  inputs/design_brief.md
  inputs/sim_trace.vcd.txt

Prints one [TEST] PASS/FAIL line per requirement id (FR1-FR4, SR1-SR3).
Exits 0 iff all requirements pass.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")

REQUIRED_INPUT_FILES = [
    "masked_and.v",
    "fault_model.json",
    "design_brief.md",
    "sim_trace.vcd.txt",
]

RESULTS = []  # list of (req_id, passed_bool, reason_str)


def record(req_id, passed, reason=""):
    RESULTS.append((req_id, passed, reason))
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


# ---------------------------------------------------------------------------
# File loading helpers
# ---------------------------------------------------------------------------

def load_inputs():
    contents = {}
    for fname in REQUIRED_INPUT_FILES:
        path = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(path):
            print("[TEST] FAIL: SETUP: %s not found" % path)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            contents[fname] = f.read()
    return contents


def load_submission():
    """
    Attempt to load and parse the submission file.

    Returns a tuple (data, parse_ok, parse_error_reason):
      - If the file is missing entirely, this is treated as a SETUP failure
        (infrastructure problem) and the script exits immediately, matching
        the contract's SETUP semantics for missing harness/answer files.
      - If the file exists but is not valid JSON (or does not decode as a
        JSON object), parse_ok is False and data is an empty dict {} so
        that every downstream requirement check can still run safely via
        .get()-based access and produce a clean FAIL rather than crashing.
      - If the file parses successfully, parse_ok is True and data is the
        parsed JSON value (which might not even be a dict, e.g. a JSON
        array or scalar; downstream checks guard against that too).
    """
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_PATH)
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        # Could not even read the file as text/UTF-8; infrastructure-level
        # but we still want FR1 to fail cleanly rather than exiting via
        # SETUP, since the file itself does exist.
        return {}, False, "could not read %s: %s" % (SUBMISSION_PATH, e)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {}, False, "%s is not valid JSON: %s" % (SUBMISSION_PATH, e)
    except Exception as e:
        return {}, False, "%s failed to parse: %s" % (SUBMISSION_PATH, e)

    if not isinstance(data, dict):
        return {}, False, (
            "%s parsed as JSON but top-level value is not an object (got %s)"
            % (SUBMISSION_PATH, type(data).__name__)
        )

    return data, True, ""


# ---------------------------------------------------------------------------
# Verilog netlist parsing helpers
# ---------------------------------------------------------------------------

IDENT_RE = r"[A-Za-z_][A-Za-z0-9_$]*"


def parse_declared_nets(verilog_src):
    """
    Collect identifiers declared as wire/reg/input/output (with optional
    wire/reg/logic qualifiers and bit-width ranges), plus identifiers
    appearing on the LHS of assign statements.
    """
    names = set()

    # port/declaration lines: input/output/wire/reg [range] name(, name)*;
    decl_pattern = re.compile(
        r"\b(?:input|output|wire|reg)\b"
        r"(?:\s+(?:wire|reg|logic))?"
        r"(?:\s*\[\s*[^\]]+\s*\])?"
        r"\s+([A-Za-z_][A-Za-z0-9_$,\s]*)\s*;",
        re.MULTILINE,
    )
    for m in decl_pattern.finditer(verilog_src):
        chunk = m.group(1)
        for tok in chunk.split(","):
            tok = tok.strip()
            tok = re.sub(r"\[.*\]", "", tok).strip()
            if re.match(r"^%s$" % IDENT_RE, tok):
                names.add(tok)

    # assign LHS identifiers: assign <name> = ...
    assign_pattern = re.compile(
        r"\bassign\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=", re.MULTILINE
    )
    for m in assign_pattern.finditer(verilog_src):
        names.add(m.group(1))

    return names


def parse_assign_statements(verilog_src):
    """
    Return list of (lhs, rhs_expr_str) tuples for each `assign lhs = rhs;`
    statement found in the source.
    """
    stmts = []
    pattern = re.compile(
        r"\bassign\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*(.*?);", re.DOTALL
    )
    for m in pattern.finditer(verilog_src):
        lhs = m.group(1).strip()
        rhs = m.group(2).strip()
        # collapse whitespace/newlines in rhs
        rhs = re.sub(r"\s+", " ", rhs)
        stmts.append((lhs, rhs))
    return stmts


def rhs_identifiers(rhs_expr):
    return set(re.findall(IDENT_RE, rhs_expr))


def normalize_and_operands(rhs_expr):
    """
    If rhs_expr is a simple bitwise-AND of two identifiers (possibly with
    surrounding parens/whitespace), return a frozenset of the two operand
    names. Otherwise return None.
    """
    expr = rhs_expr.strip()
    # strip a single layer of enclosing parens if fully wrapping
    while expr.startswith("(") and expr.endswith(")"):
        # only strip if parens are balanced across whole expr
        depth = 0
        balanced_whole = True
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(expr) - 1:
                    balanced_whole = False
                    break
        if balanced_whole:
            expr = expr[1:-1].strip()
        else:
            break

    m = re.match(r"^(%s)\s*&\s*(%s)$" % (IDENT_RE, IDENT_RE), expr)
    if not m:
        return None
    return frozenset([m.group(1), m.group(2)])


def find_cross_and_same_terms(assign_stmts):
    """
    Dynamically identify, from the parsed assign statements, which LHS
    nets correspond to:
      - same-share AND terms: a0&b0 or a1&b1 (operand-index-matched)
      - cross-share AND terms: a0&b1 or a1&b0 (operand-index-mismatched)
    Returns dict with keys 'same' -> list of lhs names, 'cross' -> list of
    lhs names, based purely on structural pattern matching against the
    fixed port names a0,a1,b0,b1 that are part of the pinned public
    interface (masked_and ports), not on baseline-specific internal names.
    """
    same_terms = []
    cross_terms = []
    for lhs, rhs in assign_stmts:
        operands = normalize_and_operands(rhs)
        if operands is None:
            continue
        ops = sorted(operands)
        if len(ops) != 2:
            continue
        a_ops = [o for o in ops if o.startswith("a")]
        b_ops = [o for o in ops if o.startswith("b")]
        if len(a_ops) != 1 or len(b_ops) != 1:
            continue
        a_name, b_name = a_ops[0], b_ops[0]
        a_idx_m = re.match(r"^a(\d+)$", a_name)
        b_idx_m = re.match(r"^b(\d+)$", b_name)
        if not a_idx_m or not b_idx_m:
            continue
        a_idx, b_idx = a_idx_m.group(1), b_idx_m.group(1)
        if a_idx == b_idx:
            same_terms.append(lhs)
        else:
            cross_terms.append(lhs)
    return {"same": same_terms, "cross": cross_terms}


def build_dependency_graph(assign_stmts):
    """
    Build a dict: lhs_name -> set(identifiers referenced on rhs).
    """
    graph = {}
    for lhs, rhs in assign_stmts:
        graph[lhs] = rhs_identifiers(rhs)
    return graph


def transitive_dependencies(graph, start):
    """
    Return the set of all identifiers reachable from `start` by following
    the dependency graph (i.e. everything start's value ultimately depends
    on, including start's immediate rhs identifiers and their rhs chains).
    """
    visited = set()
    frontier = [start]
    while frontier:
        node = frontier.pop()
        if node in visited:
            continue
        visited.add(node)
        deps = graph.get(node, set())
        for d in deps:
            if d not in visited:
                frontier.append(d)
    visited.discard(start)
    return visited


# ---------------------------------------------------------------------------
# VCD-like plain text trace parser
# ---------------------------------------------------------------------------

def parse_trace_table(trace_text):
    """
    Parse the plain-text stimulus/response table format used in
    sim_trace.vcd.txt:
        time a0 a1 b0 b1 r q0 q1
        0 0 0 0 0 0 0 0
        ...
    Returns list of dicts with keys time,a0,a1,b0,b1,r,q0,q1 (ints).
    Lines starting with '//' or that are not all-numeric-token rows with
    the right column count are skipped.
    """
    rows = []
    header_cols = None
    for line in trace_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        tokens = stripped.split()
        if header_cols is None and tokens and tokens[0] == "time":
            header_cols = tokens
            continue
        if header_cols is None:
            continue
        if len(tokens) != len(header_cols):
            continue
        if not all(re.match(r"^-?\d+$", t) for t in tokens):
            continue
        row = {}
        for col_name, val in zip(header_cols, tokens):
            row[col_name] = int(val)
        rows.append(row)
    return rows


def verify_algebraic_invariant(rows):
    """
    Given parsed rows with keys a0,a1,b0,b1,r,q0,q1, verify that
    q0^q1 == (a0^a1)&(b0^b1) for every row. Returns (all_ok, num_checked).
    """
    if not rows:
        return False, 0
    all_ok = True
    checked = 0
    for row in rows:
        required = ["a0", "a1", "b0", "b1", "q0", "q1"]
        if not all(k in row for k in required):
            continue
        expected = (row["a0"] ^ row["a1"]) & (row["b0"] ^ row["b1"])
        actual = row["q0"] ^ row["q1"]
        checked += 1
        if expected != actual:
            all_ok = False
    return (all_ok and checked > 0), checked


# ---------------------------------------------------------------------------
# iverilog / vvp cross-check (optional, best-effort)
# ---------------------------------------------------------------------------

def toolchain_available():
    for tool in ("iverilog", "vvp"):
        found = False
        for d in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(d, tool)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                found = True
                break
        if not found:
            return False
    return True


def run_iverilog_crosscheck(masked_and_path, tb_path, timeout=20):
    """
    Compile and run inputs/masked_and.v + evaluation/tb_masked_and.v via
    iverilog/vvp. Returns (success_bool, parsed_vec_lines) where
    parsed_vec_lines is a list of dicts derived from lines of the form:
        VEC <idx> <a0><a1><b0><b1><r> <q0><q1>
    On any failure (compile error, timeout, tool missing), returns
    (False, []).
    """
    if not toolchain_available():
        return False, []

    tmpdir = tempfile.mkdtemp(prefix="sca_eval_")
    sim_out = os.path.join(tmpdir, "sim.vvp")
    try:
        compile_cmd = ["iverilog", "-g2012", "-o", sim_out, masked_and_path, tb_path]
        proc = subprocess.run(
            compile_cmd, capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode != 0:
            return False, []

        run_cmd = ["vvp", sim_out]
        proc2 = subprocess.run(
            run_cmd, capture_output=True, text=True, timeout=timeout
        )
        if proc2.returncode != 0:
            return False, []

        vec_lines = []
        pattern = re.compile(
            r"^VEC\s+(\d+)\s+([01])([01])([01])([01])([01])\s+([01])([01])\s*$"
        )
        for line in proc2.stdout.splitlines():
            m = pattern.match(line.strip())
            if m:
                idx = int(m.group(1))
                a0, a1, b0, b1, r = (int(m.group(i)) for i in range(2, 7))
                q0, q1 = int(m.group(7)), int(m.group(8))
                vec_lines.append(
                    {
                        "idx": idx,
                        "a0": a0,
                        "a1": a1,
                        "b0": b0,
                        "b1": b1,
                        "r": r,
                        "q0": q0,
                        "q1": q1,
                    }
                )
        return True, vec_lines
    except Exception:
        return False, []
    finally:
        try:
            for root, dirs, files in os.walk(tmpdir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(tmpdir)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Field / schema helpers
# ---------------------------------------------------------------------------

def is_string(x):
    return isinstance(x, str)


def is_bool(x):
    return isinstance(x, bool)


def is_list_of_str(x):
    return isinstance(x, list) and all(isinstance(e, str) for e in x)


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# Requirement checks
# ---------------------------------------------------------------------------

def check_FR1(submission, parse_ok, parse_error_reason):
    if not parse_ok:
        return False, parse_error_reason

    missing = []
    type_errors = []

    if "suspect_nets" not in submission:
        missing.append("suspect_nets")
    elif not is_list_of_str(submission["suspect_nets"]):
        type_errors.append("suspect_nets must be list[str]")

    if "algebraic_masking_correct" not in submission:
        missing.append("algebraic_masking_correct")
    elif not is_bool(submission["algebraic_masking_correct"]):
        type_errors.append("algebraic_masking_correct must be bool")

    if "vulnerability_summary" not in submission:
        missing.append("vulnerability_summary")
    elif not is_string(submission["vulnerability_summary"]):
        type_errors.append("vulnerability_summary must be str")

    if "hardening_proposal" not in submission:
        missing.append("hardening_proposal")
    else:
        hp = submission["hardening_proposal"]
        if not isinstance(hp, dict):
            type_errors.append("hardening_proposal must be an object")
        else:
            if "registers_to_add" not in hp:
                missing.append("hardening_proposal.registers_to_add")
            elif not is_list_of_str(hp["registers_to_add"]):
                type_errors.append("hardening_proposal.registers_to_add must be list[str]")
            if "placement_description" not in hp:
                missing.append("hardening_proposal.placement_description")
            elif not is_string(hp["placement_description"]):
                type_errors.append("hardening_proposal.placement_description must be str")

    if "confidence" not in submission:
        missing.append("confidence")
    elif not is_number(submission["confidence"]):
        type_errors.append("confidence must be a number")
    elif not (0.0 <= float(submission["confidence"]) <= 1.0):
        type_errors.append("confidence must be within [0.0, 1.0]")

    if missing or type_errors:
        reasons = []
        if missing:
            reasons.append("missing fields: %s" % ", ".join(missing))
        if type_errors:
            reasons.append("type errors: %s" % "; ".join(type_errors))
        return False, "; ".join(reasons)
    return True, ""


def check_FR2(submission, valid_nets):
    suspects = submission.get("suspect_nets")
    if not is_list_of_str(suspects):
        return False, "suspect_nets missing or not a list of strings"
    if len(suspects) == 0:
        return False, "suspect_nets is empty"
    bad = [s for s in suspects if s not in valid_nets]
    if bad:
        return False, "suspect_nets contains names not found in inputs/masked_and.v: %s" % bad
    return True, ""


def check_FR3(submission, trace_rows, masked_and_path, tb_path):
    claimed = submission.get("algebraic_masking_correct")
    if not is_bool(claimed):
        return False, "algebraic_masking_correct missing or not boolean"

    if claimed is not True:
        return False, "algebraic_masking_correct is not true"

    # Cross-check: try iverilog/vvp simulation first; fall back to the
    # rows parsed directly from sim_trace.vcd.txt.
    sim_ok, sim_vecs = False, []
    if os.path.isfile(tb_path):
        sim_ok, sim_vecs = run_iverilog_crosscheck(masked_and_path, tb_path)

    if sim_ok and sim_vecs:
        all_ok, checked = verify_algebraic_invariant(sim_vecs)
        if checked == 0:
            # fall back to trace file rows
            all_ok, checked = verify_algebraic_invariant(trace_rows)
    else:
        all_ok, checked = verify_algebraic_invariant(trace_rows)

    if checked == 0:
        return False, "could not verify algebraic invariant from any available vectors"
    if not all_ok:
        return False, "algebraic invariant q0^q1==(a0^a1)&(b0^b1) failed on cross-check vectors"

    return True, ""


NORMALIZED_EQUIVALENTS = {"a0", "a1", "b0", "b1", "r", "q0", "q1"}


def check_FR4(submission, valid_nets):
    hp = submission.get("hardening_proposal")
    if not isinstance(hp, dict):
        return False, "hardening_proposal missing or not an object"
    regs = hp.get("registers_to_add")
    if not is_list_of_str(regs):
        return False, "hardening_proposal.registers_to_add missing or not list[str]"
    if len(regs) == 0:
        return False, "registers_to_add is empty"

    acceptable = valid_nets | NORMALIZED_EQUIVALENTS
    bad = [r for r in regs if r not in acceptable]
    if bad:
        return False, "registers_to_add contains names not traceable to inputs/masked_and.v: %s" % bad
    return True, ""


GLITCH_KEYWORDS = [
    "glitch",
    "transient",
    "timing",
    "settle",
    "propagat",
    "combinational",
    "unregistered",
    "race",
    "arrival",
    "delay",
    "skew",
    "clock cycle",
]

ALGEBRAIC_FLAW_PHRASES = [
    "masking is incorrect",
    "masking is wrong",
    "algebraically flawed",
    "algebraically incorrect",
    "wrong and",
    "incorrect and computation",
    "the masking scheme is mathematically wrong",
    "the algebra is wrong",
    "formula is incorrect",
    "formula is wrong",
]


def check_SR1(submission):
    if submission.get("algebraic_masking_correct") is not True:
        return False, "algebraic_masking_correct is not true"

    summary = submission.get("vulnerability_summary")
    if not is_string(summary):
        return False, "vulnerability_summary missing or not a string"
    if len(summary) < 40:
        return False, "vulnerability_summary shorter than 40 characters"

    lower = summary.lower()

    for phrase in ALGEBRAIC_FLAW_PHRASES:
        if phrase in lower:
            return False, "vulnerability_summary incorrectly claims the masking algebra itself is flawed"

    matched = [kw for kw in GLITCH_KEYWORDS if kw in lower]
    if not matched:
        return False, (
            "vulnerability_summary does not describe the glitch/timing/"
            "unregistered-combinational-recombination mechanism"
        )
    return True, ""


def check_SR2(submission, assign_stmts):
    terms = find_cross_and_same_terms(assign_stmts)
    cross_terms = terms["cross"]
    if len(cross_terms) < 2:
        return False, (
            "could not structurally identify two distinct cross-share AND "
            "terms in inputs/masked_and.v to validate against"
        )

    suspects = submission.get("suspect_nets")
    if not is_list_of_str(suspects) or len(suspects) == 0:
        return False, "suspect_nets missing or empty"

    suspects_set = set(suspects)
    missing_cross = [c for c in cross_terms if c not in suspects_set]
    if missing_cross:
        return False, (
            "suspect_nets does not name all cross-share AND term nets "
            "identified from the netlist dataflow: missing %s" % missing_cross
        )
    return True, ""


def check_SR3(submission, assign_stmts, graph, terms):
    hp = submission.get("hardening_proposal")
    if not isinstance(hp, dict):
        return False, "hardening_proposal missing or not an object"
    regs = hp.get("registers_to_add")
    if not is_list_of_str(regs) or len(regs) == 0:
        return False, "registers_to_add missing or empty"

    placement_desc = hp.get("placement_description")
    if not is_string(placement_desc) or len(placement_desc) < 40:
        return False, "placement_description missing or shorter than 40 characters"

    # Identify the output ports (final combination points).
    output_ports = {"q0", "q1"}

    # Identify internal partial-product / mask nets that feed the outputs:
    # same-term nets, cross-term nets, and the mask r.
    internal_targets = set(terms["same"]) | set(terms["cross"]) | {"r"}
    # Also allow the four input shares as an equally valid boundary
    # (registering a0,a1,b0,b1,r at the gadget's input boundary).
    input_shares = {"a0", "a1", "b0", "b1", "r"}

    acceptable_targets = internal_targets | input_shares

    regs_set = set(regs)

    # Fail if every listed register resolves only to output ports (i.e.
    # nothing outside output_ports was named).
    non_output_regs = [r for r in regs_set if r not in output_ports]
    if not non_output_regs:
        return False, (
            "hardening_proposal only registers final output ports (q0/q1); "
            "the internal cross-share combination remains unregistered"
        )

    # At least one non-output register must correspond to an internal
    # partial-product/mask net or an input share.
    matched = [r for r in non_output_regs if r in acceptable_targets]
    if not matched:
        return False, (
            "hardening_proposal.registers_to_add does not name any signal "
            "traceable to the share-domain intermediate nets or input "
            "shares that feed the cross/same-term XOR combination stage"
        )

    return True, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    inputs = load_inputs()
    submission, parse_ok, parse_error_reason = load_submission()

    masked_and_src = inputs["masked_and.v"]
    trace_text = inputs["sim_trace.vcd.txt"]
    # fault_model.json and design_brief.md are loaded for completeness /
    # potential future use, though not directly parsed for grading logic.
    _ = inputs["fault_model.json"]
    _ = inputs["design_brief.md"]

    valid_nets = parse_declared_nets(masked_and_src)
    assign_stmts = parse_assign_statements(masked_and_src)
    graph = build_dependency_graph(assign_stmts)
    terms = find_cross_and_same_terms(assign_stmts)
    trace_rows = parse_trace_table(trace_text)

    masked_and_path = os.path.join(INPUTS_DIR, "masked_and.v")
    tb_path = os.path.join("evaluation", "tb_masked_and.v")

    # FR1: schema/type presence, and (new) explicit handling of malformed
    # or unparseable submission JSON. This must never raise -- any parse
    # failure was already captured by load_submission() above.
    ok, reason = check_FR1(submission, parse_ok, parse_error_reason)
    record("FR1", ok, reason)

    # From here on, `submission` is guaranteed to be a dict (possibly {}
    # if parsing failed), so every remaining check can safely use .get()
    # without risking an exception/traceback.

    # FR2
    ok, reason = check_FR2(submission, valid_nets)
    record("FR2", ok, reason)

    # FR3
    ok, reason = check_FR3(submission, trace_rows, masked_and_path, tb_path)
    record("FR3", ok, reason)

    # FR4
    ok, reason = check_FR4(submission, valid_nets)
    record("FR4", ok, reason)

    # SR1
    ok, reason = check_SR1(submission)
    record("SR1", ok, reason)

    # SR2
    ok, reason = check_SR2(submission, assign_stmts)
    record("SR2", ok, reason)

    # SR3
    ok, reason = check_SR3(submission, assign_stmts, graph, terms)
    record("SR3", ok, reason)

    any_fail = any(not passed for (_, passed, _) in RESULTS)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()