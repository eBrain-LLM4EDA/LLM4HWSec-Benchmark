from __future__ import annotations

import os
import shutil
from pathlib import Path

from .utils import write_json, write_text


class Workspace:
    """Sandboxed directory: all writes are confined to self.root."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, rel: str | Path) -> Path:
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Unsafe path escapes workspace: {rel!r}")
        return candidate

    def write_json(self, rel: str | Path, data: object) -> None:
        write_json(self.path(rel), data)

    def write_text(self, rel: str | Path, content: str) -> None:
        write_text(self.path(rel), content)

    def write_file_bundle(self, bundle: dict, base_dir: str = ".") -> None:
        """Write files from a {files: [{path, content}]} bundle, enforcing sandbox."""
        for file_obj in bundle.get("files", []):
            raw_path = file_obj["path"]
            # Reject absolute paths before joining.
            if Path(raw_path).is_absolute():
                raise ValueError(f"Absolute path in bundle rejected: {raw_path!r}")
            rel = Path(base_dir) / raw_path
            self.write_text(rel, file_obj["content"])
            if rel.suffix == ".sh":
                os.chmod(self.path(rel), 0o755)

    def normalize_hls_implementation(
        self,
        bundle: dict,
        impl_path: str = "src/impl.cpp",
        top_function: str | None = None,
    ) -> None:
        """Create the canonical implementation layout expected by tool scripts.

        Expert agents may emit natural file names such as compare_token.c, while
        tester/tool prompts compile src/impl.cpp. Mirroring the implementation
        here keeps execution infrastructure deterministic without requiring the
        tester to inspect the expert bundle.
        """
        source = self._select_implementation_file(bundle, top_function=top_function)
        if source is None:
            raise ValueError("No C/C++ implementation file found in expert bundle")

        source_path = Path(source.get("path", ""))
        content = source["content"]
        if source_path.suffix.lower() == ".c":
            content = self._with_extern_c_guards(content)
        self.write_text(impl_path, content)

        for file_obj in bundle.get("files", []):
            raw_path = file_obj["path"]
            if Path(raw_path).is_absolute():
                raise ValueError(f"Absolute path in bundle rejected: {raw_path!r}")
            path = Path(raw_path)
            if path.suffix in {".h", ".hpp"}:
                self.write_text(Path("src") / path.name, self._with_extern_c_guards(file_obj["content"]))

    def copy_tree_to(self, dst: str | Path) -> None:
        dst_path = Path(dst).resolve()
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(self.root, dst_path)

    @staticmethod
    def _select_implementation_file(bundle: dict, top_function: str | None = None) -> dict | None:
        files = bundle.get("files", [])
        source_suffixes = {".c", ".cc", ".cpp", ".cxx"}

        candidates = [
            f for f in files
            if Path(f.get("path", "")).suffix.lower() in source_suffixes
        ]
        if not candidates:
            return None

        def score(file_obj: dict) -> tuple[int, int, int, int]:
            path = Path(file_obj.get("path", ""))
            text = file_obj.get("content", "")
            stem = path.stem.lower()
            looks_like_test = "test" in stem or "tb_" in stem
            has_main = " main(" in text or "\nmain(" in text
            is_impl = stem == "impl"
            has_top = bool(top_function and f"{top_function}(" in text)
            return (
                1 if looks_like_test or has_main else 0,
                0 if is_impl else 1,
                0 if has_top else 1,
                len(path.parts),
            )

        return sorted(candidates, key=score)[0]

    @staticmethod
    def _with_extern_c_guards(content: str) -> str:
        if 'extern "C"' in content:
            return content
        return (
            "#ifdef __cplusplus\n"
            'extern "C" {\n'
            "#endif\n\n"
            f"{content.rstrip()}\n\n"
            "#ifdef __cplusplus\n"
            "}\n"
            "#endif\n"
        )
