from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

class EvaluationRunner:
    def __init__(self, timeout_seconds: int = 60, use_docker: bool = False):
        self.timeout_seconds = timeout_seconds
        self.use_docker = use_docker

    def run_evaluator(self, workspace: Path, mutant_dir: Path | None = None) -> dict[str, Any]:
        """
        Runs evaluation/evaluate.py from a copy of the workspace.

        Copies the full workspace tree to a temp directory so evaluation/,
        tests/, inputs/, golden/ and ground_truth/ are all available, then
        overlays mutant_dir files on top (overwriting originals) before
        executing evaluate.py.  A non-zero exit code is returned as
        status="fail", meaning the mutant was detected.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Copy full workspace so the evaluator has all supporting files
            shutil.copytree(workspace, tmp, dirs_exist_ok=True)

            # Overlay mutant files, replacing the originals they target
            if mutant_dir is not None and mutant_dir.exists():
                shutil.copytree(mutant_dir, tmp, dirs_exist_ok=True)

            eval_script = tmp / "evaluation" / "evaluate.py"
            if not eval_script.exists():
                return {
                    "status": "error",
                    "error": "No evaluate.py found at evaluation/evaluate.py",
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "",
                }

            start = time.time()
            try:
                proc = subprocess.run(
                    ["python3", str(eval_script.absolute())],
                    cwd=str(tmp),
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                )
                duration = time.time() - start
                return {
                    "status": "pass" if proc.returncode == 0 else "fail",
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-20000:],
                    "stderr": proc.stderr[-20000:],
                    "duration": duration,
                }
            except subprocess.TimeoutExpired as exc:
                return {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
                    "stderr": (exc.stderr or "")[-20000:] if isinstance(exc.stderr, str) else "",
                    "duration": self.timeout_seconds,
                }
