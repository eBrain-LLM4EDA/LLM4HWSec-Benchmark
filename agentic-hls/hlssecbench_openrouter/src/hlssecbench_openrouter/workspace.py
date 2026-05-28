from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable

from .utils import write_json, write_text


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, rel: str | Path) -> Path:
        candidate = (self.root / rel).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError(f"Unsafe path outside workspace: {rel}")
        return candidate

    def write_json(self, rel: str | Path, data) -> None:
        write_json(self.path(rel), data)

    def write_text(self, rel: str | Path, content: str) -> None:
        write_text(self.path(rel), content)

    def write_file_bundle(self, bundle: dict, base_dir: str = ".") -> None:
        for file_obj in bundle.get("files", []):
            rel_path = Path(base_dir) / file_obj["path"]
            self.write_text(rel_path, file_obj["content"])
            # Make shell scripts executable.
            if rel_path.suffix == ".sh":
                os.chmod(self.path(rel_path), 0o755)

    def copy_tree_to(self, dst: str | Path) -> None:
        dst_path = Path(dst).resolve()
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(self.root, dst_path)
