from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


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


def _loads_json_lenient(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except JSONDecodeError:
        extracted = _extract_json_block(content)
        if not extracted:
            raise
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


class OpenRouterLLM:
    def __init__(self, settings: OpenRouterSettings):
        if OpenAI is None:
            raise RuntimeError("Install the 'openai' package to use OpenRouter generation.")
        self.default_retries = settings.max_retries
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
            )
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
    ) -> dict[str, Any]:
        if retries is None:
            retries = self.default_retries
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
                    },
                )
                content = resp.choices[0].message.content
                if not content:
                    raise ValueError("Empty content in response.")
                return _loads_json_lenient(content)
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenRouter JSON completion failed: {last_error}") from last_error

