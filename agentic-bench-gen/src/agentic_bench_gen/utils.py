from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_yaml(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def render_template(template: str, **values: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return str(values.get(match.group(1).strip(), ""))

    return re.sub(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", repl, template)


def slugify(value: str, fallback: str = "benchmark_case") -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip().lower()).strip("_")
    return slug or fallback


def env_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

