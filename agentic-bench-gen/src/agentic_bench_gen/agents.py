from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .llm import OpenRouterLLM, _reasoning_active
from .schemas import load_schema, validate_or_raise
from .utils import read_text, render_template
from .logio import console
from .workspace import is_safe_relative_path

def _path_allowed(path: str, allowed: list[str] | None) -> bool:
    """True when `path` is an exact allowed name or lives under an allowed
    directory prefix. None disables ownership restrictions, but never path
    containment checks."""
    if not is_safe_relative_path(path):
        return False
    if not allowed:
        return True
    normalized = Path(path).as_posix()
    for entry in allowed:
        if entry.endswith("/"):
            if normalized.startswith(entry) and normalized != entry.rstrip("/"):
                return True
        elif normalized == entry:
            return True
    return False


@dataclass
class AgentConfig:
    name: str
    model: str
    prompt_path: Path
    schema_path: Path
    temperature: float
    max_tokens: int
    # OpenRouter unified reasoning config for this agent (e.g. {"max_tokens":
    # 8000} for bounded extended thinking). None inherits the pipeline-level
    # default. The thinking budget counts INSIDE max_tokens, so agents with
    # reasoning need correspondingly larger max_tokens.
    reasoning: dict[str, Any] | None = None
    # File-bundle agents may only emit files under these path prefixes / exact
    # names (e.g. ["inputs/", "README.md"]). Enforced at the plan stage so a
    # scope-creeping agent (e.g. the ArtifactBuilder planning its own
    # evaluate.py) cannot spend tokens on, or write, files another agent owns.
    # None disables the restriction.
    allowed_paths: list[str] | None = None
    # Output budget for a FileBundleAgent's phase-1 PLAN call (manifest only,
    # never file bodies). The agent's thinking budget is added on top, and the
    # result is still capped by max_tokens. None uses _PLAN_MAX_TOKENS. Set
    # `plan_max_tokens` in agents.yaml to change it per agent.
    plan_max_tokens: int | None = None


def _with_schema(instruction: str, schema: dict[str, Any]) -> str:
    """Append the JSON Schema to a JSON-mode instruction. The prompts themselves
    only say "Return JSON only", so without this the schema travels solely in
    response_format — and any provider that ignores or rejects that field (seen
    as deterministic empty completions) leaves the model with no idea of the
    required shape."""
    return (
        instruction
        + "\n\nYour response must be a single JSON object that validates against this "
        "JSON Schema (no properties beyond those it allows):\n"
        + json.dumps(schema, sort_keys=True)
    )


class JsonAgent:
    # How many times a schema-invalid response is sent back to the model with
    # the exact validation error before giving up. A blind identical retry
    # repeats the mistake; the error message usually fixes it in one shot.
    max_schema_repairs = 2

    def __init__(self, llm: OpenRouterLLM, config: AgentConfig):
        self.llm = llm
        self.config = config
        self.prompt_template = read_text(config.prompt_path)
        self.schema = load_schema(config.schema_path)

    def _render(self, variables: dict[str, Any]) -> str:
        rendered = {
            key: value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
            for key, value in variables.items()
        }
        # render_template substitutes "" for unfilled placeholders; do NOT run a
        # blanket {{...}} strip over the rendered prompt afterwards — injected
        # artifact code legitimately contains double braces (e.g. Verilog
        # replication `{{8{sign}}, data}`) and stripping them corrupts what the
        # downstream agent sees.
        return render_template(self.prompt_template, **rendered).strip()

    def _complete_json_validated(
        self,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
        escalation_cap: int | None = None,
    ) -> dict[str, Any]:
        """complete_json plus local schema enforcement with a repair loop: a
        schema-invalid response is returned to the model together with the
        validation error so it can restructure, instead of failing the agent
        (or retrying blind) on the first malformed shape."""
        for repair in range(self.max_schema_repairs + 1):
            result = self.llm.complete_json(
                model=self.config.model,
                messages=messages,
                schema_name=schema_name,
                schema=schema,
                temperature=self.config.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.config.max_tokens,
                reasoning=self.config.reasoning,
                escalation_cap=escalation_cap,
            )
            try:
                validate_or_raise(result, schema)
            except ValueError as exc:
                if repair >= self.max_schema_repairs:
                    raise
                console.print(
                    f"  [yellow]{schema_name}: response violates the schema ({exc}); "
                    f"sending the error back for repair "
                    f"({repair + 1}/{self.max_schema_repairs}).[/yellow]"
                )
                messages = messages + [
                    {"role": "assistant", "content": json.dumps(result, indent=2, sort_keys=True)},
                    {"role": "user", "content": (
                        f"That response does not validate against the schema: {exc}\n"
                        "Return the corrected JSON object ONLY — keep the same substantive "
                        "content, restructured to match the schema exactly."
                    )},
                ]
                continue
            return result
        raise AssertionError("unreachable")  # pragma: no cover

    def run(self, variables: dict[str, Any]) -> dict[str, Any]:
        prompt = self._render(variables)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": _with_schema(
                "Return only JSON matching the schema. Do not include markdown fences.",
                self.schema,
            )},
        ]
        return self._complete_json_validated(messages, f"{self.config.name}_output", self.schema)


