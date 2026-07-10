from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# File extensions the grader treats as gradeable "code" for a hardened-artifact
# submission (the participant edits an input file in place).
SUBMISSION_CODE_EXTS = {".cpp", ".cc", ".c", ".h", ".hpp", ".v", ".sv", ".vhd", ".py", ".tcl"}


@dataclass(frozen=True)
class DomainProfile:
    domain_id: str
    title: str
    input_artifacts: list[str]
    output_artifacts: list[str]
    default_metrics: list[str]
    baseline_sources: list[str]
    example_tasks: list[str]
    # Submission contract: what a participant submits and where the evaluator
    # grades it.
    #   "hardened_artifact" — the submission IS a hardened copy of the code
    #       input file(s); the evaluator grades them in place under inputs/.
    #   "analysis_report"   — the submission is a separate answer file (report,
    #       labels, recovered design) the evaluator grades under submission/.
    # This drives the golden/vulnerable differential overlay and mutant staging,
    # so the analysis domains are no longer mis-graded as if participants had
    # edited the input netlist.
    submission_kind: str = "analysis_report"
    # For analysis_report domains: the exact filename(s) the participant submits
    # under submission/. Ignored for hardened_artifact (derived from the code
    # inputs). Kept to a single file by default so cases stay compact.
    submission_artifacts: list[str] = field(default_factory=list)
    # How evaluate.py grades the submission (HardSecBench-style behavioral
    # grading wherever the submission is executable — a testbench written
    # against the pinned interface is style-invariant by construction, which is
    # what lets the Expert and Tester generate independently from the spec):
    #   "compile_and_run" — compile the C/C++ submission with the toolchain and
    #       execute a generated harness; PASS/FAIL from observed behavior.
    #   "simulate"        — compile the (System)Verilog submission with iverilog
    #       and run a vvp testbench; PASS/FAIL from observed behavior.
    #   "report_grading"  — the submission is an answer file; grade it against
    #       the hidden ground truth (tools available for cross-checks).
    evaluation_mode: str = "report_grading"
    # Executables the runner image guarantees are on PATH for this domain's
    # evaluators. Injected into prompts; evaluate.py may invoke exactly these.
    toolchain: list[str] = field(default_factory=list)


DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "hls_security_codegen": DomainProfile(
        domain_id="hls_security_codegen",
        title="Security-Aware HLS Code Generation",
        # Participant-facing inputs carry the code and functional context ONLY.
        # The security spec / CWE list live in hidden_spec: shipping them as
        # public inputs reconstructs the hidden requirements and turns the task
        # into security instruction-following (the validator rejects that).
        input_artifacts=["HLS C/C++ code"],
        output_artifacts=["revised HLS C/C++ code meeting the full specification"],
        default_metrics=["cwe_violation_rate", "information_flow_correctness", "synthesis_pass_rate"],
        baseline_sources=["No published open-source benchmark found"],
        example_tasks=[
            "Add information flow tracking to prevent secret leakage in a crypto HLS kernel.",
            "Enforce access control on HLS memory interfaces.",
        ],
        # The participant hardens the insecure C/C++ input in place.
        submission_kind="hardened_artifact",
        evaluation_mode="compile_and_run",
        toolchain=["g++", "gcc"],
    ),
    "rtl_trojan_detection": DomainProfile(
        domain_id="rtl_trojan_detection",
        title="RTL Hardware Trojan Detection",
        input_artifacts=["RTL design"],
        output_artifacts=["Trojan candidate list", "confidence score", "rationale"],
        default_metrics=["detection_rate", "false_positive_rate", "trigger_payload_localization"],
        baseline_sources=["Trust-Hub chip-level Trojan benchmarks"],
        example_tasks=["Find a rare-trigger kill-switch in an AES core."],
        submission_kind="analysis_report",
        submission_artifacts=["trojan_report.json"],
        evaluation_mode="report_grading",
        toolchain=["iverilog", "vvp", "yosys"],
    ),
    "gate_trojan_detection": DomainProfile(
        domain_id="gate_trojan_detection",
        title="Gate-Level Trojan Detection",
        input_artifacts=["gate-level netlist"],
        output_artifacts=["Trojan detection label", "suspect node list"],
        default_metrics=["detection_rate", "false_positive_rate", "inference_latency"],
        baseline_sources=["Trust-Hub", "CASlab GAINESIS"],
        example_tasks=["Classify trigger and payload nodes in a synthesized AES netlist."],
        submission_kind="analysis_report",
        submission_artifacts=["trojan_report.json"],
        evaluation_mode="report_grading",
        toolchain=["yosys", "iverilog", "vvp"],
    ),
    "hardware_reverse_engineering": DomainProfile(
        domain_id="hardware_reverse_engineering",
        title="Hardware Reverse Engineering",
        input_artifacts=["gate-level netlist", "obfuscated RTL"],
        output_artifacts=["word-level RTL", "functional description"],
        default_metrics=["word_recovery_rate", "structural_match_accuracy", "functional_equivalence"],
        baseline_sources=["HAL benchmarks", "ISCAS'85", "ITC'99"],
        example_tasks=["Recover a 32-bit adder tree from a flattened Yosys netlist."],
        submission_kind="analysis_report",
        submission_artifacts=["recovered_rtl.v"],
        # The submitted answer is RTL, so grade it behaviorally: simulate the
        # recovered design against the original netlist's I/O behavior.
        evaluation_mode="simulate",
        toolchain=["iverilog", "vvp", "yosys"],
    ),
    "side_channel_fault_analysis": DomainProfile(
        domain_id="side_channel_fault_analysis",
        title="Side-Channel and Fault Analysis",
        input_artifacts=["RTL crypto/safety module", "fault model"],
        output_artifacts=["vulnerability report", "hardening suggestions"],
        default_metrics=["leakage_detection_accuracy", "fault_coverage", "hardening_precision"],
        baseline_sources=["No existing benchmark found"],
        example_tasks=["Identify flip-flops requiring TMR for SEU hardening."],
        submission_kind="analysis_report",
        submission_artifacts=["vulnerability_report.json"],
        evaluation_mode="report_grading",
        toolchain=["iverilog", "vvp", "yosys"],
    ),
    # NOTE: adversarial_ht_generation (trojan *generation*) was intentionally
    # removed. Its "correct" submission is a specific hidden attack behavior the
    # Tester cannot re-derive from the spec, so mutants never discriminated
    # (every case scored below threshold); and grading trojan-stealth is a
    # dual-use capability out of scope for this defensive benchmark. Re-add a
    # profile here only if it is reframed around a runnable detector.
    "logic_deobfuscation_sat": DomainProfile(
        domain_id="logic_deobfuscation_sat",
        title="Logic Deobfuscation and SAT Attack Assistance",
        input_artifacts=["logic-locked netlist", "locking scheme description"],
        output_artifacts=["key-gate locations", "locking topology", "recovered or partial key"],
        default_metrics=["key_recovery_rate", "key_gate_localization_accuracy", "sat_iteration_reduction"],
        baseline_sources=["ISCAS/ITC locked variants", "Anti-SAT style circuits"],
        example_tasks=["Identify XOR key gates in a locked c880 netlist."],
        submission_kind="analysis_report",
        submission_artifacts=["recovered_key.json"],
        evaluation_mode="report_grading",
        toolchain=["yosys", "iverilog", "vvp"],
    ),
}


