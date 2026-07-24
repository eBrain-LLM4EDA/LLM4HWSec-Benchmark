from __future__ import annotations
from .logio import console

import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class DockerConfig:
    """Isolation settings for the shared evaluation container.

    A single image is reused for every test case and every mutant run — the
    case workspace is bind-mounted in at /work, never baked into the image.
    Extra analysis tools (yosys, iverilog, verilator, ...) can be added to the
    image over time without changing this runner; evaluators simply invoke them.
    """

    image: str = "agentic-bench-gen-runner:latest"
    network: str = "none"
    memory_limit: str = "2g"
    cpus: str = "2.0"
    pids_limit: int = 512
    workdir: str = "/work"
    extra_args: list[str] = field(default_factory=list)


class EvaluationRunner:
    def __init__(
        self,
        timeout_seconds: int = 60,
        use_docker: bool = False,
        docker: DockerConfig | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.use_docker = use_docker
        self.docker = docker or DockerConfig()

    def check_available(self) -> None:
        """Fail fast if Docker isolation is requested but not usable.

        Called once at pipeline startup so a missing daemon / un-built image is
        reported clearly instead of surfacing as every baseline run "failing".
        """
        if not self.use_docker:
            return
        if shutil.which("docker") is None:
            raise RuntimeError(
                "execution.use_docker is enabled but the 'docker' binary was not found on PATH."
            )
        probe = subprocess.run(
            ["docker", "image", "inspect", self.docker.image],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                f"Docker image {self.docker.image!r} not found. Build the shared runner image first:\n"
                f"  docker build -t {self.docker.image} docker/"
            )
        # Smoke-test the bind mount: on macOS, temp dirs outside Docker Desktop's
        # file-sharing list mount as empty, which would surface as every single
        # evaluator run "failing" instead of one clear startup error.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            (Path(tmpdir) / "marker.txt").write_text("mount-ok")
            smoke = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--network", self.docker.network,
                    "-v", f"{tmpdir}:{self.docker.workdir}",
                    "-w", self.docker.workdir,
                    self.docker.image,
                    "python3", "-c", "print(open('marker.txt').read().strip())",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        if smoke.returncode != 0 or "mount-ok" not in smoke.stdout:
            raise RuntimeError(
                "Docker bind-mount smoke test failed — evaluator runs would all fail. "
                "Check that the daemon is running and the system temp directory is in "
                "Docker's file-sharing list.\n"
                f"exit={smoke.returncode} stdout={smoke.stdout[:200]!r} stderr={smoke.stderr[:400]!r}"
            )

    def run_evaluator(self, workspace: Path, mutant_dir: Path | None = None) -> dict[str, Any]:
        """
        Runs evaluation/evaluate.py against a copy of the workspace.

        Copies the participant inputs, evaluator, and supporting harness files
        to a temp directory, excluding private generation artifacts such as the
        golden solution. It then overlays mutant_dir files on top before
        executing evaluate.py. A non-zero exit code is returned as
        status="fail", meaning the mutant was detected.

        When use_docker is set the evaluator runs inside the shared, network-
        isolated container instead of directly on the host; otherwise it runs
        as a host subprocess (used by the unit tests and Docker-less setups).
        """
        # ignore_cleanup_errors so root-owned files written by the container do
        # not raise during temp-dir teardown.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp = Path(tmpdir)

            # Generated evaluators are untrusted. They need public inputs,
            # submissions, and Tester-owned harnesses, but must never be able to
            # read the Expert's answer or generation reports from the sandbox.
            shutil.copytree(
                workspace, tmp, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "mutant_*", "golden", "ground_truth", "expert", "mutants",
                    "reports", "artifacts",
                ),
            )

            # Overlay mutant files, replacing the originals they target
            if mutant_dir is not None and Path(mutant_dir).exists():
                self._copy_overlay(Path(mutant_dir), tmp)

            eval_script = tmp / "evaluation" / "evaluate.py"
            if not eval_script.exists():
                return {
                    "status": "error",
                    "error": "No evaluate.py found at evaluation/evaluate.py",
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "",
                }

            if self.use_docker:
                return self._run_docker(tmp)
            return self._run_host(tmp, eval_script)

    @staticmethod
    def _copy_overlay(source: Path, destination: Path) -> None:
        """Copy overlay contents without applying source-root permissions.

        `copytree(..., dirs_exist_ok=True)` copies the source directory's mode
        onto the destination root. Temporary overlay roots are normally 0700,
        which made `/work` inaccessible to the non-root Docker user after a
        golden or mutant overlay. Copying entries individually preserves the
        already-accessible sandbox root.
        """
        for item in source.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Overlay symlinks are not allowed: {item}")
            target = destination / item.relative_to(source)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    def _run_host(self, tmp: Path, eval_script: Path) -> dict[str, Any]:
        start = time.time()
        try:
            proc = subprocess.run(
                ["python3", str(eval_script.absolute())],
                cwd=str(tmp),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
            return self._result(proc.returncode, proc.stdout, proc.stderr, time.time() - start)
        except subprocess.TimeoutExpired as exc:
            return self._timeout_result(exc.stdout, exc.stderr)

    def _run_docker(self, tmp: Path) -> dict[str, Any]:
        container = f"benchgen-eval-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "--rm",
            "--name", container,
            "--network", self.docker.network,
            "--memory", self.docker.memory_limit,
            "--cpus", str(self.docker.cpus),
            "--pids-limit", str(self.docker.pids_limit),
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "-v", f"{tmp}:{self.docker.workdir}",
            "-w", self.docker.workdir,
            *self.docker.extra_args,
            self.docker.image,
            "python3", "evaluation/evaluate.py",
        ]
        start = time.time()
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=self.timeout_seconds)
            # 125/126/127 are docker CLI/daemon failures (run failed, command not
            # invocable/found), not an evaluator verdict — report them as errors
            # so they are never counted as "mutant detected".
            if proc.returncode in (125, 126, 127):
                return {
                    "status": "error",
                    "error": f"docker run failed with exit code {proc.returncode}",
                    "returncode": proc.returncode,
                    "stdout": (proc.stdout or "")[-20000:],
                    "stderr": (proc.stderr or "")[-20000:],
                    "duration": time.time() - start,
                }
            return self._result(proc.returncode, proc.stdout, proc.stderr, time.time() - start)
        except subprocess.TimeoutExpired as exc:
            # Best-effort teardown so a hung evaluator container does not linger.
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)
            return self._timeout_result(exc.stdout, exc.stderr)

    @staticmethod
    def _result(returncode: int | None, stdout: str | None, stderr: str | None, duration: float) -> dict[str, Any]:
        return {
            "status": "pass" if returncode == 0 else "fail",
            "returncode": returncode,
            "stdout": (stdout or "")[-20000:],
            "stderr": (stderr or "")[-20000:],
            "duration": duration,
        }

    def _timeout_result(self, stdout: Any, stderr: Any) -> dict[str, Any]:
        return {
            "status": "timeout",
            "returncode": None,
            "stdout": (stdout or "")[-20000:] if isinstance(stdout, str) else "",
            "stderr": (stderr or "")[-20000:] if isinstance(stderr, str) else "",
            "duration": self.timeout_seconds,
        }
