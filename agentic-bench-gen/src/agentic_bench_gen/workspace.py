from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .utils import write_json, write_text


def is_safe_relative_path(path: str | Path) -> bool:
    """Return whether a generated path is non-empty, relative, and contained."""
    raw = str(path).strip()
    candidate = Path(raw)
    return bool(raw) and raw != "." and not candidate.is_absolute() and ".." not in candidate.parts


class Workspace:
    """Sandboxed benchmark case workspace."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, rel: str | Path) -> Path:
        if not is_safe_relative_path(rel):
            raise ValueError(f"Unsafe workspace path: {rel!r}")
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Unsafe path escapes workspace: {rel!r}")
        return candidate

    def write_json(self, rel: str | Path, data: Any) -> None:
        write_json(self.path(rel), data)

    def write_text(self, rel: str | Path, content: str) -> None:
        write_text(self.path(rel), content)

    def write_file_bundle(self, bundle: dict[str, Any], base_dir: str = ".") -> None:
        for file_obj in bundle.get("files", []):
            raw_path = file_obj["path"]
            if Path(raw_path).is_absolute():
                raise ValueError(f"Absolute path in bundle rejected: {raw_path!r}")
            rel = Path(base_dir) / raw_path
            self.write_text(rel, str(file_obj.get("content", "")))
            if rel.suffix == ".sh":
                os.chmod(self.path(rel), 0o755)

    def copy_to(self, dst: str | Path) -> None:
        dst_path = Path(dst).resolve()
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(self.root, dst_path)
