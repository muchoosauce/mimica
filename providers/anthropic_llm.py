"""Direct Anthropic API LLM client.

Used as the priority LLM path when ANTHROPIC_API_KEY is configured. Same
call_llm() signature as Provider, so it can act as a drop-in replacement —
or as a wrapper that falls back to MuAPI/Kie when Anthropic itself fails.

Image gen and video gen still go through MuAPI/Kie — Anthropic doesn't host
NanoBanana / Kling.
"""
from __future__ import annotations

import base64
import os
from typing import Callable

import requests

from .errors import (
    CensorshipError,
    ProviderError,
    TransientError,
    is_censorship_error,
    is_transient,
)


_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192


def _default_log(level: str, msg: str) -> None:
    pass


class AnthropicLLM:
    """Direct Anthropic API client implementing the call_llm() contract."""

    name = "anthropic"
    display_name = "Anthropic"

    def __init__(self) -> None:
        self._client = None
        self._on_log: Callable[[str, str], None] = _default_log

    @staticmethod
    def is_configured() -> bool:
        return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())

    def set_logger(self, on_log: Callable[[str, str], None]) -> None:
        self._on_log = on_log or _default_log

    def _log(self, level: str, msg: str) -> None:
        try:
            self._on_log(level, msg)
        except Exception:
            pass

    def _ensure_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    @staticmethod
    def _fetch_image_b64(image_url: str) -> tuple[str, str]:
        """Download `image_url` and return (media_type, base64). Anthropic
        only accepts a few media types — coerce anything weird to image/png.

        Used as a fallback when the URL isn't directly fetchable by Anthropic
        (e.g. a localhost preview server). Carries a 5MB payload cap that
        the URL source path doesn't have.
        """
        r = requests.get(image_url, timeout=60)
        r.raise_for_status()
        media_type = (r.headers.get("Content-Type") or "image/png").split(";")[0].strip().lower()
        if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            media_type = "image/png"
        return media_type, base64.b64encode(r.content).decode("ascii")

    def call_llm(
        self,
        *,
        prompt: str,
        image_url: str = "",
        system_prompt: str,
        label: str = "llm",
    ) -> str:
        client = self._ensure_client()

        content: list[dict] = []
        if image_url:
            # Prefer the URL source format: Anthropic fetches the image
            # itself, no 5MB base64 payload cap, no client-side download
            # / re-encode. The previous base64 path tripped a 400 from the
            # Vision API on swap_product runs because the 1440×3840 grid
            # PNG exceeded the encoded-payload size limit. We only fall
            # back to base64 if the URL isn't a public http(s) one.
            if image_url.lower().startswith(("http://", "https://")):
                content.append({
                    "type": "image",
                    "source": {"type": "url", "url": image_url},
                })
            else:
                try:
                    media_type, b64 = self._fetch_image_b64(image_url)
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    })
                except Exception as e:
                    raise ProviderError(
                        f"Failed to fetch reference image for Anthropic: {e}"
                    ) from e
        content.append({"type": "text", "text": prompt})

        try:
            resp = client.messages.create(
                model=_DEFAULT_MODEL,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
            )
        except Exception as e:
            msg = str(e)
            if is_censorship_error(e):
                raise CensorshipError(msg) from e
            if is_transient(e):
                raise TransientError(msg) from e
            raise ProviderError(f"{label} Anthropic call failed: {msg}") from e

        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        out = "\n".join(parts).strip()
        if not out:
            raise ProviderError(f"{label}: Anthropic returned empty content")
        return out
