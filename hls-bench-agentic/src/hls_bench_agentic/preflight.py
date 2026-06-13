from __future__ import annotations

import re
import subprocess
from pathlib import Path
from shlex import split
from typing import Any

from .workspace import Workspace


def preflight_tester_bundle(
    ws: Workspace,
    test_bundle: dict[str, Any],
    require_cosim: bool = True,
) -> dict[str, Any]:
    required = {
        "tests/run_csim.sh",
        "tests/run_synth.sh",
        "tests/run_rtl_security.sh",
    }
    if require_cosim:
        required.add("tests/run_cosim.sh")
    bundle_paths = {str(file_obj.get("path", "")) for file_obj in test_bundle.get("files", [])}
    issues: list[dict[str, str]] = []

    for path in sorted(required - bundle_paths):
        issues.append({"path": path, "issue": "missing_required_bundle_file"})

    tb_files = [p for p in bundle_paths if re.fullmatch(r"tests/tb_.+\.(c|cc|cpp|cxx)", p)]
    if not tb_files:
        issues.append({"path": "tests/tb_<top_function>.cpp", "issue": "missing_testbench_bundle_file"})

    for path in sorted(required | set(tb_files)):
        if path not in bundle_paths:
            continue
        materialized = ws.path(path)
        if not materialized.is_file():
            issues.append({"path": path, "issue": "bundle_file_not_materialized"})

    for file_obj in test_bundle.get("files", []):
        path = str(file_obj.get("path", ""))
        content = str(file_obj.get("content", ""))
        if path.endswith(".sh"):
            script = ws.path(path)
            if script.is_file():
                proc = subprocess.run(
                    ["bash", "-n", str(script)],
                    cwd=str(ws.root),
                    text=True,
                    capture_output=True,
                )
                if proc.returncode != 0:
                    issues.append({
                        "path": path,
                        "issue": "bash_syntax_error",
                        "detail": (proc.stderr or proc.stdout).strip()[:1000],
                    })
            if "bambu " in content and "| tee" in content and "pipefail" not in content:
                issues.append({
                    "path": path,
                    "issue": "bambu_pipeline_without_pipefail",
                    "detail": "Bambu output piped through tee must enable pipefail or the script can hide Bambu failures.",
                })

        if path in {"tests/run_synth.sh", "tests/run_cosim.sh"}:
            if "--generate-interface=infer" in content:
                issues.append({
                    "path": path,
                    "issue": "unsupported_bambu_infer_interface",
                    "detail": "Bambu reported `Not supported interface: |infer|`; use an explicit supported interface or omit this flag.",
                })

        if path == "tests/run_synth.sh":
            _check_synth_script(content, issues)

        if path == "tests/run_cosim.sh":
            _check_cosim_script(content, bundle_paths, issues)

        if path == "tests/run_rtl_security.sh":
            if re.search(r"(^|[^A-Za-z0-9_])in\s*=", content):
                issues.append({
                    "path": path,
                    "issue": "awk_reserved_variable_in",
                    "detail": "Avoid using awk variable name `in`; it fails on common awk implementations.",
                })
            if "(?!" in content or "(?<" in content:
                issues.append({
                    "path": path,
                    "issue": "non_posix_regex",
                    "detail": "Shell grep/awk checks should not use lookaround regex syntax.",
                })

        if path.startswith("tests/") and Path(path).suffix in {".c", ".cc", ".cpp", ".cxx"}:
            if "printf(" in content and "#include <cstdio>" not in content and "#include <stdio.h>" not in content:
                issues.append({
                    "path": path,
                    "issue": "printf_without_header",
                    "detail": "Testbenches using printf must include <cstdio> or <stdio.h>.",
                })

        if path == "tests/run_csim.sh":
            if "operator uint64_t()" in content and not re.search(r"operator\s*!=\s*\([^)]*(int|uint64_t|unsigned)", content):
                issues.append({
                    "path": path,
                    "issue": "ap_uint_integral_compare_ambiguous",
                    "detail": "The fallback ap_uint shim converts to uint64_t but lacks integral comparison overloads.",
                })

    _check_testbench_linkage(ws, test_bundle, issues)
    _check_reference_token_consistency(ws, test_bundle, issues)

    report = {
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }
    ws.write_json("reports/tester_preflight.json", report)
    return report


