"""Provider abstract base class with shared retry logic."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional  # noqa: F401

from .errors import is_transient
from .parsing import download_to


def _default_log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level:<4} {msg}", flush=True)


class Provider(ABC):
    name: str            # canonical short name, e.g. "muapi"
    display_name: str    # human label, e.g. "MuAPI"

    def __init__(self) -> None:
        self._on_log: Callable[[str, str], None] = _default_log

    def set_logger(self, on_log: Callable[[str, str], None]) -> None:
        self._on_log = on_log or _default_log

    def _log(self, level: str, msg: str) -> None:
        try:
            self._on_log(level, msg)
        except Exception:
            _default_log(level, msg)

    def _retry_transient(self, fn: Callable, *args, label: str = "op",
                         attempts: int = 3, **kwargs):
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_err = e
                if attempt < attempts - 1 and is_transient(e):
                    self._log(
                        "WARN",
                        f"{label} transient error, retry {attempt + 1}/{attempts} in {2 ** attempt}s",
                    )
                    time.sleep(2 ** attempt)
                    continue
                raise
        if last_err:
            raise last_err

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def upload_image(self, path: Path) -> str: ...

    @abstractmethod
    def call_image(
        self,
        *,
        model: str,
        prompt: str,
        image_urls: list[str],
        resolution: str,
        aspect_ratio: str,
        output_format: str = "png",
        label: str = "image",
    ) -> str: ...

    @abstractmethod
    def call_llm(
        self,
        *,
        prompt: str,
        image_url: str = "",
        system_prompt: str,
        label: str = "llm",
    ) -> str: ...

    def download(self, url: str, dest: Path) -> None:
        download_to(url, dest)