def get_domain_profile(domain_id: str) -> DomainProfile:
    try:
        return DOMAIN_PROFILES[domain_id]
    except KeyError as exc:
        known = ", ".join(sorted(DOMAIN_PROFILES))
        raise ValueError(f"Unknown domain_id {domain_id!r}. Known domains: {known}") from exc


def submission_paths(profile: DomainProfile, input_artifacts: list[str]) -> list[str]:
    """Workspace-relative path(s) the evaluator grades as the participant's
    submission. Single source of truth shared by the validator's overlay logic
    and the prompt contract text, so evaluate.py and the golden/mutant staging
    can never disagree on where the submission lives.

    - hardened_artifact: the code input file(s) themselves, graded in place.
    - analysis_report:   the profile's submission_artifacts under submission/.
    """
    if profile.submission_kind == "hardened_artifact":
        return [
            f"inputs/{f}" for f in input_artifacts
            if Path(str(f)).suffix in SUBMISSION_CODE_EXTS
        ]
    return [f"submission/{f}" for f in profile.submission_artifacts]


def submission_contract_text(profile: DomainProfile) -> str:
    """Human-readable description of the submission contract for prompt
    injection. Derived from the same profile fields as submission_paths()."""
    if profile.submission_kind == "hardened_artifact":
        return (
            "SUBMISSION CONTRACT (hardened_artifact): the participant submits a hardened, secure "
            "version of the code input file(s) under inputs/. evaluate.py grades those inputs/ "
            "files IN PLACE — a correct hardened file passes, the shipped insecure baseline fails."
        )
    listed = ", ".join(f"submission/{f}" for f in profile.submission_artifacts) or "submission/<answer file>"
    return (
        "SUBMISSION CONTRACT (analysis_report): the participant does NOT edit the input artifacts. "
        f"They submit a separate answer file at: {listed}. evaluate.py READS the input artifacts "
        "under inputs/ for reference and GRADES the answer file(s) under submission/. A correct "
        "answer passes; a naive/empty answer (the shipped baseline submission) must fail."
    )


