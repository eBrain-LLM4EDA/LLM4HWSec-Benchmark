from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

from openai import OpenAI


@dataclass
class OpenRouterSettings:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "http://localhost"
    title: str = "HLSSecBench-Agentic-Generator"
    timeout_seconds: float = 120.0
    max_retries: int = 0


class OpenRouterLLM:
    def __init__(self, settings: OpenRouterSettings):
        self.default_retries = settings.max_retries
        headers = {
            "HTTP-Referer": settings.referer,
            "X-OpenRouter-Title": settings.title,
        }
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            default_headers=headers,
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
        if timeout_seconds is None:
            timeout_seconds = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "120"))
        if max_retries is None:
            max_retries = int(os.environ.get("OPENROUTER_MAX_RETRIES", "0"))
        return cls(
            OpenRouterSettings(
                api_key=api_key,
                base_url=base_url,
                referer=os.environ.get("OPENROUTER_REFERER", "http://localhost"),
                title=os.environ.get("OPENROUTER_TITLE", "HLSSecBench-Agentic-Generator"),
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
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
        max_tokens: int = 12000,
        retries: int | None = None,
    ) -> dict[str, Any]:
        if retries is None:
            retries = self.default_retries
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": schema,
                        },
                    },
                )
                choice = response.choices[0]
                content = choice.message.content
                if not content:
                    raise ValueError("Empty model response.")
                try:
                    return json.loads(content)
                except JSONDecodeError as exc:
                    finish_reason = getattr(choice, "finish_reason", None)
                    detail = (
                        f"Invalid JSON from provider ({exc.msg} at char {exc.pos}; "
                        f"finish_reason={finish_reason!r}; received {len(content)} chars)."
                    )
                    if finish_reason == "length":
                        detail += (
                            " The response was truncated; reduce the prompt/output size "
                            "or increase the agent max_tokens setting."
                        )
                    raise ValueError(detail) from exc
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(2**attempt)
        raise RuntimeError(
            f"OpenRouter JSON completion failed after {retries + 1} attempt(s): {last_error}"
        ) from last_error

    def complete_text(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 12000,
        retries: int | None = None,
    ) -> str:
        if retries is None:
            retries = self.default_retries
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty model response.")
                return content
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(2**attempt)
        raise RuntimeError(
            f"OpenRouter text completion failed after {retries + 1} attempt(s): {last_error}"
        ) from last_error
