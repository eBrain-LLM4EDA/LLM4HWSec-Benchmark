from hls_bench_agentic.orchestrator import (
    _copy_workspace_for_mutant,
    _cosim_enabled,
    _make_analysis_packet,
    _merge_file_bundle_into_test_bundle,
    _preflight_execution_results,
    _strip_c_comments,
    _unique_task_workspace,
)
from hls_bench_agentic.workspace import Workspace


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

    tester_preflight = {"status": "pass", "issues": []}
    packet = _make_analysis_packet(
        task_spec,
        expert_bundle,
        {"manifest": [], "requirement_map": []},
        execution_results,
        tester_preflight=tester_preflight,
    )

    assert packet["expert_static_review"]["status"] == "ok"
    assert packet["tester_preflight"] == tester_preflight
    assert {
        "source": "generated_static_checker",
        "classification": "likely_tester_false_positive",
        "artifact_to_revise": "tester",
        "reason": (
            "The generated rtl_security script reported a break, but independent "
            "comment-stripped expert analysis found no early exit in loops."
        ),
    } in packet["provenance_hints"]


def test_preflight_execution_results_skips_tool_steps(tmp_path):
    ws = Workspace(tmp_path)
    report = {"status": "fail", "issues": [{"path": "tests/run_csim.sh", "issue": "bash_syntax_error"}]}

    results = _preflight_execution_results(ws, report)

    assert results["steps"][0]["name"] == "tester_preflight"
    assert results["steps"][0]["status"] == "fail"
    assert (tmp_path / "reports" / "execution_results.json").exists()


def test_cosim_file_bundle_overrides_tester_cosim_files():
    test_bundle = {
        "manifest": [{"path": "tests/run_cosim.sh", "purpose": "old"}],
        "requirement_map": [{"requirement_id": "SR1", "test_files": ["tests/run_cosim.sh"], "expected_detection": "PASS"}],
        "files": [
            {"path": "tests/run_cosim.sh", "content": "old"},
            {"path": "tests/run_csim.sh", "content": "csim"},
        ],
    }
    cosim_bundle = {
        "manifest": [{"path": "tests/run_cosim.sh", "purpose": "specialized cosim"}],
        "files": [
            {"path": "tests/run_cosim.sh", "content": "new"},
            {"path": "tests/tb_cosim.cpp", "content": "tb"},
        ],
    }

    merged = _merge_file_bundle_into_test_bundle(test_bundle, cosim_bundle)
    files = {item["path"]: item["content"] for item in merged["files"]}
    manifest = {item["path"]: item["purpose"] for item in merged["manifest"]}

    assert files["tests/run_cosim.sh"] == "new"
    assert files["tests/run_csim.sh"] == "csim"
    assert files["tests/tb_cosim.cpp"] == "tb"
    assert manifest["tests/run_cosim.sh"] == "specialized cosim"
    assert merged["requirement_map"] == test_bundle["requirement_map"]


def test_cosim_enabled_reads_pipeline_switch_and_step_flag():
    assert _cosim_enabled({"pipeline": {"enable_cosim": False}, "execution": {"steps": []}}) is False
    assert _cosim_enabled({"pipeline": {"enable_cosim": True}, "execution": {"steps": [{"name": "cosim", "enabled": False}]}}) is False
    assert _cosim_enabled({"pipeline": {}, "execution": {"steps": [{"name": "cosim", "enabled": False}]}}) is False
    assert _cosim_enabled({"pipeline": {}, "execution": {"steps": [{"name": "cosim"}]}}) is True


def test_copy_workspace_for_mutant_excludes_generated_tool_artifacts(tmp_path):
    src = tmp_path / "task"
    dst = tmp_path / "task" / "mutants" / "M1"
    (src / "src").mkdir(parents=True)
    (src / "tests").mkdir()
    (src / "spec").mkdir()
    (src / "HLS_output" / "beh_sim" / "verilator_obj").mkdir(parents=True)
    (src / "cosim_out").mkdir()
    (src / "reports").mkdir()
    (src / "src" / "impl.cpp").write_text("int top(){return 0;}\n")
    (src / "tests" / "run_cosim.sh").write_text("#!/usr/bin/env bash\n")
    (src / "spec" / "task_spec.json").write_text("{}\n")
    (src / "HLS_output" / "beh_sim" / "verilator_obj" / "Vtb.cpp").write_text("generated\n")
    (src / "compare_token.v").write_text("module x; endmodule\n")
    (src / "cosim_out" / "cosim.log").write_text("generated\n")
    (src / "reports" / "execution_results.json").write_text("{}\n")

    _copy_workspace_for_mutant(src, dst)

    assert (dst / "src" / "impl.cpp").exists()
    assert (dst / "tests" / "run_cosim.sh").exists()
    assert (dst / "spec" / "task_spec.json").exists()
    assert not (dst / "HLS_output").exists()
    assert not (dst / "cosim_out").exists()
    assert not (dst / "reports").exists()
    assert not (dst / "compare_token.v").exists()
