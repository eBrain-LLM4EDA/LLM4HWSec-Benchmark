import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from .models import ParseResult, SyntaxResult


VERILOG_BLOCK_RE = re.compile(r"```(?:verilog|systemverilog)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_llm_artifacts(response_text: str) -> ParseResult:
    """Extract Verilog code block and a short natural-language summary."""
    notes: List[str] = []
    matches = VERILOG_BLOCK_RE.findall(response_text)
    if not matches:
        notes.append("No fenced Verilog block detected; using full response as Verilog payload")
        return ParseResult(verilog=response_text.strip(), summary="", parse_notes=notes)

    verilog = matches[0].strip()
    if len(matches) > 1:
        notes.append("Multiple Verilog blocks found; first block used")

    response_wo_code = VERILOG_BLOCK_RE.sub("", response_text)
    summary = " ".join(line.strip() for line in response_wo_code.splitlines() if line.strip())
    return ParseResult(verilog=verilog, summary=summary, parse_notes=notes)


def builtin_syntax_check(verilog_text: str) -> SyntaxResult:
    """Fast syntax checks that do not require external tools."""
    notes: List[str] = []
    module_count = len(re.findall(r"\bmodule\b", verilog_text))
    endmodule_count = len(re.findall(r"\bendmodule\b", verilog_text))
    if module_count == 0:
        notes.append("No module declaration found")
    if module_count != endmodule_count:
        notes.append("module/endmodule count mismatch")

    for idx, line in enumerate(verilog_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if re.match(r"^(module|endmodule|begin|end|else|if\b|always\b|generate\b|endgenerate\b)", stripped):
            continue
        if stripped.endswith((";", ")", "(", "}", "{")):
            continue
        if re.search(r"\b(assign|wire|reg|logic|input|output|inout)\b", stripped) and not stripped.endswith(";"):
            notes.append(f"Line {idx}: likely missing semicolon")

    return SyntaxResult(passed=not notes, notes=notes, tool="builtin")


def tool_syntax_check(verilog_text: str) -> SyntaxResult:
    """Try Verilator or Icarus Verilog for strict syntax checks."""
    for tool in ("verilator", "iverilog"):
        if shutil.which(tool):
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "candidate.v"
                path.write_text(verilog_text)
                try:
                    if tool == "verilator":
                        cmd = ["verilator", "--lint-only", str(path)]
                    else:
                        cmd = ["iverilog", "-tnull", str(path)]
                    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                except Exception as exc:
                    return SyntaxResult(passed=False, notes=[f"{tool} invocation failed: {exc}"], tool=tool)

                if proc.returncode == 0:
                    return SyntaxResult(passed=True, notes=[], tool=tool)
                msg = (proc.stderr or proc.stdout).strip()
                return SyntaxResult(passed=False, notes=[msg or f"{tool} reported a syntax error"], tool=tool)

    return builtin_syntax_check(verilog_text)
