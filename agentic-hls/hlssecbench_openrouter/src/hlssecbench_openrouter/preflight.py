from __future__ import annotations

import re
import subprocess
from typing import Any

from .workspace import Workspace


def preflight_tester_bundle(ws: Workspace, test_bundle: dict[str, Any]) -> dict[str, Any]:
    required = {
        "tests/run_csim.sh",
        "tests/run_synth.sh",
        "tests/run_cosim.sh",
        "tests/run_rtl_security.sh",
    }
    bundle_paths = {str(file_obj.get("path", "")) for file_obj in test_bundle.get("files", [])}
    issues: list[dict[str, str]] = []

    for path in sorted(required - bundle_paths):
        issues.append({"path": path, "issue": "missing_required_bundle_file"})

    tb_files = [p for p in bundle_paths if re.fullmatch(r"tests/tb_.+\.cpp", p)]
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

        if path.startswith("tests/") and path.endswith(".cpp"):
            if "printf(" in content and "#include <cstdio>" not in content and "#include <stdio.h>" not in content:
                issues.append({
                    "path": path,
                    "issue": "printf_without_header",
                    "detail": "C++ testbenches using printf must include <cstdio> or <stdio.h>.",
                })

        if path == "tests/run_csim.sh":
            if "operator uint64_t()" in content and not re.search(r"operator\s*!=\s*\([^)]*(int|uint64_t|unsigned)", content):
                issues.append({
                    "path": path,
                    "issue": "ap_uint_integral_compare_ambiguous",
                    "detail": "The fallback ap_uint shim converts to uint64_t but lacks integral comparison overloads.",
                })

    report = {
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }
    ws.write_json("reports/tester_preflight.json", report)
    return report
