#!/usr/bin/env python3
"""
expected_facts.py -- PRIVATE ground-truth oracle constants for
gate_trojan_detection_tie_secen_001.

This module is not participant-facing. It documents the pinned
hidden-spec ground-truth values used by evaluation/evaluate.py when
grading the security requirements (SR1-SR4) of a submitted
trojan_report.json. evaluate.py does NOT trust these constants blindly:
after importing them, it independently re-derives the same facts by
structurally parsing the freshly shipped inputs/controller_netlist.v
(via the same parsing approach as evaluation/netlist_utils.py) and
verifies each constant below still holds against that parse. If the
input netlist were ever regenerated/mutated such that these facts no
longer hold, evaluate.py surfaces a `[TEST] FAIL: SETUP: ...` line and
exits 1 rather than silently mis-grading a submission against a stale
oracle.

Ground truth (per hidden_spec):

  - The peripheral controller's `secure_enable` net is, in the shipped
    (intentionally vulnerable) netlist, driven directly by a
    constant-tie cell (TIEHI) instance named `U_TIE_SECEN`, rather than
    by the intended combinational logic cone dependent on
    access_grant / admin_override / lock_bit.

  - The intended combinational driver cone -- instances `u_sec_and1`
    (AND2) and `u_sec_or2` (OR2) -- is still physically present in the
    netlist and correctly computes the intended enable condition onto
    net `sec_enable_calc`, but that net is never connected to
    `secure_enable` and has zero downstream loads: it is dead/orphaned
    logic. A correct analysis that goes beyond surface net naming
    should flag at least one of these two instances as orphaned.

Matching rules (per public_spec.response_format / hidden_spec
acceptance_criteria):

  - Field *values* such as `verdict`, and generally any free-text /
    enum-like string field, may be matched case-insensitively (e.g.
    "Trojan_Detected" and "trojan_detected" are equivalent; "clean"
    and "CLEAN" are equivalent).

  - Instance names and net names (e.g. `driver_instance`,
    `compromised_net`, entries of `suspect_instances` /
    `orphaned_logic`) MUST match the netlist's exact identifier
    spelling -- exact string match, not case-insensitive -- since
    Verilog identifiers are case-sensitive and the acceptance criteria
    explicitly require "exact instance/net name match".
"""

# ----------------------------------------------------------------------
# Pinned ground-truth oracle values
# ----------------------------------------------------------------------

# The exact instance name of the constant-tie cell that anomalously
# drives secure_enable. Must match exactly (case-sensitive) against a
# submitted report's 'driver_instance' field.
EXPECTED_DRIVER_INSTANCE = "U_TIE_SECEN"

# The exact net name whose driver is implicated. Must match exactly
# (case-sensitive) against a submitted report's 'compromised_net'
# field.
EXPECTED_COMPROMISED_NET = "secure_enable"

# Cell types that are considered valid "constant-tie" drivers for the
# purposes of SR1 structural confirmation (TIEHI or TIELO per the
# cell_library.v convention; this design uses TIEHI, but TIELO is
# accepted defensively since the SR1 detection_strategy names both).
EXPECTED_TIE_CELL_TYPES = ("TIEHI", "TIELO")

# The intended driver cone left dangling/orphaned by the substitution:
# the two instances whose combined output (sec_enable_calc) is never
# connected to secure_enable and has zero loads. SR3 grants partial
# credit if a submitted 'orphaned_logic' array contains at least one
# of these two instance names.
EXPECTED_ORPHAN_CANDIDATES = {"u_sec_and1", "u_sec_or2"}

# The net that the orphaned driver cone computes onto, which is itself
# never read by any other instance or primary output. Documented here
# for completeness / potential auxiliary cross-checks; evaluate.py's
# SR3 check keys off instance names (EXPECTED_ORPHAN_CANDIDATES) rather
# than this net name, since the public response_format asks
# participants for instance names, not net names, in 'orphaned_logic'.
EXPECTED_ORPHANED_NET = "sec_enable_calc"

# The exact required verdict string (case-insensitive match applies to
# the value per the matching rules above) that must be reported given
# the netlist as shipped always contains the tie substitution.
EXPECTED_VERDICT = "trojan_detected"

# ----------------------------------------------------------------------
# Matching-mode documentation (informational; enforced in evaluate.py)
# ----------------------------------------------------------------------

# Field values (case-insensitive comparison permitted):
CASE_INSENSITIVE_VALUE_FIELDS = ("verdict",)

# Identifier fields (exact, case-sensitive comparison required):
EXACT_MATCH_IDENTIFIER_FIELDS = (
    "driver_instance",
    "compromised_net",
    "suspect_instances",
    "orphaned_logic",
)