def _plan_schema(bundle_schema: dict[str, Any]) -> dict[str, Any]:
    """Derive the phase-1 plan schema from a file-bundle schema: same contract
    minus the `files` array (contents are emitted per-file in phase 2)."""
    plan = deepcopy(bundle_schema)
    plan.get("properties", {}).pop("files", None)
    if isinstance(plan.get("required"), list):
        plan["required"] = [key for key in plan["required"] if key != "files"]
    return plan


_PLAN_INSTRUCTIONS = (
    "PLANNING MODE: Return ONLY the bundle plan as JSON matching the schema — the manifest "
    "(and requirement_map if the schema has one) WITHOUT any `files` array and WITHOUT file "
    "contents. Every file you intend to ship MUST have a manifest entry, and each entry's "
    "`purpose` must pin what phase 2 cannot re-derive: exact interfaces/signatures, key "
    "constants and values, required structures, and how the file relates to the other files. "
    "KEEP THE PLAN COMPACT: each `purpose` must stay under ~150 words — name each check and "
    "its verdict criterion in one line, do NOT spell out per-check pseudocode, regex patterns, "
    "test-vector tables, or output transcripts (design those in phase 2, where each file gets "
    "its own full budget). NEVER write file bodies or code in the plan — not as a "
    "`files` property (the schema forbids it) and not inside `purpose` strings; each file's "
    "full content is requested separately, one file at a time, right after this plan. "
    "Do not include markdown fences. HARD SIZE LIMIT: no planned file may require more than "
    "300 lines. Use compact behavioral or modest structural hardware examples; never plan a "
    "fully flattened design with thousands of repeated wires or gates."
)

# The plan is a manifest, not the bundle: it never legitimately needs the
# agent's full per-file output budget (48K+ for the Tester). Capping the plan
# request — and the truncation-escalation ceiling — stops a model that starts
# writing file bodies into the plan from burning the whole budget on a
# response the schema would reject anyway. Reasoning tokens bill inside
# max_tokens, so an agent's thinking budget is added on top.
_PLAN_MAX_TOKENS = 12000


def _file_request(plan: dict[str, Any], done: list[dict[str, str]], entry: dict[str, Any]) -> str:
    parts = [
        "FILE EMISSION MODE — you already produced this bundle plan:",
        json.dumps(plan, indent=2, sort_keys=True),
    ]
    if done:
        rendered = "\n\n".join(f"--- {f['path']} ---\n{f['content']}" for f in done)
        parts.append("Files already written (final content — stay consistent with them):\n" + rendered)
    parts.append(
        f"Now write the COMPLETE content of exactly one file: {entry.get('path')}\n"
        f"Its purpose: {entry.get('purpose', '')}\n"
        "Output ONLY the raw file content — no JSON wrapper, no markdown fences, no commentary."
    )
    return "\n\n".join(parts)


