from __future__ import annotations
from .logio import console

import json
import os
import re
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Callable

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

class EmptyResponseError(RuntimeError):
    """Raised when the provider returns an assistant message with no text content
    (finish_reason != 'length'). A frequent cause is a reasoning model emitting
    only a thinking block and stopping, so the retry logic drops the reasoning
    request before re-hitting the same wall."""


class TruncatedResponseError(RuntimeError):
    """Raised internally when the provider stops with finish_reason='length' or
    the returned JSON is visibly cut off. Carries the partial content and the
    observed completion token count so the retry logic can tell apart "needs a
    bigger budget" from "looping model" / "provider-capped completion" — the
    latter two must fail fast instead of escalating."""

    def __init__(self, content: str = "", completion_tokens: int | None = None):
        super().__init__("truncated response")
        self.content = content or ""
        self.completion_tokens = completion_tokens


class ContentFilteredError(RuntimeError):
    """Raised when the provider stops a response with finish_reason=
    'content_filter'. This benchmark's prompts legitimately discuss hardware
    vulnerabilities, and some endpoints serving the same model (Vertex /
    Bedrock / Azure) apply an extra safety layer that Anthropic-direct does
    not — the response is cut mid-stream or blanked. Retryable: OpenRouter
    may route the retry to a different endpoint."""

    def __init__(self, completion_tokens: int | None = None):
        super().__init__("response stopped by provider content filter")
        self.completion_tokens = completion_tokens


def _looks_degenerate(text: str) -> bool:
    """Heuristic for repetition loops in a truncated response tail. A looping
    model converts any max_tokens increase into pure waste, so escalation must
    never happen for these."""
    if not text:
        return False
    tail = text[-4000:]
    # A single character repeated very long (runs of newlines, spaces, ...).
    if re.search(r"(.)\1{499}", tail, re.DOTALL):
        return True
    lines = [ln for ln in tail.splitlines() if ln.strip()]
    if len(lines) >= 40 and len(set(lines)) / len(lines) < 0.15:
        return True
    return False


def _reasoning_active(cfg: dict[str, Any] | None) -> bool:
    """True only when the reasoning config actually turns reasoning ON.
    `{"enabled": false}` is an explicit OFF — but it is a truthy dict, so a
    plain bool check misclassifies it and the empty-response recovery then
    strips the field entirely, which *re-enables* provider-default reasoning
    on reasoning-default models."""
    return bool(cfg) and cfg.get("enabled", True) is not False


def _tool_call_arguments(message: Any) -> str:
    """Payload of the first non-empty tool call, else "". Providers that
    implement schema-constrained output as a forced tool call return the JSON
    in tool_calls[].function.arguments with an EMPTY content — reading only
    `content` misclassifies a complete, billed response as empty."""
    for call in getattr(message, "tool_calls", None) or []:
        args = getattr(getattr(call, "function", None), "arguments", None)
        if args and str(args).strip():
            return str(args)
    return ""


def _extract_json_block(text: str) -> str | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


_AFFORDABLE_RE = re.compile(r"can only afford\s+(\d+)")


def _parse_affordable_tokens(message: str) -> int | None:
    """Extract the affordable token count from an OpenRouter 402 credit error,
    e.g. 'You requested up to 48000 tokens, but can only afford 43890.'"""
    match = _AFFORDABLE_RE.search(message)
    return int(match.group(1)) if match else None


def _account_limit_message(exc: Exception) -> str | None:
    """Return an actionable message if this is a terminal account/key error
    (auth, exhausted credits, or key spending cap), else None.

    These are not transient and not fixable by shrinking max_tokens — retrying
    only wastes time and re-hits the same wall, so callers should fail fast.
    """
    text = str(exc)
    code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if code is None:
        match = re.search(r"Error code:\s*(\d+)", text)
        code = int(match.group(1)) if match else None
    if code not in (401, 402, 403):
        return None
    return (
        f"OpenRouter rejected the request (HTTP {code}): {text.strip()[:300]} — this is an "
        "account/key limit (credentials, exhausted credits, or the key's spending cap), not a "
        "transient error. Add credits or raise the key's limit at "
        "https://openrouter.ai/settings/keys; retrying will not help."
    )


