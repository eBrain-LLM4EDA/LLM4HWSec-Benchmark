from __future__ import annotations

import json
import re
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
        rendered = {
            key: value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
            for key, value in variables.items()
        }
        prompt = render_template(self.prompt_template, **rendered)
        prompt = re.sub(r"\{\{[^}]+\}\}", "", prompt).strip()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Return only JSON matching the schema. Do not include markdown fences."},
        ]
        result = self.llm.complete_json(
            model=self.config.model,
            messages=messages,
            schema_name=f"{self.config.name}_output",
            schema=self.schema,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        validate_or_raise(result, self.schema)
        return result

