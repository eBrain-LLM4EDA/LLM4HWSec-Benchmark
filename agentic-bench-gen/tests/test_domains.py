from agentic_bench_gen.domains import DOMAIN_PROFILES, get_domain_profile, profile_as_prompt_context


def test_all_requested_domains_are_registered():
    expected = {
        "hls_security_codegen",
        "rtl_trojan_detection",
        "gate_trojan_detection",
        "hardware_reverse_engineering",
        "side_channel_fault_analysis",
        "adversarial_ht_generation",
        "logic_deobfuscation_sat",
    }

    assert expected.issubset(DOMAIN_PROFILES)


def test_domain_profile_prompt_context_contains_metrics():
    context = profile_as_prompt_context("hls_security_codegen")

    assert context["domain_id"] == "hls_security_codegen"
    assert "synthesis_pass_rate" in context["default_metrics"]
    assert get_domain_profile("rtl_trojan_detection").input_artifacts == ["RTL design"]

