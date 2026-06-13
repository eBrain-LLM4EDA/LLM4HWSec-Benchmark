from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .utils import read_json


def load_schema(path: str | Path) -> dict[str, Any]:
    return read_json(path)


def validate_or_raise(instance: Any, schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.path) or "<root>"
        raise ValueError(f"Schema validation failed at {where}: {first.message}")

