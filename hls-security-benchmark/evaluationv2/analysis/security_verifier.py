#!/usr/bin/env python3
"""
Security Property Verifier for HLS Security Benchmark.

Uses AST analysis results (from ast_analyzer.py) to verify security properties
with structural analysis instead of regex matching.

Replaces: _score_ift(), _score_access_control(), _score_side_channel(),
          _score_resource_isolation() in the original run_evaluation.py.
"""

import os
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass

try:
    from analysis.ast_analyzer import ASTAnalyzer, AnalysisResult
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from analysis.ast_analyzer import ASTAnalyzer, AnalysisResult


@dataclass
class PropertyScore:
    score: float
    max_score: float
    description: str
    passed: bool


class SecurityVerifier:
    """
    Verifies security properties using AST analysis results.
    Dispatches to domain-specific verifiers based on metadata.
    """

    def __init__(self, ast: ASTAnalyzer, metadata: dict):
        self.ast = ast
        self.metadata = metadata
        self.analysis = ast.get_analysis()
        self.domain = metadata.get("security_domain", "")
        self.properties: List[PropertyScore] = []

    def score(self) -> float:
        """Run domain-specific verification and return total score (0.0–1.0)."""
        self.properties = []

        if self.domain == "information_flow_tracking":
            self._verify_ift()
        elif self.domain == "access_control":
            self._verify_access_control()
        elif self.domain == "side_channel":
            self._verify_side_channel()
        elif self.domain == "resource_isolation":
            self._verify_resource_isolation()

        if not self.properties:
            return 0.0

        total = sum(p.score for p in self.properties)
        max_total = sum(p.max_score for p in self.properties)
        return round(total / max_total, 3) if max_total > 0 else 0.0

    def score_completeness(self, spec_path: str) -> float:
        """Score how completely the security spec properties are addressed."""
        if not os.path.exists(spec_path):
            return 0.0

        with open(spec_path, "r") as f:
            spec = f.read()

        # Extract required properties from spec
        properties = re.findall(r"[-•]\s*(.+)", spec)
        if not properties:
            return 0.5

        addressed = 0
        for prop in properties:
            if self._is_property_addressed(prop):
                addressed += 1

        return round(addressed / len(properties), 3)

    def _is_property_addressed(self, property_text: str) -> bool:
        """
        Check if a security property from the spec is addressed in the code.
        Uses AST analysis instead of keyword matching.
        """
        text_lower = property_text.lower()

        # --- Check structural properties via AST ---

        # "No debug/diagnostic port"
        if any(kw in text_lower for kw in ("no debug", "no diagnostic", "remove debug")):
            # Verify no output port has debug/diagnostic in its name
            return not any(
                "debug" in p.lower() or "diagnostic" in p.lower()
                for p in self.analysis.output_ports
            )

        # "Taint/label tracking"
        if any(kw in text_lower for kw in ("taint", "label", "information flow")):
            return self.analysis.has_taint_types

        # "Secret/public labels"
        if "secret" in text_lower and "public" in text_lower:
            return self.analysis.has_taint_types

        # "No early exit" / "fixed iteration"
        if any(kw in text_lower for kw in ("no early exit", "fixed", "constant")):
            return not any(l.has_early_exit for l in self.analysis.loops)

        # "Access control" / "privilege"
        if any(kw in text_lower for kw in ("access control", "privilege", "authorization")):
            return any(
                any(kw in f.name.lower()
                    for kw in ("privilege", "access", "authorize", "policy"))
                for f in self.analysis.functions
            )

        # "Zeroize" / "clear" / "sanitize"
        if any(kw in text_lower for kw in ("zeroize", "clear", "sanitize", "overwrite")):
            return any(
                any(kw in f.name.lower()
                    for kw in ("zeroize", "sanitize", "clear"))
                for f in self.analysis.functions
            )

        # "Separate storage" / "isolated"
        if any(kw in text_lower for kw in ("separate", "isolat")):
            static_arrays = [
                v for v in self.analysis.variables
                if v.is_static and v.is_array
            ]
            return len(static_arrays) >= 2

        # Fallback: keyword presence in function/variable names
        keywords = [w for w in re.findall(r"\w{4,}", text_lower)][:3]
        all_names = (
            [f.name.lower() for f in self.analysis.functions]
            + [v.name.lower() for v in self.analysis.variables]
        )
        return any(kw in name for kw in keywords for name in all_names)

    # ------------------------------------------------------------------
    # Domain: Information Flow Tracking
    # ------------------------------------------------------------------

    def _verify_ift(self):
        """Verify information flow tracking properties via AST."""

        # P1: Taint-tracked data type exists (struct with data+label fields)
        has_taint = self.analysis.has_taint_types
        self.properties.append(PropertyScore(
            score=0.2 if has_taint else 0.0,
            max_score=0.2,
            description="Taint-tracked data type defined",
            passed=has_taint,
        ))

        # P2: Security labels assigned at inputs
        # Check if any function assigns SECRET label to a parameter-derived var
        source = self._read_source()
        labels_assigned = (
            "SECRET" in source and "PUBLIC" in source
            and has_taint  # labels without taint type are meaningless
        )
        self.properties.append(PropertyScore(
            score=0.2 if labels_assigned else 0.0,
            max_score=0.2,
            description="Security labels assigned at inputs",
            passed=labels_assigned,
        ))

        # P3: Taint propagates through operators
        # Check if taint type has operator overloads
        has_operator_overloads = False
        if has_taint:
            # Look for operator^ or operator+ methods in taint types
            for func in self.analysis.functions:
                if func.name.startswith("operator"):
                    has_operator_overloads = True
                    break
            # Also check via source (operator overloads inside structs)
            if not has_operator_overloads:
                has_operator_overloads = bool(
                    re.search(r"operator[+\-\^|&]", source)
                )

        self.properties.append(PropertyScore(
            score=0.2 if has_operator_overloads else 0.0,
            max_score=0.2,
            description="Taint propagation through operators",
            passed=has_operator_overloads,
        ))

        # P4: Taint propagates through lookups (S-box)
        # Check if S-box result inherits the label of the index
        lookup_propagates = False
        if has_taint:
            # Look for pattern: sbox[x.data] with label = x.label
            lookup_propagates = bool(
                re.search(r"sbox\[.*\.data\]", source)
                and re.search(r"\.label", source)
            )
        self.properties.append(PropertyScore(
            score=0.1 if lookup_propagates else 0.0,
            max_score=0.1,
            description="Taint propagation through lookups",
            passed=lookup_propagates,
        ))

        # P5: Declassification is explicit
        has_declass = self.analysis.has_declassification or bool(
            re.search(r"declassif|authorized.*output|intentional.*release",
                      source, re.IGNORECASE)
        )
        self.properties.append(PropertyScore(
            score=0.15 if has_declass else 0.0,
            max_score=0.15,
            description="Explicit declassification",
            passed=has_declass,
        ))

        # P6: No untracked secret-to-output flows
        # Check that no output port directly receives a secret variable
        # WITHOUT going through a taint-tracked type
        no_leaks = len(self.analysis.secret_to_output_flows) == 0
        # Also verify no debug ports exist
        no_debug = not any(
            "debug" in p.lower() or "internal_state" in p.lower()
            for p in self.analysis.output_ports
        )
        both_ok = no_leaks and no_debug
        self.properties.append(PropertyScore(
            score=0.15 if both_ok else 0.0,
            max_score=0.15,
            description="No untracked secret-to-output flows",
            passed=both_ok,
        ))

    # ------------------------------------------------------------------
    # Domain: Access Control
    # ------------------------------------------------------------------

    def _verify_access_control(self):
        source = self._read_source()

        # P1: Access policy function exists (by AST — real function, not comment)
        policy_funcs = [
            f for f in self.analysis.functions
            if any(kw in f.name.lower()
                   for kw in ("privilege", "access", "authorize",
                              "policy", "channel_authorized"))
        ]
        self.properties.append(PropertyScore(
            score=0.25 if policy_funcs else 0.0,
            max_score=0.25,
            description="Access policy function exists",
            passed=bool(policy_funcs),
        ))

        # P2: Policy function is called before memory access
        # Check that top-level function calls a policy function
        policy_names = {f.name for f in policy_funcs}
        top_funcs = [f for f in self.analysis.functions if f.is_top_level]
        policy_called = any(
            any(call in policy_names for call in f.calls)
            for f in top_funcs
        )
        self.properties.append(PropertyScore(
            score=0.25 if policy_called else 0.0,
            max_score=0.25,
            description="Policy checked before memory access",
            passed=policy_called,
        ))

        # P3: Denied access returns safe default
        # Look for "rdata = 0" or "resp.rdata = 0" in denial path
        safe_default = bool(re.search(r"rdata\s*=\s*0", source))
        self.properties.append(PropertyScore(
            score=0.2 if safe_default else 0.0,
            max_score=0.2,
            description="Safe default (zero) on denial",
            passed=safe_default,
        ))

        # P4: Access denied feedback in response struct
        # Check for access_denied field in any struct via AST
        has_denied_field = any(
            v.name == "access_denied"
            for v in self.analysis.variables
        )
        # Also check struct field declarations in source
        if not has_denied_field:
            has_denied_field = bool(re.search(r"bool\s+access_denied", source))
        self.properties.append(PropertyScore(
            score=0.15 if has_denied_field else 0.0,
            max_score=0.15,
            description="Access denied feedback in response",
            passed=has_denied_field,
        ))

        # P5: No debug mode bypass
        no_debug = "debug_mode" not in source
        self.properties.append(PropertyScore(
            score=0.15 if no_debug else 0.0,
            max_score=0.15,
            description="No debug mode bypass",
            passed=no_debug,
        ))

    # ------------------------------------------------------------------
    # Domain: Side Channel
    # ------------------------------------------------------------------

    def _verify_side_channel(self):
        source = self._read_source()

        # P1: No early exit in loops (AST-verified)
        loops_with_exit = [l for l in self.analysis.loops if l.has_early_exit]
        no_early_exit = len(loops_with_exit) == 0
        self.properties.append(PropertyScore(
            score=0.3 if no_early_exit else 0.0,
            max_score=0.3,
            description="No early exit (break/return) in loops",
            passed=no_early_exit,
        ))

        # P2: Fixed iteration count (AST-verified)
        all_fixed = all(l.has_fixed_bound for l in self.analysis.loops) \
                    and len(self.analysis.loops) > 0
        self.properties.append(PropertyScore(
            score=0.2 if all_fixed else 0.0,
            max_score=0.2,
            description="All loops have fixed iteration count",
            passed=all_fixed,
        ))

        # P3: Constant operations per iteration
        # Check for Montgomery ladder (cswap) or OR-accumulate pattern
        has_constant_ops = bool(
            re.search(r"\bcswap\b", source)
            or re.search(r"diff\s*\|=", source)
        )
        # Also check: all loops have 0 branches (no if inside loop body)
        if not has_constant_ops:
            has_constant_ops = all(
                l.body_branch_count == 0
                for l in self.analysis.loops
            )
        self.properties.append(PropertyScore(
            score=0.2 if has_constant_ops else 0.0,
            max_score=0.2,
            description="Constant operations per loop iteration",
            passed=has_constant_ops,
        ))

        # P4: Branchless conditional operations
        has_branchless = bool(
            re.search(r"\bcswap\b", source)        # cswap function
            or re.search(r"\|=\s*\(", source)       # OR-accumulate
            or re.search(r"mask\s*[&^]", source)    # mask-based select
        )
        self.properties.append(PropertyScore(
            score=0.2 if has_branchless else 0.0,
            max_score=0.2,
            description="Branchless conditional operations",
            passed=has_branchless,
        ))

        # P5: HLS pragmas enforce fixed pipeline
        has_pipeline = any(
            p.kind in ("UNROLL", "PIPELINE")
            for p in self.analysis.pragmas
        )
        self.properties.append(PropertyScore(
            score=0.1 if has_pipeline else 0.0,
            max_score=0.1,
            description="HLS pragmas enforce fixed pipeline",
            passed=has_pipeline,
        ))

    # ------------------------------------------------------------------
    # Domain: Resource Isolation
    # ------------------------------------------------------------------

    def _verify_resource_isolation(self):
        source = self._read_source()

        # P1: Separate storage arrays (AST-verified)
        static_arrays = [
            v for v in self.analysis.variables
            if v.is_static and v.is_array
        ]
        has_separate = len(static_arrays) >= 2
        self.properties.append(PropertyScore(
            score=0.25 if has_separate else 0.0,
            max_score=0.25,
            description=f"Separate storage ({len(static_arrays)} static arrays found)",
            passed=has_separate,
        ))

        # P2: Sanitization on context switch / reset
        # Check for a sanitization function (by AST)
        sanitize_funcs = [
            f for f in self.analysis.functions
            if any(kw in f.name.lower()
                   for kw in ("sanitize", "zeroize", "clear_buffer"))
        ]
        # Also check for inline zeroing loop in reset/ctx_switch handler
        has_inline_sanitize = bool(
            re.search(r"(reset|ctx_switch).*for.*=\s*0", source, re.DOTALL)
            or re.search(r"for.*=\s*0.*\].*=\s*0", source, re.DOTALL)
        )
        has_sanitize = bool(sanitize_funcs) or has_inline_sanitize
        self.properties.append(PropertyScore(
            score=0.25 if has_sanitize else 0.0,
            max_score=0.25,
            description="Sanitization on context switch / reset",
            passed=has_sanitize,
        ))

        # P3: Stale data cleared after use
        # Look for zeroing after pop/read operations
        stale_cleared = bool(
            re.search(r"\[.*head.*\]\s*=\s*0", source)      # FIFO pop clear
            or re.search(r"data_buf\[.*\]\s*=\s*0", source)  # buffer clear
        )
        self.properties.append(PropertyScore(
            score=0.2 if stale_cleared else 0.0,
            max_score=0.2,
            description="Stale data cleared after use",
            passed=stale_cleared,
        ))

        # P4: No cross-domain timing interference
        # Check for TDM/slot-based scheduling
        has_tdm = bool(re.search(r"current_slot|tdm_schedule|time_slot", source))
        # Also check: no break in arbiter loop (constant-time scheduling)
        no_arb_break = not any(l.has_early_exit for l in self.analysis.loops)
        temporal_isolated = has_tdm or no_arb_break
        self.properties.append(PropertyScore(
            score=0.15 if temporal_isolated else 0.0,
            max_score=0.15,
            description="No cross-domain timing interference",
            passed=temporal_isolated,
        ))

        # P5: Zeroization command available
        has_zeroize = bool(sanitize_funcs) or bool(
            re.search(r"bool\s+zeroize", source)
        )
        self.properties.append(PropertyScore(
            score=0.15 if has_zeroize else 0.0,
            max_score=0.15,
            description="Zeroization command available",
            passed=has_zeroize,
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_source(self) -> str:
        with open(self.ast.source_path, "r") as f:
            return f.read()

    def get_report(self) -> List[dict]:
        """Return detailed property verification report."""
        return [
            {
                "description": p.description,
                "passed": p.passed,
                "score": p.score,
                "max_score": p.max_score,
            }
            for p in self.properties
        ]
