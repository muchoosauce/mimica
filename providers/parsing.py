"""Pure helpers for parsing provider responses and downloading files."""
from __future__ import annotations

import json
import re
import socket
import time
from pathlib import Path

import requests


def coerce_text(out) -> str:
    """Best-effort flatten of an LLM response into a single string."""
    if isinstance(out, str):
        return out
    if isinstance(out, list):
        parts = []
        for item in out:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
        return "\n".join(p for p in parts if p)
    if isinstance(out, dict):
        return out.get("text") or out.get("content") or json.dumps(out)
    return str(out)


def parse_prompts(text: str) -> list[str]:
    """Split LLM text into individual ad prompts. Each prompt starts with ^."""
    matches = re.findall(r"\^[^\^]+", text, flags=re.DOTALL)
    return [m.strip() for m in matches if m.strip().startswith("^")]


def fallback_split(text: str, n: int) -> list[str]:
    """Last-resort splitter when ^ markers are missing."""
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    prompts = []
    for c in chunks:
        if not c.startswith("^"):
            c = "^" + c.lstrip("^").lstrip()
        prompts.append(c)
    return prompts[:n]


def first_url(out):
    """Walk a response payload looking for the first http(s) URL."""
    if isinstance(out, str):
        return out if out.startswith("http") else None
    if isinstance(out, list):
        for item in out:
            if isinstance(item, str) and item.startswith("http"):
                return item
            if isinstance(item, dict):
                u = item.get("url") or item.get("image_url") or item.get("output")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    if isinstance(out, dict):
        for k in ("url", "image_url", "output", "image"):
            v = out.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, list):
                r = first_url(v)
                if r:
                    return r
    return None


_RETRYABLE_NET_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    socket.gaierror,
    ConnectionResetError,
)


def download_to(url: str, dest: Path, timeout: int = 180, max_attempts: int = 4) -> None:
    """Download `url` to `dest`. Retries up to `max_attempts` times on
    transient network errors. See forge/providers/parsing.py for the full
    rationale (Windows DNS flakes were forcing users to "spam" regen).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, timeout=timeout, stream=True)
            if 500 <= r.status_code < 600:
                raise requests.exceptions.HTTPError(
                    f"{r.status_code} server error on download (attempt {attempt})",
                    response=r,
                )
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            return
        except _RETRYABLE_NET_EXCEPTIONS as e:
            last_exc = e
        except requests.exceptions.HTTPError as e:
            if e.response is not None and 500 <= e.response.status_code < 600:
                last_exc = e
            else:
                raise
        if attempt < max_attempts:
            time.sleep((1, 3, 6, 10)[min(attempt - 1, 3)])
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"download_to: {url!r} failed after {max_attempts} attempts")
