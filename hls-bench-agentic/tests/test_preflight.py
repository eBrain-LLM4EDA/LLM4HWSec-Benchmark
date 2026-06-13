from hls_bench_agentic.preflight import preflight_tester_bundle
from hls_bench_agentic.workspace import Workspace


def test_tester_preflight_catches_known_portability_issues(tmp_path):
    ws = Workspace(tmp_path)
    bundle = {
        "files": [
            {
                "path": "tests/tb_compare_token.cpp",
                "content": '#include <stdint.h>\nint main(){ printf("x\\n"); }\n',
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
                "content": "#!/usr/bin/env bash\nset -e\nbambu src/impl.cpp --generate-interface=infer 2>&1 | tee synth.log\ntest -f synth_out/compare_token.v\n",
            },
            {
                "path": "tests/run_cosim.sh",
                "content": "#!/usr/bin/env bash\nset -e\nbambu src/impl.cpp --simulate --generate-tb=tests/test_vectors.xml 2>&1 | tee cosim.log\ngrep -q \"Simulation completed\" cosim.log\n",
            },
            {
                "path": "tests/run_rtl_security.sh",
                "content": "awk 'BEGIN{in=0} /x(?!y)/ {print}' compare_token.c\n",
            },
            {
                "path": "tests/test_vectors.xml",
                "content": "<testbench><test></test></testbench>\n",
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
    assert "bambu_pipeline_without_pipefail" in issues
    assert "unsupported_bambu_infer_interface" in issues
    assert "brittle_synth_rtl_path" in issues
    assert "hallucinated_bambu_xml_testbench" in issues
    assert "unverified_bambu_xml_schema" in issues
    assert "brittle_bambu_completion_grep" in issues


def test_tester_preflight_can_relax_cosim_requirement(tmp_path):
    ws = Workspace(tmp_path)
    bundle = {
        "files": [
            {"path": "tests/tb_csim.cpp", "content": "#include <stdio.h>\nint main(){return 0;}\n"},
            {"path": "tests/run_csim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_synth.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_rtl_security.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
        ]
    }
    ws.write_file_bundle(bundle)

    required_report = preflight_tester_bundle(ws, bundle)
    optional_report = preflight_tester_bundle(ws, bundle, require_cosim=False)

    assert {
        "path": "tests/run_cosim.sh",
        "issue": "missing_required_bundle_file",
    } in required_report["issues"]
    assert optional_report["status"] == "pass"


def test_tester_preflight_catches_extern_c_linkage_mismatch(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_text("src/impl.cpp", "#include <stdint.h>\nuint8_t compare_token(const uint8_t input_token[16]) { return input_token[0]; }\n")
    bundle = {
        "files": [
            {
                "path": "tests/tb_csim.cpp",
                "content": '#include <stdint.h>\nextern "C" uint8_t compare_token(const uint8_t input_token[16]);\nint main(){ uint8_t x[16]={0}; return compare_token(x); }\n',
            },
            {"path": "tests/run_csim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_synth.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_cosim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\nbambu src/impl.cpp --simulate\n"},
            {"path": "tests/run_rtl_security.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
        ]
    }
    ws.write_file_bundle(bundle)

    report = preflight_tester_bundle(ws, bundle)
    issues = {issue["issue"] for issue in report["issues"]}

    assert "extern_c_linkage_mismatch" in issues


def test_tester_preflight_accepts_extern_c_from_included_header(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_text("src/compare_token.h", '#ifdef __cplusplus\nextern "C" {\n#endif\n#include <stdint.h>\nuint8_t compare_token(const uint8_t input_token[16]);\n#ifdef __cplusplus\n}\n#endif\n')
    ws.write_text("src/impl.cpp", '#include "compare_token.h"\nuint8_t compare_token(const uint8_t input_token[16]) { return input_token[0]; }\n')
    bundle = {
        "files": [
            {
                "path": "tests/tb_csim.cpp",
                "content": '#include <stdint.h>\nextern "C" uint8_t compare_token(const uint8_t input_token[16]);\nint main(){ uint8_t x[16]={0}; return compare_token(x); }\n',
            },
            {"path": "tests/run_csim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_synth.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_cosim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\nbambu src/impl.cpp --simulate\n"},
            {"path": "tests/run_rtl_security.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
        ]
    }
    ws.write_file_bundle(bundle)

    report = preflight_tester_bundle(ws, bundle)
    issues = {issue["issue"] for issue in report["issues"]}

    assert "extern_c_linkage_mismatch" not in issues


def test_tester_preflight_catches_reference_token_mismatch(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_text(
        "src/impl.cpp",
        "#include <stdint.h>\n"
        "uint8_t compare_token(const uint8_t input_token[16]) {\n"
        "  const uint8_t reference_token[16] = {0x4A,0x7B,0x9C,0x2D,0xE1,0xF3,0x56,0x88,0xA4,0xC7,0x3E,0x91,0xD2,0x6F,0xB5,0x08};\n"
        "  return input_token[0] == reference_token[0];\n"
        "}\n",
    )
    bundle = {
        "files": [
            {
                "path": "tests/tb_csim.cpp",
                "content": "#include <stdint.h>\nstatic const uint8_t reference[16] = {0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,0xFE,0xDC,0xBA,0x98,0x76,0x54,0x32,0x10};\nint main(){return reference[0];}\n",
            },
            {"path": "tests/run_csim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_synth.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
            {"path": "tests/run_cosim.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\nbambu src/impl.cpp --simulate\n"},
            {"path": "tests/run_rtl_security.sh", "content": "#!/usr/bin/env bash\nset -euo pipefail\n"},
        ]
    }
    ws.write_file_bundle(bundle)

    report = preflight_tester_bundle(ws, bundle)
    issues = {issue["issue"] for issue in report["issues"]}

    assert "reference_token_mismatch" in issues
