from hlssecbench_openrouter.preflight import preflight_tester_bundle
from hlssecbench_openrouter.runner import ToolRunner
from hlssecbench_openrouter.workspace import Workspace


def test_runner_classifies_not_run_marker_as_not_run():
    assert ToolRunner.classify_result(0, "[NOT_RUN] FR4: bambu not found\n", "") == "not_run"


def test_tester_preflight_catches_known_portability_issues(tmp_path):
    ws = Workspace(tmp_path)
    bundle = {
        "files": [
            {
                "path": "tests/tb_check_token.cpp",
                "content": '#include <ap_int.h>\nint main(){ printf("x\\n"); }\n',
            },
            {
                "path": "tests/run_csim.sh",
                "content": """#!/usr/bin/env bash
cat > tests/ap_int.h <<'EOF'
class x { operator uint64_t() const; };
EOF
""",
            },
            {
                "path": "tests/run_synth.sh",
                "content": "#!/usr/bin/env bash\nexit 0\n",
            },
            {
                "path": "tests/run_cosim.sh",
                "content": "#!/usr/bin/env bash\nexit 0\n",
            },
            {
                "path": "tests/run_rtl_security.sh",
                "content": "awk 'BEGIN{in=0} /x(?!y)/ {print}' check_token.cpp\n",
            },
        ]
    }
    ws.write_file_bundle(bundle)

    report = preflight_tester_bundle(ws, bundle)
    issues = {issue["issue"] for issue in report["issues"]}

    assert report["status"] == "fail"
    assert "printf_without_header" in issues
    assert "awk_reserved_variable_in" in issues
    assert "non_posix_regex" in issues
    assert "ap_uint_integral_compare_ambiguous" in issues