def _check_testbench_linkage(
    ws: Workspace,
    test_bundle: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    impl_path = ws.path("src/impl.cpp")
    if not impl_path.is_file():
        return
    impl = impl_path.read_text(errors="ignore")
    for file_obj in test_bundle.get("files", []):
        path = str(file_obj.get("path", ""))
        if not path.startswith("tests/") or Path(path).suffix.lower() not in {".c", ".cc", ".cpp", ".cxx"}:
            continue
        content = str(file_obj.get("content", ""))
        for top in _extern_c_function_names(content):
            definition = re.search(
                rf"(^|[;\n}}\s])(?:[A-Za-z_][\w:<>,\s*&]*\s+)+{re.escape(top)}\s*\(",
                impl,
                flags=re.MULTILINE,
            )
            if definition and 'extern "C"' not in impl[:definition.start()] and not _included_header_declares_extern_c(ws, impl, top):
                issues.append({
                    "path": path,
                    "issue": "extern_c_linkage_mismatch",
                    "detail": f"{path} declares `{top}` with C linkage, but src/impl.cpp defines it without visible extern \"C\" linkage.",
                })


def _extern_c_function_names(content: str) -> set[str]:
    names: set[str] = set()
    for block in re.finditer(r'extern\s+"C"\s*\{(?P<body>.*?)\}', content, flags=re.DOTALL):
        names.update(_function_decl_names(block.group("body")))
    for decl in re.finditer(r'extern\s+"C"\s+[^;{]+;', content):
        names.update(_function_decl_names(decl.group(0)))
    return names


def _included_header_declares_extern_c(ws: Workspace, impl: str, top: str) -> bool:
    for include in re.finditer(r'#include\s+"([^"]+)"', impl):
        header = ws.path(Path("src") / include.group(1))
        if header.is_file() and top in _extern_c_function_names(header.read_text(errors="ignore")):
            return True
    return False


def _function_decl_names(content: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;", content):
        name = match.group(1)
        if name not in {"if", "for", "while", "switch", "return"}:
            names.add(name)
    return names


def _check_reference_token_consistency(
    ws: Workspace,
    test_bundle: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    impl_path = ws.path("src/impl.cpp")
    if not impl_path.is_file():
        return
    impl_tokens = _extract_named_byte_arrays(impl_path.read_text(errors="ignore"))
    reference_values = _select_reference_array(impl_tokens)
    if reference_values is None:
        return

    for file_obj in test_bundle.get("files", []):
        path = str(file_obj.get("path", ""))
        if not path.startswith("tests/") or Path(path).suffix.lower() not in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}:
            continue
        test_arrays = _extract_named_byte_arrays(str(file_obj.get("content", "")))
        for name, values in test_arrays.items():
            lower_name = name.lower()
            if values != reference_values and (
                "ref" in lower_name
                or "match" in lower_name
                or "token" in lower_name
            ):
                issues.append({
                    "path": path,
                    "issue": "reference_token_mismatch",
                    "detail": f"`{name}` does not match the internal reference token in src/impl.cpp; derive all-match vectors from the implementation instead of inventing constants.",
                })
                break


def _select_reference_array(arrays: dict[str, tuple[int, ...]]) -> tuple[int, ...] | None:
    for name, values in arrays.items():
        if len(values) == 16 and "ref" in name.lower():
            return values
    return None


def _extract_named_byte_arrays(content: str) -> dict[str, tuple[int, ...]]:
    arrays: dict[str, tuple[int, ...]] = {}
    pattern = re.compile(
        r"(?:static\s+)?(?:const\s+)?(?:uint8_t|unsigned\s+char)\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\])+\s*=\s*\{(?P<body>[^{}]+)\}",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(content):
        values = []
        for token in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", match.group("body")):
            try:
                values.append(int(token, 0))
            except ValueError:
                pass
        if values:
            arrays[match.group("name")] = tuple(values)
    return arrays


def _check_synth_script(content: str, issues: list[dict[str, str]]) -> None:
    references_synth_rtl = bool(re.search(r"synth_out/[^ \n;&|)]+\.v\b", content))
    uses_broader_search = (
        "HLS_output" in content
        or re.search(r"\bfind\b[^;\n]*\.v", content)
        or re.search(r"\bshopt\b[^;\n]*globstar", content)
        or "**/*.v" in content
    )
    if references_synth_rtl and not uses_broader_search:
        issues.append({
            "path": "tests/run_synth.sh",
            "issue": "brittle_synth_rtl_path",
            "detail": "Bambu may emit RTL at the workspace root or under HLS_output; do not require only synth_out/<top>.v.",
        })


def _check_cosim_script(
    content: str,
    bundle_paths: set[str],
    issues: list[dict[str, str]],
) -> None:
    if "bambu " not in content or "--simulate" not in content:
        issues.append({
            "path": "tests/run_cosim.sh",
            "issue": "missing_bambu_simulate",
            "detail": "run_cosim.sh must run Bambu with --simulate for co-simulation.",
        })

    for match in re.finditer(r"--generate-tb(?:=|\s+)([^\s\\]+)", content):
        raw_arg = match.group(1).strip("'\"")
        tb_path = _clean_shell_token(raw_arg)
        suffix = Path(tb_path).suffix.lower()
        if suffix == ".xml":
            issues.append({
                "path": "tests/run_cosim.sh",
                "issue": "hallucinated_bambu_xml_testbench",
                "detail": "Do not pass invented XML test vectors to --generate-tb; use a C/C++ tb_cosim file unless an exact Bambu XML schema is provided.",
            })
        elif suffix in {".c", ".cc", ".cpp", ".cxx"} and tb_path not in bundle_paths:
            issues.append({
                "path": "tests/run_cosim.sh",
                "issue": "missing_cosim_testbench_file",
                "detail": f"`--generate-tb` references {tb_path}, but that file is not in the tester bundle.",
            })

    for xml_path in sorted(p for p in bundle_paths if Path(p).suffix.lower() == ".xml"):
        issues.append({
            "path": xml_path,
            "issue": "unverified_bambu_xml_schema",
            "detail": "Tester-generated Bambu XML schemas are not accepted without an exact schema from project context.",
        })

    if re.search(r'grep\s+-q\s+["\']Simulation completed["\']', content):
        issues.append({
            "path": "tests/run_cosim.sh",
            "issue": "brittle_bambu_completion_grep",
            "detail": "Do not require a Bambu log phrase unless the script emits it itself after checking the Bambu exit code.",
        })


def _clean_shell_token(token: str) -> str:
    try:
        parts = split(token)
    except ValueError:
        return token
    return parts[0] if parts else token
