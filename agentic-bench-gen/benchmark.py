#!/usr/bin/env python3
"""
benchmark.py — OpenAI-compatible runner for LLM4HWSec-Benchmark.

Designed for:
  https://github.com/eBrain-LLM4EDA/LLM4HWSec-Benchmark

The runner:
  1. Discovers benchmark cases.
  2. Copies each case to an isolated run directory.
  3. Sends only participant-facing material to the model:
       - README.md
       - inputs/**
       - existing submission/** starter files
  4. Requires the model to return a JSON file bundle.
  5. Writes only explicitly allowed submission paths.
  6. Runs evaluation/evaluate.py.
  7. Logs per-case results to JSONL and writes aggregate summaries.

No benchmark-internal golden/expert/tests/evaluation/spec/reports contents are
sent to the model.

Example:
    python benchmark.py \
      --cases agentic-bench-gen/testcases \
      --base-url http://127.0.0.1:8001/v1 \
      --model Qwen/Qwen2.5-Coder-7B-Instruct \
      --output runs/qwen25coder \
      --limit 10

Dependencies:
    Python 3.10+.
    No OpenAI SDK is required; HTTP calls use the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Benchmark submission contracts
# ---------------------------------------------------------------------------

# Mirrors agentic_bench_gen/domains.py in the benchmark repository.
DOMAIN_CONTRACTS: dict[str, dict[str, Any]] = {
    "hls_security_codegen": {
        "submission_kind": "hardened_artifact",
        "submission_artifacts": [],
    },
    "rtl_trojan_detection": {
        "submission_kind": "analysis_report",
        "submission_artifacts": ["trojan_report.json"],
    },
    "gate_trojan_detection": {
        "submission_kind": "analysis_report",
        "submission_artifacts": ["trojan_report.json"],
    },
    "hardware_reverse_engineering": {
        "submission_kind": "analysis_report",
        "submission_artifacts": ["recovered_rtl.v"],
    },
    "side_channel_fault_analysis": {
        "submission_kind": "analysis_report",
        "submission_artifacts": ["vulnerability_report.json"],
    },
    "logic_deobfuscation_sat": {
        "submission_kind": "analysis_report",
        "submission_artifacts": ["recovered_key.json"],
    },
}

CODE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".v", ".sv", ".vhd", ".vhdl", ".py", ".tcl",
}

TEXT_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".v", ".sv", ".vhd", ".vhdl",
    ".py", ".tcl",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
    ".csv", ".tsv", ".sdc", ".xdc",
}

# Files/directories that must never enter the model prompt.
PRIVATE_TOP_LEVEL = {
    "golden",
    "expert",
    "tests",
    "evaluation",
    "mutants",
    "reports",
    "spec",
    "artifacts",
}

# Metadata files are useful to the benchmark infrastructure but should not be
# needed by the participant model.
PRIVATE_FILES = {
    "case_manifest.json",
    "run_manifest.json",
}


@dataclass
class CaseInfo:
    source_dir: Path
    case_id: str
    domain: str | None
    allowed_paths: list[str]


@dataclass
class APIResult:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_s: float
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized_relpath(raw: str) -> str:
    """
    Normalize a model-provided path and reject absolute/traversal paths.
    Always returns a POSIX-style workspace-relative path.
    """
    raw = raw.strip().replace("\\", "/")
    p = PurePosixPath(raw)

    if p.is_absolute():
        raise ValueError(f"absolute path is forbidden: {raw!r}")

    parts = p.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe relative path: {raw!r}")

    return str(p)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" not in data


def read_text_safely(path: Path, max_bytes: int) -> tuple[str, bool]:
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    text = data.decode("utf-8", errors="replace")
    return text, truncated


def iter_public_files(case_dir: Path) -> Iterable[Path]:
    """
    Participant-visible files only.

    README.md is included separately. Here we expose inputs/** and existing
    submission/** starter files. Hidden benchmark internals are deliberately
    excluded.
    """
    for root_name in ("inputs", "submission"):
        root = case_dir / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and is_text_file(path):
                yield path


def discover_cases(cases_root: Path) -> list[Path]:
    """
    A case is a directory containing README.md and evaluation/evaluate.py.
    Search recursively so the runner also works if the repo groups cases.
    """
    found: list[Path] = []
    for readme in cases_root.rglob("README.md"):
        case_dir = readme.parent
        if (case_dir / "evaluation" / "evaluate.py").is_file():
            found.append(case_dir)
    return sorted(set(found), key=lambda p: p.as_posix())


def load_case_grades(path: Path) -> dict[str, str]:
    """
    Map case_id -> letter grade from case_grades.json (produced by the
    benchmark's spec-integrity/mutation-testing grading pass).

    Keys in that file look like "testcases/<case_id>" (optionally nested
    deeper, e.g. under a set directory); only the final path component is
    used as the case_id, so this works regardless of --cases layout.
    """
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} does not contain a JSON object")

    grades: dict[str, str] = {}
    for key, entry in obj.items():
        if not isinstance(entry, dict):
            continue
        grade = entry.get("grade")
        if not isinstance(grade, str):
            continue
        case_id = PurePosixPath(key).name
        grades[case_id] = grade
    return grades


# ---------------------------------------------------------------------------
# Domain and submission-path inference
# ---------------------------------------------------------------------------

def extract_domain_from_json(path: Path) -> str | None:
    """
    Read domain from local case metadata without exposing the metadata to the
    model. Supports likely keys used by generated benchmark manifests/specs.
    """
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    candidates: list[Any] = [
        obj.get("domain_id"),
        obj.get("domain"),
        obj.get("task_domain"),
    ]
    for parent_key in ("public_spec", "task_spec", "spec", "metadata"):
        v = obj.get(parent_key)
        if isinstance(v, dict):
            candidates.extend([
                v.get("domain_id"),
                v.get("domain"),
                v.get("task_domain"),
            ])

    for value in candidates:
        if isinstance(value, str) and value in DOMAIN_CONTRACTS:
            return value
    return None


def infer_domain(case_dir: Path) -> str | None:
    # Prefer explicit metadata if present.
    metadata_candidates = [
        case_dir / "case_manifest.json",
        case_dir / "spec" / "public_spec.json",
        case_dir / "spec" / "task_spec.json",
    ]
    for path in metadata_candidates:
        domain = extract_domain_from_json(path)
        if domain:
            return domain

    # Fall back to directory name hints.
    name = case_dir.name.lower()
    hints = {
        "hls": "hls_security_codegen",
        "rtl_trojan": "rtl_trojan_detection",
        "gate_trojan": "gate_trojan_detection",
        "reverse": "hardware_reverse_engineering",
        "side_channel": "side_channel_fault_analysis",
        "fault": "side_channel_fault_analysis",
        "deobfus": "logic_deobfuscation_sat",
        "logic_lock": "logic_deobfuscation_sat",
        "sat": "logic_deobfuscation_sat",
    }
    for needle, domain in hints.items():
        if needle in name:
            return domain

    # Last fallback: inspect README terminology.
    readme_path = case_dir / "README.md"
    if readme_path.is_file():
        text = readme_path.read_text(encoding="utf-8", errors="replace").lower()
        readme_hints = [
            ("trojan_report.json", "rtl_trojan_detection"),
            ("vulnerability_report.json", "side_channel_fault_analysis"),
            ("recovered_key.json", "logic_deobfuscation_sat"),
            ("recovered_rtl.v", "hardware_reverse_engineering"),
            ("hls", "hls_security_codegen"),
        ]
        for needle, domain in readme_hints:
            if needle in text:
                return domain

    return None


def explicit_paths_from_readme(readme: str) -> list[str]:
    """
    Extract workspace paths quoted in README. This is used only as a conservative
    hint for HLS hardened-artifact cases.
    """
    paths: list[str] = []
    for match in re.finditer(r"`((?:inputs|submission)/[^`\s]+)`", readme):
        raw = match.group(1).rstrip(".,;:)")
        try:
            rel = normalized_relpath(raw)
        except ValueError:
            continue
        if rel not in paths:
            paths.append(rel)
    return paths


def infer_allowed_paths(case_dir: Path, domain: str | None) -> list[str]:
    """
    Determine files the model may write.

    Analysis-report domains have fixed submission files from domains.py.

    Hardened HLS cases are trickier because the exact code input filename is
    case-specific. We conservatively infer code files under inputs/ mentioned in
    README, preferring language such as "modify", "edit", and "submission".
    """
    if domain in DOMAIN_CONTRACTS:
        contract = DOMAIN_CONTRACTS[domain]
        if contract["submission_kind"] == "analysis_report":
            return [
                f"submission/{name}"
                for name in contract["submission_artifacts"]
            ]

    readme_path = case_dir / "README.md"
    readme = (
        readme_path.read_text(encoding="utf-8", errors="replace")
        if readme_path.is_file()
        else ""
    )

    mentioned = explicit_paths_from_readme(readme)
    code_mentions = [
        p for p in mentioned
        if p.startswith("inputs/") and Path(p).suffix.lower() in CODE_EXTENSIONS
    ]

    # Rank code paths by context indicating participant modification.
    scored: list[tuple[int, str]] = []
    lower = readme.lower()
    for rel in code_mentions:
        basename = PurePosixPath(rel).name.lower()
        score = 0
        for m in re.finditer(re.escape(rel.lower()), lower):
            lo = max(0, m.start() - 120)
            hi = min(len(lower), m.end() + 120)
            context = lower[lo:hi]
            for token, weight in [
                ("only modify", 10),
                ("may only modify", 10),
                ("should edit", 8),
                ("file you should edit", 8),
                ("you should edit", 7),
                ("modify", 5),
                ("edit", 5),
                ("submission", 3),
                ("replace", 3),
                ("harden", 2),
            ]:
                if token in context:
                    score += weight
        if basename in lower:
            score += 1
        scored.append((score, rel))

    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        best_score = scored[0][0]
        # Keep all strongly indicated files, or at least the top one.
        allowed = [p for s, p in scored if s >= max(5, best_score - 4)]
        if allowed:
            return sorted(set(allowed))

    # Fallback for hardened-artifact cases: all code files directly under
    # inputs/. This is intentionally conservative and does not include docs.
    fallback = []
    inputs = case_dir / "inputs"
    if inputs.is_dir():
        for path in sorted(inputs.rglob("*")):
            if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS:
                fallback.append(path.relative_to(case_dir).as_posix())
    return fallback


def inspect_case(case_dir: Path) -> CaseInfo:
    domain = infer_domain(case_dir)
    allowed_paths = infer_allowed_paths(case_dir, domain)
    return CaseInfo(
        source_dir=case_dir,
        case_id=case_dir.name,
        domain=domain,
        allowed_paths=allowed_paths,
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert hardware-security and hardware-design engineer solving a benchmark task.

You are operating on a COPY of one benchmark testcase. Follow the participant-facing README exactly.

Critical rules:
1. You may use ONLY the task statement and participant-facing files shown to you.
2. Do not ask for hidden tests, golden answers, evaluator code, private specs, or benchmark metadata.
3. Modify/create ONLY the explicitly allowed output paths.
4. Preserve pinned interfaces and required file formats exactly.
5. Return ONLY one JSON object matching this schema:
   {"files":[{"path":"workspace/relative/path","content":"complete file contents"}]}
6. Every listed file must contain the COMPLETE final contents, not a diff.
7. Do not wrap the JSON in Markdown fences.
8. Do not include explanations outside the JSON.
"""


def build_prompt(
    case_dir: Path,
    info: CaseInfo,
    max_file_bytes: int,
    max_prompt_chars: int,
) -> str:
    readme = (case_dir / "README.md").read_text(
        encoding="utf-8", errors="replace"
    )

    chunks = [
        f"CASE ID: {info.case_id}",
        f"DOMAIN: {info.domain or 'unknown'}",
        "",
        "ALLOWED OUTPUT PATHS:",
    ]
    chunks.extend(f"- {p}" for p in info.allowed_paths)

    chunks.extend([
        "",
        "TASK README:",
        "<<<README",
        readme,
        "README",
        "",
        "PARTICIPANT-FACING FILES:",
    ])

    for path in iter_public_files(case_dir):
        rel = path.relative_to(case_dir).as_posix()
        text, truncated = read_text_safely(path, max_file_bytes)
        chunks.extend([
            f"",
            f"<<<FILE path={rel}",
            text,
            f"FILE{' [TRUNCATED]' if truncated else ''}",
        ])

    chunks.extend([
        "",
        "Return the final submission as the required JSON object. "
        "Do not modify any path not listed under ALLOWED OUTPUT PATHS.",
    ])

    prompt = "\n".join(chunks)
    if len(prompt) > max_prompt_chars:
        raise RuntimeError(
            f"prompt would be {len(prompt):,} characters, exceeding "
            f"--max-prompt-chars={max_prompt_chars:,}. Increase the limit or "
            f"reduce --max-file-bytes."
        )
    return prompt


# ---------------------------------------------------------------------------
# OpenAI-compatible HTTP client
# ---------------------------------------------------------------------------

def join_api_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


class ContextLengthExceededError(RuntimeError):
    """
    Raised when the server rejects a request because
    prompt_tokens + max_tokens exceeds the model's context window.

    Carries the server-reported context_length and input(prompt)_tokens
    (when parseable) so callers can shrink max_tokens and retry instead of
    failing the case outright.
    """

    def __init__(
        self,
        message: str,
        context_length: int | None,
        input_tokens: int | None,
    ) -> None:
        super().__init__(message)
        self.context_length = context_length
        self.input_tokens = input_tokens


# Matches the OpenAI/vLLM-style error body, e.g.:
#   "This model's maximum context length is 16384 tokens. However, you
#    requested 8192 output tokens and your prompt contains at least 8193
#    input tokens, for a total of at least 16385 tokens. ..."
_CONTEXT_LENGTH_ERROR_RE = re.compile(
    r"maximum context length is (\d+) tokens.*?"
    r"prompt contains at least (\d+) input tokens",
    re.IGNORECASE | re.DOTALL,
)


def api_json_request(
    url: str,
    payload: dict[str, Any] | None,
    api_key: str,
    timeout_s: float,
    method: str = "POST",
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = f"HTTP {exc.code} from {url}: {body[:4000]}"
        match = _CONTEXT_LENGTH_ERROR_RE.search(body)
        if match:
            raise ContextLengthExceededError(
                message,
                context_length=int(match.group(1)),
                input_tokens=int(match.group(2)),
            ) from exc
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request to {url} failed: {exc}") from exc


def compute_shrunk_max_tokens(
    current_max_tokens: int,
    context_length: int | None,
    input_tokens: int | None,
    margin: int = 64,
    min_tokens: int = 64,
) -> int | None:
    """
    Given a context-length-exceeded error's reported context_length and
    input_tokens, compute a smaller max_tokens that should fit, or None if
    no safe reduction is possible (unknown counts, budget too small, or the
    computed budget would not actually be smaller than what was requested).
    """
    if context_length is None or input_tokens is None:
        return None
    budget = context_length - input_tokens - margin
    if budget < min_tokens or budget >= current_max_tokens:
        return None
    return budget


def resolve_model(base_url: str, api_key: str, timeout_s: float) -> str:
    obj = api_json_request(
        join_api_url(base_url, "models"),
        payload=None,
        api_key=api_key,
        timeout_s=timeout_s,
        method="GET",
    )
    models = obj.get("data")
    if not isinstance(models, list) or not models:
        raise RuntimeError("GET /v1/models returned no models")
    model_id = models[0].get("id")
    if not isinstance(model_id, str) or not model_id:
        raise RuntimeError("first /v1/models entry has no string id")
    return model_id


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    seed: int | None,
    extra_body: dict[str, Any],
) -> APIResult:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        payload["seed"] = seed
    payload.update(extra_body)

    started = time.perf_counter()
    raw = api_json_request(
        join_api_url(base_url, "chat/completions"),
        payload=payload,
        api_key=api_key,
        timeout_s=timeout_s,
        method="POST",
    )
    latency_s = time.perf_counter() - started

    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"response has no choices: {raw}")

    message = choices[0].get("message", {})
    text = message.get("content")
    if not isinstance(text, str):
        # Some reasoning servers may place visible output elsewhere.
        text = choices[0].get("text")
    if not isinstance(text, str):
        raise RuntimeError(f"response has no textual content: {raw}")

    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    return APIResult(
        text=text,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        latency_s=latency_s,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Model output parsing and safe materialization
# ---------------------------------------------------------------------------

def extract_json_object(text: str) -> dict[str, Any]:
    """
    Accept strict JSON, a fenced JSON block, or text containing one balanced
    top-level JSON object. The benchmark prompt asks for strict JSON, but this
    makes local-model evaluation less brittle.
    """
    stripped = text.strip()

    # 1. Strict JSON.
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced JSON.
    fence = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fence:
        try:
            obj = json.loads(fence.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3. Find balanced JSON object while respecting JSON strings.
    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = stripped.find("{", start + 1)

    raise ValueError("model response did not contain a valid JSON object")


def parse_file_bundle(
    text: str,
    allowed_paths: list[str],
) -> dict[str, str]:
    obj = extract_json_object(text)
    files = obj.get("files")
    if not isinstance(files, list):
        raise ValueError("JSON must contain a 'files' array")

    allowed = {normalized_relpath(p) for p in allowed_paths}
    bundle: dict[str, str] = {}

    for i, item in enumerate(files):
        if not isinstance(item, dict):
            raise ValueError(f"files[{i}] is not an object")
        raw_path = item.get("path")
        content = item.get("content")
        if not isinstance(raw_path, str):
            raise ValueError(f"files[{i}].path must be a string")
        if not isinstance(content, str):
            raise ValueError(f"files[{i}].content must be a string")

        path = normalized_relpath(raw_path)
        if path not in allowed:
            raise ValueError(
                f"model attempted forbidden output path {path!r}; "
                f"allowed: {sorted(allowed)}"
            )
        if path in bundle:
            raise ValueError(f"duplicate output path {path!r}")
        bundle[path] = content

    missing = sorted(allowed - set(bundle))
    if missing:
        raise ValueError(
            "model omitted required output file(s): " + ", ".join(missing)
        )

    return bundle


def materialize_bundle(case_dir: Path, bundle: dict[str, str]) -> None:
    root = case_dir.resolve()
    for rel, content in bundle.items():
        target = (case_dir / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"output escapes testcase root: {rel}") from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def run_grader_host(
    case_dir: Path,
    python_executable: str,
    timeout_s: float,
) -> dict[str, Any]:
    cmd = [python_executable, "evaluation/evaluate.py"]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=case_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
        elapsed = time.perf_counter() - started
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": elapsed,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": cmd,
            "returncode": None,
            "passed": False,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_s": elapsed,
            "timed_out": True,
        }


def run_grader_docker(
    case_dir: Path,
    image: str,
    timeout_s: float,
) -> dict[str, Any]:
    """
    Match the benchmark README's network-isolated Docker grading approach.
    Requires Docker on the host.
    """
    mount = str(case_dir.resolve())
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=512m",
        "-v", f"{mount}:/work:rw",
        "-w", "/work",
        image,
        "python3", "evaluation/evaluate.py",
    ]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        elapsed = time.perf_counter() - started
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": elapsed,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": cmd,
            "returncode": None,
            "passed": False,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_s": elapsed,
            "timed_out": True,
        }


# ---------------------------------------------------------------------------
# Evaluation orchestration
# ---------------------------------------------------------------------------

def load_completed_ids(results_jsonl: Path) -> set[str]:
    completed: set[str] = set()
    if not results_jsonl.is_file():
        return completed
    for line in results_jsonl.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = obj.get("case_id")
        if isinstance(case_id, str):
            completed.add(case_id)
    return completed


def prepare_workspace(
    source: Path,
    destination: Path,
    overwrite: bool,
) -> None:
    if destination.exists():
        if not overwrite:
            raise FileExistsError(destination)
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)


def format_exception(exc: BaseException) -> str:
    return "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )


def evaluate_case(
    info: CaseInfo,
    *,
    run_root: Path,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    api_timeout: float,
    api_retries: int,
    retry_backoff: float,
    parse_retries: int,
    seed: int | None,
    extra_body: dict[str, Any],
    grader_mode: str,
    grader_timeout: float,
    grader_python: str,
    docker_image: str,
    max_file_bytes: int,
    max_prompt_chars: int,
    keep_api_response: bool,
) -> dict[str, Any]:
    case_start = time.perf_counter()
    workspace = run_root / "cases" / info.case_id
    prepare_workspace(info.source_dir, workspace, overwrite=True)

    result: dict[str, Any] = {
        "case_id": info.case_id,
        "domain": info.domain,
        "source_dir": str(info.source_dir),
        "workspace": str(workspace),
        "model": model,
        "allowed_paths": info.allowed_paths,
        "passed": False,
        "status": "started",
    }

    if not info.allowed_paths:
        result.update({
            "status": "submission_path_inference_failed",
            "error": (
                "Could not infer an allowed submission path. "
                "Use --allowed-path for a single-case run or inspect README."
            ),
            "elapsed_s": time.perf_counter() - case_start,
        })
        return result

    try:
        prompt = build_prompt(
            workspace,
            info,
            max_file_bytes=max_file_bytes,
            max_prompt_chars=max_prompt_chars,
        )
        result["prompt_sha256"] = sha256_text(prompt)
        result["prompt_chars"] = len(prompt)

        raw_response_text: str | None = None
        api_result: APIResult | None = None
        bundle: dict[str, str] | None = None
        last_error: str | None = None

        # max_tokens is shrunk (and remembered) across attempts/retries when
        # the server reports prompt_tokens + max_tokens exceeds the model's
        # context window, so we don't burn every retry on the same overflow.
        current_max_tokens = max_tokens
        context_shrink_count = 0
        max_context_shrinks = 3

        # One initial generation plus optional parse/format retries.
        for parse_attempt in range(parse_retries + 1):
            if parse_attempt == 0:
                current_system = SYSTEM_PROMPT
                current_prompt = prompt
            else:
                current_system = SYSTEM_PROMPT
                current_prompt = (
                    prompt
                    + "\n\n"
                    + "Your previous response could not be materialized because:\n"
                    + (last_error or "invalid output")
                    + "\nReturn the complete corrected JSON file bundle only."
                )

            # Network/server retries for each generation attempt.
            api_attempt = 0
            while True:
                try:
                    api_result = chat_completion(
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        system_prompt=current_system,
                        user_prompt=current_prompt,
                        temperature=temperature,
                        max_tokens=current_max_tokens,
                        timeout_s=api_timeout,
                        seed=seed,
                        extra_body=extra_body,
                    )
                    break
                except ContextLengthExceededError as exc:
                    shrunk = compute_shrunk_max_tokens(
                        current_max_tokens,
                        exc.context_length,
                        exc.input_tokens,
                    )
                    if shrunk is None or context_shrink_count >= max_context_shrinks:
                        raise
                    context_shrink_count += 1
                    eprint(
                        f"    Prompt exceeds model context window "
                        f"(context={exc.context_length}, "
                        f"prompt~={exc.input_tokens} tokens); "
                        f"reducing max_tokens {current_max_tokens} -> "
                        f"{shrunk} and retrying "
                        f"({context_shrink_count}/{max_context_shrinks})"
                    )
                    current_max_tokens = shrunk
                    # Does not consume an api_attempt/retry-backoff slot.
                    continue
                except Exception:
                    if api_attempt >= api_retries:
                        raise
                    sleep_s = retry_backoff * (2 ** api_attempt)
                    eprint(
                        f"    API attempt {api_attempt + 1} failed; "
                        f"retrying after {sleep_s:.1f}s"
                    )
                    time.sleep(sleep_s)
                    api_attempt += 1
            assert api_result is not None

            raw_response_text = api_result.text
            try:
                bundle = parse_file_bundle(
                    raw_response_text,
                    info.allowed_paths,
                )
                break
            except Exception as exc:
                last_error = str(exc)
                if parse_attempt >= parse_retries:
                    raise RuntimeError(
                        f"could not parse/materialize model output after "
                        f"{parse_retries + 1} generation attempt(s): {last_error}"
                    ) from exc
                eprint(
                    f"    Output format attempt {parse_attempt + 1} invalid: "
                    f"{last_error}"
                )

        assert api_result is not None
        assert raw_response_text is not None
        assert bundle is not None

        result["generation"] = {
            "latency_s": api_result.latency_s,
            "prompt_tokens": api_result.prompt_tokens,
            "completion_tokens": api_result.completion_tokens,
            "total_tokens": api_result.total_tokens,
            "response_chars": len(raw_response_text),
            "response_sha256": sha256_text(raw_response_text),
            "max_tokens_requested": current_max_tokens,
            "context_shrink_count": context_shrink_count,
        }

        response_path = workspace / "_model_response.txt"
        response_path.write_text(raw_response_text, encoding="utf-8")
        result["model_response_path"] = str(response_path)

        if keep_api_response:
            api_path = workspace / "_api_response.json"
            atomic_write_json(api_path, api_result.raw)
            result["api_response_path"] = str(api_path)

        materialize_bundle(workspace, bundle)
        result["files_written"] = sorted(bundle)

        if grader_mode == "docker":
            grader = run_grader_docker(
                workspace,
                image=docker_image,
                timeout_s=grader_timeout,
            )
        else:
            grader = run_grader_host(
                workspace,
                python_executable=grader_python,
                timeout_s=grader_timeout,
            )

        result["grader"] = grader
        result["passed"] = bool(grader["passed"])
        result["status"] = "passed" if result["passed"] else "failed"

    except Exception as exc:
        result["status"] = "runner_error"
        result["error"] = str(exc)
        result["traceback"] = format_exception(exc)

    result["elapsed_s"] = time.perf_counter() - case_start
    return result


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(bool(r.get("passed")) for r in results)
    statuses = Counter(str(r.get("status", "unknown")) for r in results)

    per_domain: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        grouped[str(r.get("domain") or "unknown")].append(r)

    for domain, rows in sorted(grouped.items()):
        d_passed = sum(bool(r.get("passed")) for r in rows)
        per_domain[domain] = {
            "passed": d_passed,
            "total": len(rows),
            "pass_rate": (d_passed / len(rows)) if rows else None,
        }

    prompt_tokens = 0
    completion_tokens = 0
    token_rows = 0
    generation_time = 0.0

    for r in results:
        gen = r.get("generation")
        if not isinstance(gen, dict):
            continue
        pt = gen.get("prompt_tokens")
        ct = gen.get("completion_tokens")
        if isinstance(pt, int):
            prompt_tokens += pt
        if isinstance(ct, int):
            completion_tokens += ct
        if isinstance(pt, int) or isinstance(ct, int):
            token_rows += 1
        latency = gen.get("latency_s")
        if isinstance(latency, (int, float)):
            generation_time += float(latency)

    return {
        "passed": passed,
        "total": total,
        "pass_rate": (passed / total) if total else None,
        "statuses": dict(statuses),
        "per_domain": per_domain,
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "rows_with_usage": token_rows,
        },
        "generation_time_s": generation_time,
    }


def write_summary_csv(
    path: Path,
    results: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id",
        "domain",
        "status",
        "passed",
        "model",
        "elapsed_s",
        "generation_latency_s",
        "prompt_tokens",
        "completion_tokens",
        "grader_returncode",
        "grader_elapsed_s",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            gen = r.get("generation") if isinstance(r.get("generation"), dict) else {}
            grader = r.get("grader") if isinstance(r.get("grader"), dict) else {}
            writer.writerow({
                "case_id": r.get("case_id"),
                "domain": r.get("domain"),
                "status": r.get("status"),
                "passed": r.get("passed"),
                "model": r.get("model"),
                "elapsed_s": r.get("elapsed_s"),
                "generation_latency_s": gen.get("latency_s"),
                "prompt_tokens": gen.get("prompt_tokens"),
                "completion_tokens": gen.get("completion_tokens"),
                "grader_returncode": grader.get("returncode"),
                "grader_elapsed_s": grader.get("elapsed_s"),
            })


def print_summary(summary: dict[str, Any]) -> None:
    print()
    print("=" * 72)
    print("LLM4HWSec benchmark summary")
    print("=" * 72)
    total = summary["total"]
    passed = summary["passed"]
    rate = summary["pass_rate"]
    rate_text = f"{100.0 * rate:.2f}%" if rate is not None else "n/a"
    print(f"Overall: {passed}/{total} passed ({rate_text})")
    print()

    print("Per-domain:")
    for domain, row in summary["per_domain"].items():
        drate = row["pass_rate"]
        drate_text = f"{100.0 * drate:.2f}%" if drate is not None else "n/a"
        print(
            f"  {domain:34s} "
            f"{row['passed']:4d}/{row['total']:<4d} {drate_text:>8s}"
        )

    print()
    print("Statuses:")
    for status, count in sorted(summary["statuses"].items()):
        print(f"  {status:34s} {count}")

    usage = summary["token_usage"]
    if usage["rows_with_usage"]:
        print()
        print(
            "Tokens: "
            f"prompt={usage['prompt_tokens']:,} "
            f"completion={usage['completion_tokens']:,}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_extra_body(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"--extra-body must be JSON: {exc}"
        ) from exc
    if not isinstance(obj, dict):
        raise argparse.ArgumentTypeError("--extra-body must be a JSON object")
    return obj


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run an OpenAI-compatible model on LLM4HWSec-Benchmark.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--cases",
        type=Path,
        required=True,
        help="Root containing benchmark testcase directories.",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for copied workspaces and results.",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8001/v1"),
        help="OpenAI-compatible API base URL.",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", "EMPTY"),
        help="API key. vLLM commonly accepts EMPTY.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Served model name. If omitted, use first GET /v1/models result.",
    )

    selection = p.add_argument_group("case selection")
    selection.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run only this case ID. Repeat for multiple cases.",
    )
    selection.add_argument(
        "--domain",
        action="append",
        choices=sorted(DOMAIN_CONTRACTS),
        default=[],
        help="Run only this domain. Repeat for multiple domains.",
    )
    selection.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of selected cases after filtering/shuffling.",
    )
    selection.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle cases before applying --limit.",
    )
    selection.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Selection/model seed.",
    )
    selection.add_argument(
        "--allowed-path",
        action="append",
        default=[],
        help=(
            "Override inferred allowed output path. Intended for --case with "
            "unusual/custom cases; repeat for multiple paths."
        ),
    )
    selection.add_argument(
        "--usable-only",
        action="store_true",
        help=(
            "Only run cases graded in --usable-grades (default: A,B) per "
            "--case-grades (case_grades.json). Filters out cases flagged as "
            "lower-quality/spec-integrity-compromised by benchmark grading."
        ),
    )
    selection.add_argument(
        "--usable-grades",
        default="A,B",
        help="Comma-separated letter grades kept by --usable-only.",
    )
    selection.add_argument(
        "--case-grades",
        type=Path,
        default=None,
        help=(
            "Path to case_grades.json used by --usable-only. Defaults to "
            "case_grades.json next to this script."
        ),
    )

    generation = p.add_argument_group("generation")
    generation.add_argument("--temperature", type=float, default=0.0)
    generation.add_argument("--max-tokens", type=int, default=8192)
    generation.add_argument("--api-timeout", type=float, default=600.0)
    generation.add_argument("--api-retries", type=int, default=2)
    generation.add_argument("--retry-backoff", type=float, default=2.0)
    generation.add_argument(
        "--parse-retries",
        type=int,
        default=1,
        help="Regenerate when model output is malformed or writes forbidden paths.",
    )
    generation.add_argument(
        "--extra-body",
        default=None,
        help='Extra JSON merged into /chat/completions body, e.g. \'{"top_p":0.95}\'.',
    )
    generation.add_argument(
        "--max-file-bytes",
        type=int,
        default=2_000_000,
        help="Maximum bytes read from each participant-facing file.",
    )
    generation.add_argument(
        "--max-prompt-chars",
        type=int,
        default=8_000_000,
        help="Safety cap on assembled prompt size.",
    )
    generation.add_argument(
        "--keep-api-response",
        action="store_true",
        help="Save complete raw API JSON in each case workspace.",
    )

    grading = p.add_argument_group("grading")
    grading.add_argument(
        "--grader-mode",
        choices=["host", "docker"],
        default="host",
        help=(
            "host: execute evaluator directly; docker: use benchmark's "
            "network-isolated runner image."
        ),
    )
    grading.add_argument(
        "--grader-timeout",
        type=float,
        default=300.0,
    )
    grading.add_argument(
        "--grader-python",
        default=sys.executable,
        help="Python executable for host-mode evaluation.",
    )
    grading.add_argument(
        "--docker-image",
        default="agentic-bench-gen-runner:latest",
    )

    control = p.add_argument_group("run control")
    control.add_argument(
        "--resume",
        action="store_true",
        help="Skip case IDs already present in results.jsonl.",
    )
    control.add_argument(
        "--inspect-only",
        action="store_true",
        help="Discover cases/submission paths and exit without contacting model.",
    )

    return p


def main() -> int:
    args = build_parser().parse_args()

    cases_root: Path = args.cases.resolve()
    output: Path = args.output.resolve()

    if not cases_root.is_dir():
        eprint(f"error: --cases is not a directory: {cases_root}")
        return 2

    discovered = discover_cases(cases_root)
    if not discovered:
        eprint(
            f"error: no cases containing README.md + evaluation/evaluate.py "
            f"found under {cases_root}"
        )
        return 2

    infos = [inspect_case(path) for path in discovered]

    if args.case:
        wanted = set(args.case)
        infos = [x for x in infos if x.case_id in wanted]
        missing = wanted - {x.case_id for x in infos}
        if missing:
            eprint("warning: requested case ID(s) not found:", ", ".join(sorted(missing)))

    if args.domain:
        wanted_domains = set(args.domain)
        infos = [x for x in infos if x.domain in wanted_domains]

    if args.allowed_path:
        if len(infos) != 1:
            eprint("error: --allowed-path override requires exactly one selected case")
            return 2
        infos[0].allowed_paths = [
            normalized_relpath(p) for p in args.allowed_path
        ]

    if args.usable_only:
        grades_path = args.case_grades or (
            Path(__file__).resolve().parent / "case_grades.json"
        )
        if not grades_path.is_file():
            eprint(
                f"error: --usable-only requires a case grades file; "
                f"not found: {grades_path}"
            )
            return 2
        try:
            grades = load_case_grades(grades_path)
        except Exception as exc:
            eprint(f"error: failed to load --case-grades {grades_path}: {exc}")
            return 2

        wanted_grades = {
            g.strip().upper() for g in args.usable_grades.split(",") if g.strip()
        }
        before = len(infos)
        ungraded = sum(1 for x in infos if x.case_id not in grades)
        infos = [
            x for x in infos
            if grades.get(x.case_id, "").upper() in wanted_grades
        ]
        skipped = before - len(infos)
        if skipped:
            print(
                f"Usable-only: skipping {skipped} case(s) not graded "
                f"{sorted(wanted_grades)} in {grades_path.name} "
                f"({ungraded} had no grade entry)."
            )

    if args.shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(infos)

    if args.limit is not None:
        if args.limit < 0:
            eprint("error: --limit must be >= 0")
            return 2
        infos = infos[: args.limit]

    if not infos:
        eprint("error: no cases selected")
        return 2

    print(f"Discovered {len(discovered)} case(s); selected {len(infos)}.")
    unknown_domains = sum(x.domain is None for x in infos)
    unresolved_paths = sum(not x.allowed_paths for x in infos)
    print(
        f"Domain inference: {len(infos) - unknown_domains}/{len(infos)} resolved; "
        f"submission paths: {len(infos) - unresolved_paths}/{len(infos)} resolved."
    )

    if args.inspect_only:
        for i, info in enumerate(infos, 1):
            print(
                f"[{i}/{len(infos)}] {info.case_id} "
                f"domain={info.domain or '?'} "
                f"outputs={','.join(info.allowed_paths) or '?'}"
            )
        return 0

    output.mkdir(parents=True, exist_ok=True)
    results_jsonl = output / "results.jsonl"

    completed = load_completed_ids(results_jsonl) if args.resume else set()
    if completed:
        before = len(infos)
        infos = [x for x in infos if x.case_id not in completed]
        print(f"Resume: skipping {before - len(infos)} completed case(s).")

    if not infos:
        print("Nothing to run.")
        return 0

    model = args.model
    if not model:
        print(f"Resolving served model from {args.base_url}/models ...")
        model = resolve_model(
            args.base_url,
            args.api_key,
            args.api_timeout,
        )
    print(f"Model: {model}")
    print(f"Endpoint: {args.base_url}")
    print(f"Grader mode: {args.grader_mode}")
    print(f"Results: {results_jsonl}")
    print()

    try:
        extra_body = parse_extra_body(args.extra_body)
    except argparse.ArgumentTypeError as exc:
        eprint(f"error: {exc}")
        return 2

    current_results: list[dict[str, Any]] = []

    for idx, info in enumerate(infos, 1):
        print(
            f"[{idx}/{len(infos)}] {info.case_id} "
            f"domain={info.domain or '?'}"
        )
        print(f"    outputs: {', '.join(info.allowed_paths) or '(unresolved)'}")

        result = evaluate_case(
            info,
            run_root=output,
            base_url=args.base_url,
            api_key=args.api_key,
            model=model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            api_timeout=args.api_timeout,
            api_retries=args.api_retries,
            retry_backoff=args.retry_backoff,
            parse_retries=args.parse_retries,
            seed=args.seed,
            extra_body=extra_body,
            grader_mode=args.grader_mode,
            grader_timeout=args.grader_timeout,
            grader_python=args.grader_python,
            docker_image=args.docker_image,
            max_file_bytes=args.max_file_bytes,
            max_prompt_chars=args.max_prompt_chars,
            keep_api_response=args.keep_api_response,
        )

        append_jsonl(results_jsonl, result)
        current_results.append(result)

        grader = result.get("grader")
        if isinstance(grader, dict):
            rc = grader.get("returncode")
            print(
                f"    {result['status'].upper()} "
                f"grader_rc={rc} "
                f"elapsed={result.get('elapsed_s', 0):.2f}s"
            )
            stdout = str(grader.get("stdout") or "").strip()
            stderr = str(grader.get("stderr") or "").strip()
            if stdout:
                print("    grader stdout:")
                for line in stdout.splitlines()[-20:]:
                    print(f"      {line}")
            if stderr:
                print("    grader stderr:")
                for line in stderr.splitlines()[-20:]:
                    print(f"      {line}")
        else:
            print(
                f"    {result['status'].upper()}: "
                f"{result.get('error', '')}"
            )

    # Aggregate all rows currently in JSONL, including previous rows when
    # --resume is used. Keep the latest result for a duplicate case ID.
    by_case: dict[str, dict[str, Any]] = {}
    for line in results_jsonl.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = row.get("case_id")
        if isinstance(case_id, str):
            by_case[case_id] = row

    all_results = list(by_case.values())
    summary = aggregate_results(all_results)
    atomic_write_json(output / "summary.json", summary)
    write_summary_csv(output / "summary.csv", all_results)
    print_summary(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())