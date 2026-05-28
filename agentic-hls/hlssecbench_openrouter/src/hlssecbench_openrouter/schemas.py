from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .utils import read_json


def load_schema(path: str | Path) -> dict[str, Any]:
    return read_json(path)


def validate_or_raise(instance: Any, schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
    if errors:
        formatted = []
        for err in errors:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            formatted.append(f"{loc}: {err.message}")
        raise ValueError("Schema validation failed:\n" + "\n".join(formatted))