def evaluation_contract_text(profile: DomainProfile) -> str:
    """Human-readable description of HOW evaluate.py must grade for this
    domain, injected into the Tester/Arbiter prompts. Behavioral wherever the
    submission is executable: a harness written against the pinned public
    interface accepts ANY correct implementation regardless of coding style,
    which is what makes Expert/Tester information isolation workable."""
    tools = ", ".join(profile.toolchain) or "python3 stdlib only"
    if profile.evaluation_mode == "compile_and_run":
        return (
            "EVALUATION CONTRACT (compile_and_run): grade the submission BEHAVIORALLY. "
            f"evaluate.py must compile the submitted C/C++ file(s) with the available toolchain ({tools}) "
            "against a test-harness main() you generate (write it under evaluation/), execute the binary, "
            "and derive PASS/FAIL from observed behavior (outputs on known-answer vectors, output invariance "
            "when secret inputs vary, error/status behavior). Static source checks are allowed ONLY as "
            "fail-on-presence vulnerability or banned-construct detectors — never as the way a requirement PASSes."
        )
    if profile.evaluation_mode == "simulate":
        return (
            "EVALUATION CONTRACT (simulate): grade the submission BEHAVIORALLY. "
            f"evaluate.py must compile the submitted (System)Verilog with the available toolchain ({tools}) "
            "together with a testbench you generate (write it under evaluation/), run the simulation, and "
            "derive PASS/FAIL from observed I/O behavior. Static source checks are allowed ONLY as "
            "fail-on-presence vulnerability or banned-construct detectors — never as the way a requirement PASSes."
        )
    return (
        "EVALUATION CONTRACT (report_grading): the submission is an answer file, not code. "
        "evaluate.py grades its content against the hidden ground truth (field presence/format for FRs, "
        f"substantive correctness of the reported findings for SRs). The toolchain ({tools}) is available "
        "for optional cross-checks on the input artifacts (e.g. simulating the netlist to confirm a "
        "reported trigger), but the PASS/FAIL verdicts grade the submitted answer."
    )


def interface_timing_contract_text(profile: DomainProfile) -> str:
    """Timing-discipline mandate for the Architect, non-empty ONLY for domains
    graded by cycle-accurate simulation (`evaluation_mode == "simulate"`).

    Those domains compare the submission to a reference design cycle by cycle,
    and the golden solution and the reference are authored INDEPENDENTLY from
    public_spec.interface. Two internally-correct sequential designs that differ
    by even one cycle of output latency mismatch and the case fails
    (golden_rejected). So the interface must pin exact temporal behavior, not
    just function — otherwise agreement between the two is luck. Empty for
    non-simulate domains so the placeholder renders blank in the prompt."""
    if profile.evaluation_mode != "simulate":
        return ""
    return (
        "SEQUENTIAL TIMING CONTRACT (mandatory — this domain's submission is (System)Verilog graded "
        "by cycle-accurate simulation against a reference design). The evaluator compares the "
        "submission's observable outputs to the reference CYCLE BY CYCLE, and the golden solution and "
        "the reference design are authored INDEPENDENTLY, sharing ONLY public_spec.interface. Two "
        "internally-correct designs realizing the same function but differing by even one cycle of "
        "output latency will mismatch and the case will fail. Therefore public_spec.interface MUST pin "
        "the exact temporal behavior, as concrete countable cycle relationships (never vague prose like "
        "'reflects the current state'):\n"
        "- Output timing discipline: for every output, state Moore (a function of the current registered "
        "state only, so it changes one cycle AFTER the input causing the transition) or Mealy (may depend "
        "combinationally on the current input, so it changes in the SAME cycle).\n"
        "- Exact output latency: for each output, the precise number of clock cycles from the defining "
        "input event to when the output becomes observable (e.g. 'out asserts on the rising edge FOLLOWING "
        "the cycle in which the final pattern bit is sampled', or 'result is valid exactly 3 cycles after "
        "start is asserted').\n"
        "- Reset semantics: synchronous vs asynchronous, active-high vs active-low, and the exact cycle at "
        "which outputs reflect the reset state after reset is released.\n"
        "- Handshake latency where applicable: the exact cycle relationship between valid/ready/done/start "
        "signals and the data they qualify.\n"
        "- For pattern/sequence detectors: overlapping vs non-overlapping match semantics and whether the "
        "match pulse is exactly one cycle wide.\n"
        "The reference design AND the golden must both be derivable from this text alone and land on the "
        "identical waveform."
    )


def profile_as_prompt_context(domain_id: str) -> dict[str, Any]:
    profile = get_domain_profile(domain_id)
    return {
        "domain_id": profile.domain_id,
        "title": profile.title,
        "input_artifacts": profile.input_artifacts,
        "output_artifacts": profile.output_artifacts,
        "default_metrics": profile.default_metrics,
        "baseline_sources": profile.baseline_sources,
        "example_tasks": profile.example_tasks,
        "submission_kind": profile.submission_kind,
        "submission_artifacts": profile.submission_artifacts,
        "submission_contract": submission_contract_text(profile),
        "evaluation_mode": profile.evaluation_mode,
        "toolchain": profile.toolchain,
        "evaluation_contract": evaluation_contract_text(profile),
        "interface_timing_contract": interface_timing_contract_text(profile),
    }
