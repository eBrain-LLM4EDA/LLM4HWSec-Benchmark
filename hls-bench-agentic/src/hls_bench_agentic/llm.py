from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import BadRequestError, OpenAI


def _extract_json_block(text: str) -> str | None:
    """Return the first {...} block found in text (handles markdown fences)."""
    # Strip ```json ... ``` fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    # Find the outermost { ... }
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


@dataclass
class OpenRouterSettings:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "http://localhost"
    title: str = "HLSBenchAgentic"


class OpenRouterLLM:
    def __init__(self, settings: OpenRouterSettings):
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            default_headers={
                "HTTP-Referer": settings.referer,
                "X-Title": settings.title,
            },
        )

    @classmethod
    def from_env(cls, base_url: str = "https://openrouter.ai/api/v1") -> "OpenRouterLLM":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY before running.")
        return cls(
            OpenRouterSettings(
                api_key=api_key,
                base_url=base_url,
                referer=os.environ.get("OPENROUTER_REFERER", "http://localhost"),
                title=os.environ.get("OPENROUTER_TITLE", "HLSBenchAgentic"),
            )
        )

    def _extract_content(self, resp: Any) -> str:
        """Pull text from a completion response, guarding against null choices."""
        choices = resp.choices
        if not choices:
            raise ValueError(f"Response has no choices (choices={choices!r}). "
                             "The model may not support this response_format.")
        content = choices[0].message.content
        if not content:
            raise ValueError("Empty content in response choice.")
        return content

    def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 16000,
        retries: int = 3,
    ) -> dict[str, Any]:
        """
        Request a JSON response.  Strategy (per attempt):
          1. Try json_schema with strict=True  (best structured output).
          2. If choices comes back null, fall back to json_object mode.
          3. As a last resort, parse the first JSON block from a plain text reply.
        """
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                content = self._try_json_schema(model, messages, schema_name, schema, temperature, max_tokens)
                return json.loads(content)
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(
            f"OpenRouter JSON completion failed after {retries + 1} attempts: {last_error}"
        ) from last_error

    def _try_json_schema(
        self,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> str:
        # Attempt 1: strict json_schema
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
            return self._extract_content(resp)
        except (BadRequestError, ValueError, TypeError):
            pass  # choices was None — fall through to json_object

        # Attempt 2: json_object (broader model support)
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return self._extract_content(resp)
        except (ValueError, TypeError):
            pass

        # Attempt 3: plain text, extract first {...} block
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = self._extract_content(resp)
        extracted = _extract_json_block(raw)
        if not extracted:
            raise ValueError("Could not extract a JSON object from the plain-text response.")
        return extracted

    def complete_text(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 16000,
        retries: int = 3,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return self._extract_content(resp)
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenRouter text completion failed after {retries + 1} attempts: {last_error}") from last_error
