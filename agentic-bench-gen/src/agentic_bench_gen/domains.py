from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainProfile:
    domain_id: str
    title: str
    input_artifacts: list[str]
    output_artifacts: list[str]
    default_metrics: list[str]
    baseline_sources: list[str]
    example_tasks: list[str]


DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "hls_security_codegen": DomainProfile(
        domain_id="hls_security_codegen",
        title="Security-Aware HLS Code Generation",
        input_artifacts=["HLS C/C++ code", "security spec", "CWE list"],
        output_artifacts=["security-hardened HLS code", "vulnerability report", "evaluation framework"],
        default_metrics=["cwe_violation_rate", "information_flow_correctness", "synthesis_pass_rate"],
        baseline_sources=["No published open-source benchmark found"],
        example_tasks=[
            "Add information flow tracking to prevent secret leakage in a crypto HLS kernel.",
            "Enforce access control on HLS memory interfaces.",
        ],
    ),``
    "rtl_trojan_detection": DomainProfile(
        domain_id="rtl_trojan_detection",
        title="RTL Hardware Trojan Detection",
        input_artifacts=["RTL design"],
        output_artifacts=["Trojan candidate list", "confidence score", "rationale"],
        default_metrics=["detection_rate", "false_positive_rate", "trigger_payload_localization"],
        baseline_sources=["Trust-Hub chip-level Trojan benchmarks"],
        example_tasks=["Find a rare-trigger kill-switch in an AES core."],
    ),
    "gate_trojan_detection": DomainProfile(
        domain_id="gate_trojan_detection",
        title="Gate-Level Trojan Detection",
        input_artifacts=["gate-level netlist"],
        output_artifacts=["Trojan detection label", "suspect node list"],
        default_metrics=["detection_rate", "false_positive_rate", "inference_latency"],
        baseline_sources=["Trust-Hub", "CASlab GAINESIS"],
        example_tasks=["Classify trigger and payload nodes in a synthesized AES netlist."],
    ),
    "hardware_reverse_engineering": DomainProfile(
        domain_id="hardware_reverse_engineering",
        title="Hardware Reverse Engineering",
        input_artifacts=["gate-level netlist", "obfuscated RTL"],
        output_artifacts=["word-level RTL", "functional description"],
        default_metrics=["word_recovery_rate", "structural_match_accuracy", "functional_equivalence"],
        baseline_sources=["HAL benchmarks", "ISCAS'85", "ITC'99"],
        example_tasks=["Recover a 32-bit adder tree from a flattened Yosys netlist."],
    ),
    "side_channel_fault_analysis": DomainProfile(
        domain_id="side_channel_fault_analysis",
        title="Side-Channel and Fault Analysis",
        input_artifacts=["RTL crypto/safety module", "fault model"],
        output_artifacts=["vulnerability report", "hardening suggestions"],
        default_metrics=["leakage_detection_accuracy", "fault_coverage", "hardening_precision"],
        baseline_sources=["No existing benchmark found"],
        example_tasks=["Identify flip-flops requiring TMR for SEU hardening."],
    ),
    "adversarial_ht_generation": DomainProfile(
        domain_id="adversarial_ht_generation",
        title="Adversarial Hardware Trojan Generation",
        input_artifacts=["target RTL", "detector model", "HT specification"],
        output_artifacts=["Trojan-infected RTL", "evasion report", "functional correctness evidence"],
        default_metrics=["trojan_survival_rate_post_synthesis", "detector_evasion_rate", "design_diversity"],
        baseline_sources=["GHOST benchmarks"],
        example_tasks=["Generate a stealthy SRAM Trojan that evades a detector."],
    ),
    "logic_deobfuscation_sat": DomainProfile(
        domain_id="logic_deobfuscation_sat",
        title="Logic Deobfuscation and SAT Attack Assistance",
        input_artifacts=["logic-locked netlist", "locking scheme description"],
        output_artifacts=["key-gate locations", "locking topology", "recovered or partial key"],
        default_metrics=["key_recovery_rate", "key_gate_localization_accuracy", "sat_iteration_reduction"],
        baseline_sources=["ISCAS/ITC locked variants", "Anti-SAT style circuits"],
        example_tasks=["Identify XOR key gates in a locked c880 netlist."],
    ),
}


def get_domain_profile(domain_id: str) -> DomainProfile:
    try:
        return DOMAIN_PROFILES[domain_id]
    except KeyError as exc:
        known = ", ".join(sorted(DOMAIN_PROFILES))
        raise ValueError(f"Unknown domain_id {domain_id!r}. Known domains: {known}") from exc


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
    }

