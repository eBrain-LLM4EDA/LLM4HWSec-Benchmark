# evaluation/private/ground_truth.py
"""Hidden ground truth constants and helper functions for SR checks.

This module is NOT visible to participants. It defines the expected keywords
that a correct vulnerability report must contain in the 'vulnerable_component'
and 'recommended_fix' fields.
"""

# ---------------------------------------------------------------------------
# SR1: vulnerable_component must mention the early-termination logic.
# ---------------------------------------------------------------------------
SR1_KEYWORDS = [
    "early_done",
    "comparator",
    "a_reg == 0",
    "a_reg == {WIDTH{1'b0}}",
    "early termination",
    "early-termination",
    "variable latency",
    "variable-latency",
]

# ---------------------------------------------------------------------------
# SR2: recommended_fix must describe a fixed-latency design change.
# ---------------------------------------------------------------------------
SR2_KEYWORDS = [
    "remove early_done",
    "remove early done",
    "fixed latency",
    "fixed-latency",
    "all iterations",
    "run all iterations",
    "counter runs to width",
    "WIDTH cycles",
    "always run WIDTH",
    "disable early termination",
    "eliminate early termination",
    "constant time",
    "constant-time",
    "fixed number of cycles",
    "run for WIDTH",
    "complete all WIDTH",
    "no early exit",
    "no early termination",
    "run to completion",
    "full WIDTH iterations",
]

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def check_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if *any* keyword appears as a case-insensitive substring."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)