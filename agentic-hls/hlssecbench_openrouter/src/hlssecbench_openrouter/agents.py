from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .llm import OpenRouterLLM
from .schemas import load_schema, validate_or_raise
from .utils import read_text, render_template


@dataclass
class AgentConfig:
    name: str
    model: str
    prompt_path: Path
    schema_path: Path
    temperature: float
    max_tokens: int


class JsonAgent:
    def __init__(self, llm: OpenRouterLLM, config: AgentConfig):
        self.llm = llm
        self.config = config
        self.prompt_template = read_text(config.prompt_path)
        self.schema = load_schema(config.schema_path)

    def run(self, variables: dict[str, Any]) -> dict[str, Any]:
        variables = {"repair_context_json": "{}", **variables}
        rendered_vars = {
            k: v if isinstance(v, str) else json.dumps(v, indent=2, sort_keys=True)
            for k, v in variables.items()
        }
        system_prompt = render_template(self.prompt_template, **rendered_vars)
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": "Return only JSON matching the schema. Do not include markdown fences.",
            },
        ]
        result = self.llm.complete_json(
            model=self.config.model,
            messages=messages,
            schema_name=f"{self.config.name}_schema",
            schema=self.schema,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        validate_or_raise(result, self.schema)
        return result
