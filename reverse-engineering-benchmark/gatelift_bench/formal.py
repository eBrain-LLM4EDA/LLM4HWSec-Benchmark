import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import FormalResult
from .verilog_utils import get_module_name


def run_formal_equivalence(ground_truth_verilog: str, candidate_verilog: str, top_module: str = "") -> FormalResult:
    """Run Yosys SAT-based equivalence check between reference and candidate RTL."""
    if not shutil.which("yosys"):
        return FormalResult(
            score=0.0,
            passed=False,
            notes=["Yosys not installed; FE metric reported as 0.0"],
            tool="yosys",
        )

    top = top_module or get_module_name(ground_truth_verilog)
    with tempfile.TemporaryDirectory() as td:
        gold_path = Path(td) / "gold.v"
        cand_path = Path(td) / "candidate.v"
        script_path = Path(td) / "equiv.ys"

        gold_path.write_text(ground_truth_verilog)
        cand_path.write_text(candidate_verilog)

        script = f"""
read_verilog {gold_path}
prep -top {top}
design -stash gold

read_verilog {cand_path}
prep -top {top}
design -stash gate

design -copy-from gold -as gold {top}
design -copy-from gate -as gate {top}

equiv_make gold gate equiv
prep -top equiv
equiv_simple
equiv_status -assert
"""
        script_path.write_text(script)

        proc = subprocess.run(["yosys", "-q", str(script_path)], capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return FormalResult(score=1.0, passed=True, notes=["Formal equivalence proven"], tool="yosys")

        msg = (proc.stderr or proc.stdout).strip()
        return FormalResult(score=0.0, passed=False, notes=[msg or "Formal equivalence failed"], tool="yosys")
