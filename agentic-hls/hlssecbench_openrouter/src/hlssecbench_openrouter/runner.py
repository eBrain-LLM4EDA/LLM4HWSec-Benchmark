from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from shlex import quote
from typing import Any

from .utils import write_json


@dataclass
class CommandStep:
    name: str
    command: str
    required: bool = False


@dataclass
class ExecutionConfig:
    allow_execution: bool
    timeout_seconds: int
    steps: list[CommandStep] = field(default_factory=list)
    docker_enabled: bool = False
    docker_image: str = ""
    docker_platform: str = ""


class ToolRunner:
    def __init__(self, config: ExecutionConfig):
        self.config = config

    def _wrap_command(self, step: CommandStep, workspace: Path) -> str:
        """Wrap a step command in a Docker invocation when Docker is enabled.

        The workspace directory is bind-mounted to /workspace inside the
        container so that all generated files (C sources, test scripts,
        reports …) are accessible to the Bambu toolchain.
        """
        if self.config.docker_enabled and self.config.docker_image:
            # Escape single-quotes in the inner command so it survives the
            # outer sh -c '...' wrapper.
            escaped = quote(step.command)
            volume = quote(f"{workspace}:/workspace")
            image = quote(self.config.docker_image)
            platform = (
                f"--platform {quote(self.config.docker_platform)} "
                if self.config.docker_platform
                else ""
            )
            return (
                f"docker run --rm "
                f"{platform}"
                f"-v {volume} "
                f"-w /workspace "
                f"{image} "
                f"sh -c {escaped}"
            )
        return step.command

    def run_all(self, workspace: str | Path) -> dict[str, Any]:
        workspace = Path(workspace).resolve()
        results: dict[str, Any] = {
            "allow_execution": self.config.allow_execution,
            "workspace": str(workspace),
            "steps": [],
        }

        for step in self.config.steps:
            if not self.config.allow_execution:
                results["steps"].append({
                    "name": step.name,
                    "command": step.command,
                    "status": "not_run",
                    "required": step.required,
                    "stdout": "",
                    "stderr": "Execution disabled (allow_execution: false).",
                    "returncode": None,
                    "duration_seconds": 0.0,
                })
                continue

            cmd = self._wrap_command(step, workspace)
            start = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(workspace),
                    shell=True,
                    text=True,
                    capture_output=True,
                    timeout=self.config.timeout_seconds,
                )
                duration = time.monotonic() - start
                results["steps"].append({
                    "name": step.name,
                    "command": step.command,
                    "status": "pass" if proc.returncode == 0 else "fail",
                    "required": step.required,
                    "stdout": proc.stdout[-20_000:],
                    "stderr": proc.stderr[-20_000:],
                    "returncode": proc.returncode,
                    "duration_seconds": round(duration, 3),
                })
            except subprocess.TimeoutExpired as exc:
                results["steps"].append({
                    "name": step.name,
                    "command": step.command,
                    "status": "timeout",
                    "required": step.required,
                    "stdout": (exc.stdout or "")[-20_000:] if isinstance(exc.stdout, str) else "",
                    "stderr": (exc.stderr or "")[-20_000:] if isinstance(exc.stderr, str) else "",
                    "returncode": None,
                    "duration_seconds": float(self.config.timeout_seconds),
                })

        write_json(workspace / "reports" / "execution_results.json", results)
        return results


def parse_execution_config(raw: dict[str, Any]) -> ExecutionConfig:
    exec_raw = raw.get("execution", {})
    docker_raw = exec_raw.get("docker", {})
    return ExecutionConfig(
        allow_execution=bool(exec_raw.get("allow_execution", False)),
        timeout_seconds=int(exec_raw.get("timeout_seconds", 180)),
        docker_enabled=bool(docker_raw.get("enabled", False)),
        docker_image=str(docker_raw.get("image", "")),
        docker_platform=str(docker_raw.get("platform", "")),
        steps=[
            CommandStep(
                name=s["name"],
                command=s["command"],
                required=bool(s.get("required", False)),
            )
            for s in exec_raw.get("steps", [])
        ],
    )
