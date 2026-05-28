from hls_bench_agentic.orchestrator import (
    _make_analysis_packet,
    _strip_c_comments,
    _unique_task_workspace,
)


def test_unique_task_workspace_uses_task_id_when_available(tmp_path):
    assert _unique_task_workspace(tmp_path, "hls_cwe385") == tmp_path / "hls_cwe385"


def test_unique_task_workspace_suffixes_existing_runs(tmp_path):
    (tmp_path / "hls_cwe385").mkdir()
    (tmp_path / "hls_cwe385_gen001").mkdir()

    assert _unique_task_workspace(tmp_path, "hls_cwe385") == tmp_path / "hls_cwe385_gen002"


def test_strip_c_comments_removes_block_comment_keywords():
    source = "/* no early returns, breaks, or branches */\nint f(void) { return 1; }\n"

    stripped = _strip_c_comments(source)

    assert "breaks" not in stripped
    assert "return 1" in stripped


def test_analysis_packet_flags_static_checker_comment_false_positive():
    task_spec = {
        "task_id": "hls_cwe385",
        "public_spec": {"functional_requirements": []},
        "hidden_spec": {
            "security_domain": "side_channel",
            "security_requirements": [{"id": "SR2", "requirement": "No early exit"}],
            "forbidden_patterns": [],
        },
    }
    expert_bundle = {
        "files": [
            {
                "path": "compare_token.c",
                "content": (
                    "/* No early returns, breaks, or data-dependent branches. */\n"
                    "#include <stdint.h>\n"
                    "int compare_token(const uint8_t a[16], const uint8_t b[16]) {\n"
                    "  uint8_t diff = 0;\n"
                    "  #pragma HLS loop_bound min=16 max=16\n"
                    "  for (int i = 0; i < 16; i++) { diff |= a[i] ^ b[i]; }\n"
                    "  return diff == 0;\n"
                    "}\n"
                ),
            }
        ],
        "manifest": [],
    }
    execution_results = {
        "steps": [
            {
                "name": "rtl_security",
                "status": "fail",
                "stdout": "[FAIL] SR2: Break statement found in implementation",
                "stderr": "",
            }
        ]
    }

    packet = _make_analysis_packet(task_spec, expert_bundle, {"manifest": [], "requirement_map": []}, execution_results)

    assert packet["expert_static_review"]["status"] == "ok"
    assert {
        "source": "generated_static_checker",
        "classification": "likely_tester_false_positive",
        "artifact_to_revise": "tester",
        "reason": (
            "The generated rtl_security script reported a break, but independent "
            "comment-stripped expert analysis found no early exit in loops."
        ),
    } in packet["provenance_hints"]