_CONTEXT_OVERFLOW_RE = re.compile(
    r"maximum context length|context length is|context_length_exceeded"
    r"|reduce the length of the messages|prompt is too long",
    re.IGNORECASE,
)


def _context_overflow_message(exc: Exception, requested_max_tokens: int) -> str | None:
    """Return an actionable message if the prompt (input) plus reserved output
    exceeds the model's context window, else None.

    max_tokens only caps *output*; this is an input-size problem. Retrying with
    the same prompt re-hits the same wall, so callers should fail fast.
    """
    if not _CONTEXT_OVERFLOW_RE.search(str(exc)):
        return None
    return (
        "OpenRouter rejected the request: the prompt (input tokens) plus the reserved output "
        f"(max_tokens={requested_max_tokens}) exceeds the model's context window — "
        f"{str(exc).strip()[:300]}. Note max_tokens caps *output* only; this is an *input* size "
        "problem. If output is the bulk, lower this agent's max_tokens; otherwise the prompt is "
        "too large — reduce what is fed to the agent (e.g. the artifact/expert/tester bundles)."
    )


_FENCE_RE = re.compile(r"^```[\w+.-]*\n(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Unwrap a whole-response markdown code fence if the model added one."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


def _close_unbalanced_json(text: str) -> str | None:
    """Append the closing braces/brackets a finish_reason='stop' response left
    off (models occasionally emit everything but the last `}`). Returns the
    completed text, or None when the tail is not merely missing closers (mid-
    string cut, mismatched nesting). Only ever called after normal parsing
    failed, and the result is still json.loads'd and schema-validated — a wrong
    guess cannot silently pass."""
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = in_string
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack or stack[-1] != ch:
                return None
            stack.pop()
    if in_string or not stack:
        return None
    return text + "".join(reversed(stack))


def _loads_json_lenient(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except JSONDecodeError:
        extracted = _extract_json_block(content)
        if extracted is None:
            completed = _close_unbalanced_json(content.strip())
            if completed is None:
                raise
            try:
                parsed = json.loads(completed)
            except JSONDecodeError:
                raise
        else:
            parsed = json.loads(extracted)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from provider.")
    return parsed


@dataclass
class OpenRouterSettings:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "http://localhost"
    title: str = "AgenticBenchGen"
    timeout_seconds: float = 120.0
    max_retries: int = 3
    # Hard ceiling for output tokens. On a truncated response we escalate
    # max_tokens up to this cap before giving up (Sonnet 4.x caps at 64K).
    max_output_tokens: int = 64000
    # OpenRouter unified reasoning control, sent as the request's `reasoning`
    # field. Hidden reasoning tokens are billed as *completion* tokens and count
    # against max_tokens, so reasoning-default models can silently burn an
    # agent's whole output budget before emitting any JSON. None sends nothing
    # (provider default).
    reasoning: dict[str, Any] | None = None
    # OpenRouter provider-routing preferences, sent as the request's `provider`
    # field (e.g. {"order": ["anthropic"], "allow_fallbacks": False}). Pinning
    # matters here: the same model is served by endpoints with different
    # safety layers, and the non-Anthropic ones content-filter this
    # benchmark's vulnerability-heavy prompts. None sends nothing.
    provider: dict[str, Any] | None = None


class OpenRouterLLM:
    def __init__(self, settings: OpenRouterSettings):
        if OpenAI is None:
            raise RuntimeError("Install the 'openai' package to use OpenRouter generation.")
        self.default_retries = settings.max_retries
        self.max_output_tokens = settings.max_output_tokens
        self.reasoning = settings.reasoning
        self.provider = settings.provider
        self.usage_totals: dict[str, int] = {
            "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "calls": 0,
        }
        # (model, label) pairs where the provider returned empty content until
        # response_format was dropped. Skipping the format for them afterwards
        # saves one guaranteed-dead call per request (the schema still travels
        # in the messages and is enforced locally).
        self._response_format_broken: set[tuple[str, str]] = set()
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            default_headers={
                "HTTP-Referer": settings.referer,
                "X-Title": settings.title,
                "X-OpenRouter-Title": settings.title,
            },
            timeout=settings.timeout_seconds,
            max_retries=0,
        )

    @classmethod
    def from_env(
        cls,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_output_tokens: int | None = None,
        reasoning: dict[str, Any] | None = None,
        provider: dict[str, Any] | None = None,
    ) -> "OpenRouterLLM":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY before running.")
        return cls(
            OpenRouterSettings(
                api_key=api_key,
                base_url=base_url,
                referer=os.environ.get("OPENROUTER_REFERER", "http://localhost"),
                title=os.environ.get("OPENROUTER_TITLE", "AgenticBenchGen"),
                timeout_seconds=timeout_seconds if timeout_seconds is not None else float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "120")),
                max_retries=max_retries if max_retries is not None else int(os.environ.get("OPENROUTER_MAX_RETRIES", "3")),
                max_output_tokens=max_output_tokens if max_output_tokens is not None else int(os.environ.get("OPENROUTER_MAX_OUTPUT_TOKENS", "64000")),
                reasoning=reasoning,
                provider=provider,
            )
        )

    def _record_usage(self, schema_name: str, usage: Any) -> None:
        """Accumulate and print per-call token usage so cost hotspots are
        visible in the console instead of only on the OpenRouter dashboard."""
        if usage is None:
            return
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "completion_tokens_details", None)
        rt = (getattr(details, "reasoning_tokens", 0) or 0) if details is not None else 0
        self.usage_totals["prompt_tokens"] += pt
        self.usage_totals["completion_tokens"] += ct
        self.usage_totals["reasoning_tokens"] += rt
        self.usage_totals["calls"] += 1
        # Escape the label bracket: rich would otherwise parse
        # "[tester_plan]" as a style tag and swallow it from the output.
        line = f"  [dim]tokens \\[{schema_name}]: in={pt} out={ct}"
        if rt:
            line += f" (reasoning={rt})"
        line += (
            f" | run totals: in={self.usage_totals['prompt_tokens']}"
            f" out={self.usage_totals['completion_tokens']}"
            f" calls={self.usage_totals['calls']}[/dim]"
        )
        console.print(line)
        if rt and ct and rt / ct > 0.5:
            console.print(
                "  [yellow]More than half of this call's output budget went to hidden "
                "reasoning tokens — tune `openrouter.reasoning` in pipeline.yaml.[/yellow]"
            )

    def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 16000,
        retries: int | None = None,
        reasoning: dict[str, Any] | None = None,
        escalation_cap: int | None = None,
    ) -> dict[str, Any]:
        # strict=False: several of our schemas intentionally carry optional
        # properties (e.g. task_spec.interface, file_bundle.requirement_map).
        # OpenAI-style strict structured outputs require *every* property to be
        # listed in "required", so strict=True can make providers reject these
        # schemas outright. We keep the schema as a guide and enforce the full
        # contract locally via validate_or_raise() in JsonAgent.run().
        return self._complete(
            model=model,
            messages=messages,
            usage_label=schema_name,
            parse=_loads_json_lenient,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": False, "schema": schema},
            },
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
            reasoning=reasoning,
            escalation_cap=escalation_cap,
            brace_truncation_check=True,
        )

    def complete_text(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        label: str,
        temperature: float = 0.1,
        max_tokens: int = 16000,
        retries: int | None = None,
        reasoning: dict[str, Any] | None = None,
        escalation_cap: int | None = None,
    ) -> str:
        """Plain-text completion (no JSON envelope). Used for per-file bundle
        emission: file content is never JSON-escaped and never has to share a
        single response budget with the rest of a bundle."""
        return self._complete(
            model=model,
            messages=messages,
            usage_label=label,
            parse=_strip_fences,
            response_format=None,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
            reasoning=reasoning,
            escalation_cap=escalation_cap,
        )

    def _complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        usage_label: str,
        parse: Callable[[str], Any],
        response_format: dict[str, Any] | None,
        temperature: float,
        max_tokens: int,
        retries: int | None,
        reasoning: dict[str, Any] | None,
        escalation_cap: int | None = None,
        brace_truncation_check: bool = False,
    ) -> Any:
        if retries is None:
            retries = self.default_retries
        if response_format is not None and (model, usage_label) in self._response_format_broken:
            response_format = None
        # Per-call reasoning config (per-agent, from agents.yaml) overrides the
        # instance default (pipeline.yaml `openrouter.reasoning`).
        reasoning_cfg = reasoning if reasoning is not None else self.reasoning
        # Extended thinking and schema-constrained output are mutually exclusive
        # on Anthropic-style providers (the format is implemented as a FORCED
        # tool call, which cannot be combined with thinking) — sending both
        # yields an empty assistant message. Reasoning wins: the schema still
        # travels in the messages and is enforced locally.
        if response_format is not None and _reasoning_active(reasoning_cfg):
            response_format = None

        def _build_extra_body(cfg: dict[str, Any] | None) -> dict[str, Any] | None:
            body: dict[str, Any] = {}
            if cfg:
                body["reasoning"] = cfg
            if self.provider:
                body["provider"] = self.provider
            return body or None

        extra_body = _build_extra_body(reasoning_cfg)
        # configured_cap is the ceiling escalation may reach for THIS call
        # (e.g. a bundle plan never justifies the full per-file budget);
        # effective_cap starts there and is lowered further when the provider
        # reports a credit limit.
        configured_cap = self.max_output_tokens
        if escalation_cap is not None:
            configured_cap = min(configured_cap, int(escalation_cap))
        effective_cap = configured_cap
        current_max = min(int(max_tokens), effective_cap)
        last_error: Exception | None = None
        attempt = 0
        credit_deescalations = 0
        reasoning_disabled_after_empty = False
        format_dropped_after_empty = False
        while True:
            try:
                kwargs: dict[str, Any] = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=current_max,
                    extra_body=extra_body,
                )
                if response_format is not None:
                    kwargs["response_format"] = response_format
                resp = self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                usage = getattr(resp, "usage", None)
                self._record_usage(usage_label, usage)
                completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
                content = choice.message.content or ""
                if not content.strip():
                    # The payload may be in tool_calls instead of content when
                    # the provider implements the schema as a forced tool call.
                    content = _tool_call_arguments(choice.message)
                finish_reason = getattr(choice, "finish_reason", None)
                provider_name = getattr(resp, "provider", None)
                # Verbatim record of every response (including truncated/empty
                # ones — those are exactly the calls that need a post-mortem)
                # goes to the run log only; the terminal keeps the summaries.
                console.log_only(
                    f"===== response [{usage_label}] model={model} "
                    + (f"provider={provider_name} " if provider_name else "")
                    + f"finish_reason={finish_reason} max_tokens={current_max} "
                    f"reasoning={'on' if _reasoning_active(reasoning_cfg) else 'off'} "
                    f"response_format={'on' if response_format is not None else 'off'} ====="
                )
                # The raw OpenRouter response object, exactly as received —
                # provider, native_finish_reason, error/refusal fields and all.
                dump = getattr(resp, "model_dump_json", None)
                if callable(dump):
                    try:
                        console.log_only(
                            "--- raw openrouter response ---\n" + dump(indent=2, exclude_none=True)
                        )
                    except Exception:
                        pass
                reasoning_text = getattr(choice.message, "reasoning", None)
                if reasoning_text:
                    console.log_only(f"--- reasoning ---\n{reasoning_text}")
                console.log_only(
                    "--- content ---\n" + (content if content.strip() else "<EMPTY CONTENT>")
                )
                # A provider-side safety layer stopped the response: the output
                # is incomplete regardless of how much text arrived. Must be
                # checked BEFORE the length/empty/parse paths or it gets
                # misdiagnosed as a token clamp (seen with the IdeaGenerator).
                if finish_reason == "content_filter":
                    raise ContentFilteredError(completion_tokens)
                # finish_reason='length' means the provider hit max_tokens mid-output;
                # the JSON is truncated and unparseable. Escalate the cap and retry
                # rather than failing on an "Unterminated string" further down.
                if finish_reason == "length":
                    raise TruncatedResponseError(content, completion_tokens)
                if not content.strip():
                    raise EmptyResponseError("Empty content in response.")
                try:
                    parsed = parse(content)
                except JSONDecodeError:
                    # Some providers mislabel truncation (finish_reason != 'length'
                    # on a cut-off body). Unbalanced braces mean the output was
                    # truncated — escalate instead of burning full-cost retries at
                    # the same cap that can never succeed.
                    if brace_truncation_check and content.count("{") > content.count("}"):
                        raise TruncatedResponseError(content, completion_tokens) from None
                    raise
                if format_dropped_after_empty:
                    # Empty with the format, fine without it: the provider cannot
                    # handle this schema as a response_format. Remember that so
                    # every later call for this label skips the dead first try.
                    self._response_format_broken.add((model, usage_label))
                    console.print(
                        f"  [dim]response_format disabled for {usage_label!r} on {model} for the "
                        "rest of this run (provider returns empty content with it).[/dim]"
                    )
                return parsed
            except TruncatedResponseError as trunc:
                # 'length' with EMPTY content means every output token went to
                # hidden reasoning before any answer text — the model is
                # ruminating, and escalating max_tokens only funds a longer
                # rumination at a higher price (measured: 32K->48K escalation
                # burned 80K tokens across two calls and still returned
                # nothing, while the reasoning-off retry answered within the
                # original budget). Recover like the empty-response path:
                # retry ONCE with reasoning explicitly disabled, same budget.
                if (_reasoning_active(reasoning_cfg) and not trunc.content.strip()
                        and not reasoning_disabled_after_empty):
                    reasoning_disabled_after_empty = True
                    reasoning_cfg = {"enabled": False}
                    extra_body = _build_extra_body(reasoning_cfg)
                    console.print(
                        "  [yellow]Response hit max_tokens with the whole budget spent on "
                        "hidden reasoning (empty content); retrying once with reasoning "
                        "explicitly disabled instead of escalating max_tokens.[/yellow]"
                    )
                    continue
                if _looks_degenerate(trunc.content):
                    last_error = RuntimeError(
                        f"Response truncated at max_tokens={current_max} and the output tail is "
                        "degenerate repetition — the model is looping, so raising max_tokens "
                        "only burns more tokens. Use a stronger model for this agent (or adjust "
                        "its temperature); do not raise the token limit."
                    )
                    break
                observed = trunc.completion_tokens
                if observed is not None and observed < current_max * 0.9:
                    # 'length' far below the requested budget is not a real
                    # token limit (every endpoint serving these models allows
                    # 128K completions) — it is a provider-side stop: a
                    # mislabeled safety filter or a mid-stream cut. Escalating
                    # max_tokens cannot help, but a plain retry can, because
                    # OpenRouter may route it to a different endpoint.
                    last_error = RuntimeError(
                        f"finish_reason='length' after only ~{observed} completion tokens although "
                        f"max_tokens={current_max} was requested — a provider-side stop, not a real "
                        "token limit. If this persists, pin `openrouter.provider` in pipeline.yaml "
                        "(e.g. order: [anthropic], allow_fallbacks: false) to avoid endpoints that "
                        "cut responses."
                    )
                    if attempt >= retries:
                        break
                    attempt += 1
                    console.print(
                        f"  [yellow]Response stopped at ~{observed}/{current_max} tokens "
                        f"(provider-side cut); retrying ({attempt}/{retries}).[/yellow]"
                    )
                    time.sleep(2 ** (attempt - 1))
                    continue
                if current_max >= effective_cap:
                    credit_limited = effective_cap < configured_cap
                    _limit = "credit balance" if credit_limited else "cap"
                    last_error = RuntimeError(
                        f"Response truncated at max_tokens={current_max} (finish_reason='length') "
                        f"and max_tokens is already at the {_limit} of {effective_cap}; this agent's "
                        f"output is too large. Reduce what it must emit"
                        + (" or raise openrouter.max_output_tokens."
                           if effective_cap >= self.max_output_tokens else ".")
                        + (" Add OpenRouter credits to allow a larger response."
                           if credit_limited else "")
                    )
                    break
                new_max = min(current_max * 2, effective_cap)
                console.print(
                    f"  [yellow]Response truncated at max_tokens={current_max}; "
                    f"retrying with max_tokens={new_max}.[/yellow]"
                )
                current_max = new_max
                # An escalation retry does not consume a transient-error retry.
                continue
            except ContentFilteredError as filt:
                last_error = RuntimeError(
                    "finish_reason='content_filter': the provider's safety layer stopped the "
                    f"response after ~{filt.completion_tokens} tokens. This benchmark's prompts "
                    "legitimately discuss hardware vulnerabilities, and some endpoints serving "
                    "the same model (Vertex/Bedrock/Azure) filter them while Anthropic-direct "
                    "does not — pin `openrouter.provider` in pipeline.yaml "
                    "(order: [anthropic], allow_fallbacks: false)."
                )
                if attempt >= retries:
                    break
                attempt += 1
                console.print(
                    f"  [yellow]Provider content filter stopped the response; retrying "
                    f"({attempt}/{retries}) — routing may pick a different endpoint.[/yellow]"
                )
                time.sleep(2 ** (attempt - 1))
                continue
            except EmptyResponseError as empty:
                # An empty assistant message with reasoning active is most often
                # the model emitting only a thinking block. Retry ONCE with
                # reasoning EXPLICITLY disabled — stripping the field entirely
                # falls back to the provider default, which re-enables reasoning
                # on reasoning-default models and re-hits the same wall.
                if _reasoning_active(reasoning_cfg) and not reasoning_disabled_after_empty:
                    reasoning_disabled_after_empty = True
                    reasoning_cfg = {"enabled": False}
                    extra_body = _build_extra_body(reasoning_cfg)
                    console.print(
                        "  [yellow]Empty response with reasoning enabled; retrying once "
                        "with reasoning explicitly disabled for this call.[/yellow]"
                    )
                    continue
                # A deterministic empty (same prompt → same silence) can never be
                # fixed by identical retries. Vary the request once: some
                # providers return empty content when a schema-constrained
                # response_format is active, so drop it and rely on the lenient
                # local JSON parse + schema validation instead.
                if response_format is not None and not format_dropped_after_empty:
                    format_dropped_after_empty = True
                    response_format = None
                    console.print(
                        "  [yellow]Empty response persists; retrying once without the JSON "
                        "response_format (the schema is still enforced locally).[/yellow]"
                    )
                    continue
                last_error = empty
                if attempt >= retries:
                    break
                attempt += 1
                time.sleep(2 ** (attempt - 1))
                continue
            except Exception as exc:
                # OpenRouter reserves credits from max_tokens up front and returns
                # a 402 stating the affordable amount. Lower the ceiling to that
                # and retry rather than crashing the run.
                affordable = _parse_affordable_tokens(str(exc))
                if (affordable is not None and affordable < current_max
                        and affordable >= 256 and credit_deescalations < 3):
                    credit_deescalations += 1
                    effective_cap = min(effective_cap, affordable)
                    console.print(
                        f"  [yellow]Credit-limited: reducing max_tokens "
                        f"{current_max} -> {effective_cap} and retrying.[/yellow]"
                    )
                    current_max = effective_cap
                    continue
                # Context-window overflow is an input-size problem — retrying the
                # same prompt cannot help. Fail fast with an actionable message.
                overflow = _context_overflow_message(exc, current_max)
                if overflow is not None:
                    raise RuntimeError(overflow) from exc
                # Terminal account/key errors are not retryable — fail fast with
                # an actionable message rather than burning the backoff budget.
                terminal = _account_limit_message(exc)
                if terminal is not None:
                    raise RuntimeError(terminal) from exc
                last_error = exc
                if attempt >= retries:
                    break
                attempt += 1
                time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"OpenRouter completion failed: {last_error}") from last_error
