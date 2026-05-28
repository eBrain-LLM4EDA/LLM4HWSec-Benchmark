"""
Domain-specific security property verification.
Operates on AnalysisResult from ast_analyzer.py.

Supported domains (map to hidden_spec.security_domain):
  information_flow_tracking
  access_control
  side_channel
  resource_isolation
  generic
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ast_analyzer import AnalysisResult


# ---------------------------------------------------------------------------
# Property score record
# ---------------------------------------------------------------------------

@dataclass
class PropertyScore:
    name: str
    score: float
    max_score: float
    passed: bool
    evidence: str = ""


@dataclass
class VerifierReport:
    domain: str
    total_score: float              # 0–1
    property_scores: list[PropertyScore] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SUPPORTED_DOMAINS = frozenset({
    "information_flow_tracking",
    "access_control",
    "side_channel",
    "resource_isolation",
    "generic",
})


def verify(result: AnalysisResult, task_spec: dict[str, Any]) -> VerifierReport:
    """Run domain-specific property checks and return a VerifierReport."""
    domain = task_spec.get("hidden_spec", {}).get("security_domain", "generic")
    forbidden = task_spec.get("hidden_spec", {}).get("forbidden_patterns", [])

    if domain == "information_flow_tracking":
        report = _verify_ift(result)
    elif domain == "access_control":
        report = _verify_access_control(result)
    elif domain == "side_channel":
        report = _verify_side_channel(result)
    elif domain == "resource_isolation":
        report = _verify_resource_isolation(result)
    else:
        report = _verify_generic(result, forbidden)

    return report


# ---------------------------------------------------------------------------
# Domain checkers
# ---------------------------------------------------------------------------

def _verify_ift(result: AnalysisResult) -> VerifierReport:
    src = result.source_text
    props: list[PropertyScore] = []

    # 1. Taint type defined (struct with data + label fields) — 0.20
    if result.has_taint_types:
        props.append(PropertyScore("taint_type_defined", 0.20, 0.20, True,
                                   "struct with data+label found"))
    else:
        props.append(PropertyScore("taint_type_defined", 0.00, 0.20, False,
                                   "no taint struct (data+label) detected"))

    # 2. SECRET and PUBLIC label literals present — 0.20
    has_secret = bool(re.search(r"\bSECRET\b", src))
    has_public = bool(re.search(r"\bPUBLIC\b", src))
    if has_secret and has_public:
        props.append(PropertyScore("labels_at_inputs", 0.20, 0.20, True))
    else:
        missing = [l for l, ok in [("SECRET", has_secret), ("PUBLIC", has_public)] if not ok]
        props.append(PropertyScore("labels_at_inputs", 0.00, 0.20, False,
                                   f"missing: {missing}"))

    # 3. Taint propagation via operator overloads — 0.20
    fn_names = [f.name for f in result.functions]
    has_op = any("operator" in n for n in fn_names) or bool(
        re.search(r"operator\s*[\^&|+]", src)
    )
    props.append(PropertyScore("taint_propagates", 0.20 if has_op else 0.00, 0.20, has_op,
                               "operator overload found" if has_op else "no taint-propagating operator"))

    # 4. Taint through table lookups — 0.10
    has_taint_lookup = bool(re.search(r"\w+\[.*\.data\]", src)) and bool(re.search(r"\.label", src))
    props.append(PropertyScore("taint_through_lookup", 0.10 if has_taint_lookup else 0.00, 0.10,
                               has_taint_lookup))

    # 5. Explicit declassification function — 0.15
    declassif_kw = ("declassif", "authorize", "check_output", "release")
    has_declassif = any(kw in n.lower() for n in fn_names for kw in declassif_kw)
    props.append(PropertyScore("explicit_declassification", 0.15 if has_declassif else 0.00, 0.15,
                               has_declassif,
                               "declassification function found" if has_declassif else "no declassification function"))

    # 6. No untracked secret→output flows — 0.15
    has_debug_out = any("debug" in p or "diagnostic" in p for p in result.output_ports)
    has_flows = bool(result.secret_to_output_flows)
    safe = not has_debug_out and not has_flows
    props.append(PropertyScore("no_secret_output_flow", 0.15 if safe else 0.00, 0.15, safe,
                               "no debug output port" if safe else "potential secret→output flow"))

    return _make_report("information_flow_tracking", props)


def _verify_access_control(result: AnalysisResult) -> VerifierReport:
    src = result.source_text
    fn_names = [f.name for f in result.functions]
    props: list[PropertyScore] = []

    # 1. Policy function exists — 0.25
    policy_kw = ("privilege", "access", "authorize", "policy", "check_perm", "check_priv")
    has_policy_fn = any(kw in n.lower() for n in fn_names for kw in policy_kw)
    props.append(PropertyScore("policy_function_exists", 0.25 if has_policy_fn else 0.00, 0.25,
                               has_policy_fn))

    # 2. Policy called before access (policy fn in calls of top-level fn) — 0.25
    top_calls: list[str] = []
    for fi in result.functions:
        if fi.is_top_level:
            top_calls.extend(fi.calls)
    policy_fns = [n for n in fn_names for kw in policy_kw if kw in n.lower()]
    policy_called = any(pf in top_calls for pf in policy_fns)
    if not policy_fns and has_policy_fn:
        # Regex fallback: check if privilege check appears before any write
        policy_called = bool(re.search(
            r"(privilege_level|priv_level|access_level)\s*[=!<>].*?(?=\w+\s*=)",
            src, re.DOTALL
        ))
    props.append(PropertyScore("policy_called_before_access", 0.25 if policy_called else 0.00,
                               0.25, policy_called))

    # 3. Safe default on denial (zero output) — 0.20
    safe_default = bool(re.search(
        r"(?:rdata|out|result|data_out)\s*=\s*0\b|return\s+0\s*;", src
    ))
    props.append(PropertyScore("safe_default_on_denial", 0.20 if safe_default else 0.00, 0.20,
                               safe_default))

    # 4. Denial feedback signal — 0.15
    denial_signal = bool(re.search(
        r"\baccess_denied\b|\berror_flag\b|\bdenied\b|\breject\b|\bforbidden\b", src
    ))
    props.append(PropertyScore("denial_feedback", 0.15 if denial_signal else 0.00, 0.15,
                               denial_signal))

    # 5. No debug bypass — 0.15
    no_bypass = not bool(re.search(r"\bdebug_mode\b|\bbypass\b|\boverride\b", src, re.IGNORECASE))
    props.append(PropertyScore("no_debug_bypass", 0.15 if no_bypass else 0.00, 0.15, no_bypass,
                               "no debug bypass found" if no_bypass else "debug bypass keyword detected"))

    return _make_report("access_control", props)


def _verify_side_channel(result: AnalysisResult) -> VerifierReport:
    src = result.source_text
    props: list[PropertyScore] = []

    # 1. No early exit in any loop — 0.30 (most important)
    has_early_exit = any(l.has_early_exit for l in result.loops)
    if not has_early_exit:
        # Regex double-check for break/return inside loops
        has_early_exit = bool(re.search(
            r"\bfor\b[^{]*\{[^}]*\b(?:break|return)\b", src, re.DOTALL
        ))
    props.append(PropertyScore("no_early_exit", 0.30 if not has_early_exit else 0.00, 0.30,
                               not has_early_exit,
                               "no early exits in loops" if not has_early_exit else "early exit detected"))

    # 2. Fixed iteration counts — 0.20
    if result.loops:
        all_fixed = all(l.has_fixed_bound for l in result.loops)
    else:
        # No loops found by AST; check pragma-bounded loops via regex
        all_fixed = bool(re.search(r"#pragma\s+HLS\s+loop_bound\s+\d+", src, re.IGNORECASE))
    props.append(PropertyScore("fixed_iteration_count", 0.20 if all_fixed else 0.00, 0.20,
                               all_fixed))

    # 3. Constant ops per iteration (branchless accumulation) — 0.20
    branchless_acc = bool(re.search(r"\bacc\s*\|=|\bdiff\s*\|=|\bcswap\b|mask\s*&\s*\w", src))
    no_branches_in_loops = (
        bool(result.loops) and all(l.body_branch_count == 0 for l in result.loops)
    )
    const_ops = branchless_acc or no_branches_in_loops
    props.append(PropertyScore("constant_ops_per_iteration", 0.20 if const_ops else 0.00, 0.20,
                               const_ops))

    # 4. Branchless conditional patterns — 0.20
    branchless = bool(re.search(
        r"\bcswap\b|\|\s*=\s*\(|mask\s*&|\bselect\s*\(|\bternary\b|\?[^:]+:", src
    ))
    props.append(PropertyScore("branchless_conditionals", 0.20 if branchless else 0.00, 0.20,
                               branchless))

    # 5. HLS pipeline/unroll pragmas — 0.10
    has_pragma = any(
        p.kind.lower() in ("pipeline", "unroll") for p in result.pragmas
    )
    if not has_pragma:
        has_pragma = bool(re.search(r"#pragma\s+HLS\s+(pipeline|unroll)", src, re.IGNORECASE))
    props.append(PropertyScore("hls_timing_pragmas", 0.10 if has_pragma else 0.00, 0.10,
                               has_pragma))

    return _make_report("side_channel", props)


def _verify_resource_isolation(result: AnalysisResult) -> VerifierReport:
    src = result.source_text
    fn_names = [f.name for f in result.functions]
    props: list[PropertyScore] = []

    # 1. Separate static storage (≥2 static arrays) — 0.25
    static_arrays = [v for v in result.variables if v.is_static and v.is_array]
    if not static_arrays:
        # Regex fallback
        static_arrays_count = len(re.findall(r"\bstatic\b[^;]+\[[^\]]+\]", src))
    else:
        static_arrays_count = len(static_arrays)
    sep_storage = static_arrays_count >= 2
    props.append(PropertyScore("separate_static_storage", 0.25 if sep_storage else 0.00, 0.25,
                               sep_storage, f"{static_arrays_count} static arrays found"))

    # 2. Sanitize on domain transition — 0.25
    sanitize_kw = ("sanitize", "zeroize", "clear_buffer", "flush", "wipe")
    has_sanitize_fn = any(kw in n.lower() for n in fn_names for kw in sanitize_kw)
    has_memset_zero = bool(re.search(r"memset\s*\([^,]+,\s*0\s*,|= \{0\}|\[\w+\]\s*=\s*0\b", src))
    sanitized = has_sanitize_fn or has_memset_zero
    props.append(PropertyScore("sanitize_on_transition", 0.25 if sanitized else 0.00, 0.25,
                               sanitized))

    # 3. Stale data explicitly cleared — 0.20
    stale_cleared = bool(re.search(
        r"\[head\]\s*=\s*0|\[tail\]\s*=\s*0|buf\[.*?\]\s*=\s*0|\bdata\w*\[.*?\]\s*=\s*0", src
    ))
    if not stale_cleared:
        stale_cleared = bool(re.search(r"memset|bzero", src))
    props.append(PropertyScore("stale_data_cleared", 0.20 if stale_cleared else 0.00, 0.20,
                               stale_cleared))

    # 4. Cross-domain timing isolation — 0.15
    has_tdm = bool(re.search(r"current_slot|tdm_schedule|time_slot|round_robin", src))
    no_cross_timing = has_tdm or not any(l.has_early_exit for l in result.loops)
    props.append(PropertyScore("no_cross_domain_timing", 0.15 if no_cross_timing else 0.00, 0.15,
                               no_cross_timing))

    # 5. Explicit zeroization command/parameter — 0.15
    has_zeroize = any("zeroize" in n.lower() or "clear" in n.lower() for n in fn_names)
    if not has_zeroize:
        has_zeroize = bool(re.search(r"\bbool\s+zeroize\b|zeroize\s*=\s*true", src))
    props.append(PropertyScore("explicit_zeroization_command", 0.15 if has_zeroize else 0.00, 0.15,
                               has_zeroize))

    return _make_report("resource_isolation", props)


def _verify_generic(result: AnalysisResult, forbidden_patterns: list[str]) -> VerifierReport:
    """Fallback: score based on absence of forbidden patterns + no synthesis violations."""
    src = result.source_text
    props: list[PropertyScore] = []

    n_violations = len(result.synthesis_violations)
    props.append(PropertyScore("no_synthesis_violations",
                               1.0 if n_violations == 0 else 0.0, 1.0,
                               n_violations == 0,
                               f"{n_violations} synthesis violations"))

    if forbidden_patterns:
        violated = [p for p in forbidden_patterns if _pattern_found(src, p)]
        frac = 1.0 - len(violated) / len(forbidden_patterns)
        props.append(PropertyScore("forbidden_patterns_absent", frac, 1.0,
                                   frac == 1.0,
                                   f"{len(violated)}/{len(forbidden_patterns)} forbidden patterns found"))

    return _make_report("generic", props)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(domain: str, props: list[PropertyScore]) -> VerifierReport:
    total_max = sum(p.max_score for p in props) or 1.0
    total_score = sum(p.score for p in props) / total_max
    return VerifierReport(domain=domain, total_score=round(total_score, 4),
                          property_scores=props)


def _pattern_found(source: str, pattern: str) -> bool:
    try:
        return bool(re.search(pattern, source, re.IGNORECASE))
    except re.error:
        return pattern.lower() in source.lower()