class FileBundleAgent(JsonAgent):
    """Two-phase file-bundle generation.

    Phase 1 asks for the bundle *plan* (manifest and any non-file fields such as
    requirement_map) as JSON. Phase 2 emits each planned file with a separate
    plain-text completion that sees the plan and all previously written files.

    No single response ever has to fit a whole bundle, so per-agent output caps
    stop aborting cases with large artifacts (netlists, multi-file harnesses),
    a truncation costs one file's retry rather than the whole bundle, and file
    content is transmitted raw instead of JSON-escaped."""

    def __init__(self, llm: OpenRouterLLM, config: AgentConfig):
        super().__init__(llm, config)
        self.plan_schema = _plan_schema(self.schema)

    def _emit_file(
        self,
        prompt: str,
        plan: dict[str, Any],
        context: list[dict[str, str]],
        entry: dict[str, Any],
    ) -> str:
        path = str(entry.get("path", ""))
        request = _file_request(plan, context, entry)
        kwargs = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": request},
            ],
            "label": f"{self.config.name}:{path}",
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "reasoning": self.config.reasoning,
            # A file that cannot fit the configured per-file budget should be
            # redesigned, not blindly retried at the global 64K ceiling.
            "escalation_cap": self.config.max_tokens,
        }
        try:
            return self.llm.complete_text(**kwargs)
        except RuntimeError as exc:
            if "output is too large" not in str(exc):
                raise
            compact_budget = min(self.config.max_tokens, 16000)
            console.print(
                f"  [yellow]{self.config.name}:{path} exceeded its file budget; "
                "retrying once as a compact replacement under 300 lines.[/yellow]"
            )
            kwargs.update({
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": request + (
                        "\n\nCOMPACT REPLACEMENT REQUIRED: the previous response was too large. "
                        "Redesign this file to stay under 300 lines and 12,000 output tokens. "
                        "Preserve the required interface and behavior, but use loops, arrays, "
                        "generate constructs, helper functions, or behavioral RTL instead of "
                        "enumerating repeated wires/gates."
                    )},
                ],
                "max_tokens": compact_budget,
                "escalation_cap": compact_budget,
            })
            return self.llm.complete_text(**kwargs)

    def run(self, variables: dict[str, Any]) -> dict[str, Any]:
        prompt = self._render(variables)
        # Effective reasoning for this agent's calls: its own config, else the
        # pipeline-level default the LLM client will fall back to. Judging only
        # the agent config misses globally-enabled reasoning — the plan then
        # starts at the plain 1x budget and truncates once thinking bills
        # against it (seen on artifact_builder repair-round plans).
        reasoning_cfg = (self.config.reasoning if self.config.reasoning is not None
                         else getattr(self.llm, "reasoning", None)) or {}
        reasoning_active = _reasoning_active(reasoning_cfg)
        # Legacy budget-style configs ({"max_tokens": N}) still add their nominal
        # budget on top of the base; effort-style configs have no number to add.
        reasoning_budget = int(reasoning_cfg.get("max_tokens", 0) or 0) if reasoning_active else 0
        plan_base = self.config.plan_max_tokens if self.config.plan_max_tokens else _PLAN_MAX_TOKENS
        plan_budget = min(self.config.max_tokens, plan_base + reasoning_budget)
        if reasoning_active:
            # Thinking is adaptive and bills inside completion_tokens (only a
            # summary is returned/reported); nominal thinking budgets are
            # unenforced on sonnet-5. Measured on real runs: 1x plan budgets
            # truncated ~half the plan calls (a full billed response wasted
            # each time) while 2x always succeeded. Start at 2x instead of
            # burning a doomed call.
            plan_budget = min(self.config.max_tokens, plan_budget * 2)
        plan = self._complete_json_validated(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": _with_schema(_PLAN_INSTRUCTIONS, self.plan_schema)},
            ],
            schema_name=f"{self.config.name}_plan",
            schema=self.plan_schema,
            max_tokens=plan_budget,
            escalation_cap=min(self.config.max_tokens, plan_budget * 2),
        )
        manifest = plan.get("manifest") or []
        if not manifest:
            raise ValueError(f"{self.config.name}: bundle plan has an empty manifest.")
        # Drop out-of-scope files before spending a completion on each, so an
        # agent that plans files another agent owns (e.g. the ArtifactBuilder
        # planning evaluation/evaluate.py) neither bills for them nor pollutes
        # the workspace. The manifest lives in the returned bundle too, so prune
        # it there as well to keep plan and files consistent.
        allowed = self.config.allowed_paths
        kept_manifest: list[dict[str, Any]] = []
        for entry in manifest:
            path = str(entry.get("path", "")).strip()
            if path and not _path_allowed(path, allowed):
                console.print(
                    f"  [yellow]{self.config.name}: dropping out-of-scope planned file "
                    f"{path!r} (allowed: {allowed}).[/yellow]"
                )
                continue
            kept_manifest.append(entry)
        if not kept_manifest:
            raise ValueError(
                f"{self.config.name}: every planned file was out of scope for allowed_paths "
                f"{allowed}; nothing to emit."
            )
        plan["manifest"] = kept_manifest
        files: list[dict[str, str]] = []
        for entry in kept_manifest:
            path = str(entry.get("path", "")).strip()
            if not path:
                raise ValueError(f"{self.config.name}: manifest entry without a path.")
            content = self._emit_file(prompt, plan, files, entry)
            files.append({"path": path, "content": content})
        bundle = {**plan, "files": files}
        validate_or_raise(bundle, self.schema)
        return bundle

    def repair_files(
        self,
        variables: dict[str, Any],
        previous_bundle: dict[str, Any],
        paths: list[str],
    ) -> dict[str, Any]:
        """Regenerate selected files without paying for a new plan or unrelated files."""
        wanted = set(paths)
        manifest = previous_bundle.get("manifest") or []
        by_path = {str(entry.get("path", "")): entry for entry in manifest}
        entries = [by_path[path] for path in paths if path in wanted and path in by_path]
        if not entries:
            raise ValueError(f"{self.config.name}: no requested repair paths exist in the manifest.")

        prompt = self._render(variables)
        plan = {key: deepcopy(value) for key, value in previous_bundle.items() if key != "files"}
        original_files = previous_bundle.get("files") or []
        repaired: dict[str, str] = {}
        context = [deepcopy(item) for item in original_files if str(item.get("path", "")) not in wanted]
        for entry in entries:
            path = str(entry["path"])
            content = self._emit_file(prompt, plan, context, entry)
            repaired[path] = content
            context.append({"path": path, "content": content})

        files = [
            {**item, "content": repaired.get(str(item.get("path", "")), item.get("content", ""))}
            for item in original_files
        ]
        bundle = {**plan, "files": files}
        validate_or_raise(bundle, self.schema)
        return bundle
