from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, IO

from rich.console import Console


class TeeConsole(Console):
    """Console that mirrors everything printed to an attached plain-text log
    file, so each generation run leaves a `generation.log` in its output folder
    for post-mortem debugging (the terminal scrollback is not a durable record
    of a multi-hour LLM run)."""

    def __init__(self) -> None:
        super().__init__()
        self._file_console: Console | None = None
        self._file_handle: IO[str] | None = None

    def attach_log_file(self, path: Path) -> None:
        self.detach_log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(path, "a", encoding="utf-8")
        self._file_console = Console(
            file=self._file_handle,
            no_color=True,
            highlight=False,
            width=200,
            soft_wrap=True,
        )
        self._file_console.print(
            f"===== run started {datetime.now():%Y-%m-%d %H:%M:%S} ====="
        )
        self._file_handle.flush()

    def detach_log_file(self) -> None:
        if self._file_handle is not None:
            try:
                self._file_handle.close()
            except OSError:
                pass
        self._file_console = None
        self._file_handle = None

    def print(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().print(*args, **kwargs)
        if self._file_console is not None and self._file_handle is not None:
            # Logging must never break the run it is documenting.
            try:
                self._file_console.print(f"[{datetime.now():%H:%M:%S}]", *args, **kwargs)
                self._file_handle.flush()
            except Exception:
                pass

    def log_only(self, message: str) -> None:
        """Write verbatim text to the attached log file ONLY (not the terminal).
        Markup and highlighting are disabled so raw LLM output — which freely
        contains `[...]` sequences rich would misread as style tags — is stored
        exactly as received. No-op when no log file is attached."""
        if self._file_console is None or self._file_handle is None:
            return
        try:
            self._file_console.print(
                f"[{datetime.now():%H:%M:%S}] {message}",
                markup=False, highlight=False,
            )
            self._file_handle.flush()
        except Exception:
            pass


# Shared instance: every module prints through this so an attached run log
# captures the whole pipeline, not just one module's output.
console = TeeConsole()
