from agentic_bench_gen.domains import (
    DOMAIN_PROFILES,
    get_domain_profile,
    interface_timing_contract_text,
    profile_as_prompt_context,
    submission_contract_text,
    submission_paths,
)


def test_all_requested_domains_are_registered():
    expected = {
        "hls_security_codegen",
        "rtl_trojan_detection",
        "gate_trojan_detection",
        "hardware_reverse_engineering",
        "side_channel_fault_analysis",
        "logic_deobfuscation_sat",
    }

    assert expected.issubset(DOMAIN_PROFILES)
    # Trojan *generation* was cut (undiscriminating mutants + dual-use); the
    # pipeline must not carry a profile for it.
    assert "adversarial_ht_generation" not in DOMAIN_PROFILES


def test_domain_profile_prompt_context_contains_metrics():
    context = profile_as_prompt_context("hls_security_codegen")

    assert context["domain_id"] == "hls_security_codegen"
    assert "synthesis_pass_rate" in context["default_metrics"]
    assert get_domain_profile("rtl_trojan_detection").input_artifacts == ["RTL design"]


def test_every_domain_declares_a_usable_submission_contract():
    for domain_id, profile in DOMAIN_PROFILES.items():
        assert profile.submission_kind in {"hardened_artifact", "analysis_report"}, domain_id
        if profile.submission_kind == "analysis_report":
            # Report domains must name the answer file(s) the participant submits.
            assert profile.submission_artifacts, domain_id


def test_only_hls_is_a_hardened_artifact_domain():
    hardened = {d for d, p in DOMAIN_PROFILES.items() if p.submission_kind == "hardened_artifact"}
    assert hardened == {"hls_security_codegen"}


def test_submission_paths_hardened_artifact_grades_code_inputs_in_place():
    profile = get_domain_profile("hls_security_codegen")
    # Only the code input is graded; the spec/CWE list are not submissions.
    paths = submission_paths(profile, ["aes_sbox.cpp", "security_spec.md", "cwe_list.txt"])
    assert paths == ["inputs/aes_sbox.cpp"]


def test_submission_paths_analysis_report_grades_submission_dir():
    profile = get_domain_profile("logic_deobfuscation_sat")
    # The input netlist is NOT the submission; the answer file under submission/ is.
    paths = submission_paths(profile, ["locked_c880.v", "locking.md"])
    assert paths == ["submission/recovered_key.json"]


def test_submission_contract_text_reflects_kind():
    hardened = submission_contract_text(get_domain_profile("hls_security_codegen"))
    report = submission_contract_text(get_domain_profile("gate_trojan_detection"))
    assert "hardened_artifact" in hardened
    assert "analysis_report" in report
    assert "submission/trojan_report.json" in report


def test_prompt_context_exposes_submission_fields():
    ctx = profile_as_prompt_context("side_channel_fault_analysis")
    assert ctx["submission_kind"] == "analysis_report"
    assert ctx["submission_artifacts"] == ["vulnerability_report.json"]
    assert "submission_contract" in ctx



def test_every_domain_declares_evaluation_mode_and_toolchain():
    valid_modes = {"compile_and_run", "simulate", "report_grading"}
    for domain_id, profile in DOMAIN_PROFILES.items():
        assert profile.evaluation_mode in valid_modes, domain_id
        # Behavioral modes are meaningless without an executable toolchain.
        if profile.evaluation_mode in {"compile_and_run", "simulate"}:
            assert profile.toolchain, domain_id


def test_hls_domain_grades_by_compile_and_run():
    profile = get_domain_profile("hls_security_codegen")
    assert profile.evaluation_mode == "compile_and_run"
    assert "g++" in profile.toolchain


def test_prompt_context_exposes_evaluation_contract():
    ctx = profile_as_prompt_context("hls_security_codegen")
    assert ctx["evaluation_mode"] == "compile_and_run"
    assert "compile" in ctx["evaluation_contract"]
    assert "fail-on-presence" in ctx["evaluation_contract"]

    report_ctx = profile_as_prompt_context("gate_trojan_detection")
    assert report_ctx["evaluation_mode"] == "report_grading"
    assert "answer file" in report_ctx["evaluation_contract"]


def test_timing_contract_present_only_for_simulate_domains():
    # Simulate domains compare golden vs reference cycle-by-cycle, so the
    # Architect gets a mandate to pin exact timing; other domains get "".
    for domain_id, profile in DOMAIN_PROFILES.items():
        text = interface_timing_contract_text(profile)
        if profile.evaluation_mode == "simulate":
            assert "SEQUENTIAL TIMING CONTRACT" in text, domain_id
            assert "Moore" in text and "cycle" in text.lower(), domain_id
        else:
            assert text == "", domain_id


def test_prompt_context_exposes_timing_contract_for_simulate_domain():
    ctx = profile_as_prompt_context("hardware_reverse_engineering")
    assert ctx["evaluation_mode"] == "simulate"
    assert "SEQUENTIAL TIMING CONTRACT" in ctx["interface_timing_contract"]

    # A non-simulate domain renders the placeholder empty (blank in the prompt).
    assert profile_as_prompt_context("gate_trojan_detection")["interface_timing_contract"] == ""
