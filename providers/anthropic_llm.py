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

    @staticmethod
    def _format_error(e: Exception) -> str:
        """Pull the most informative string out of an anthropic.APIError.

        Default str(e) truncates the response body, so a 400 from Vision
        ends up as `Error code: 400 - {'type': 'error', 'error': {... 'mes`
        with the actual reason cut off. Reach into .body / .message to
        recover the full diagnostic.
        """
        body = getattr(e, "body", None)
        if isinstance(body, dict):
            err = body.get("error") or {}
            err_type = err.get("type")
            err_msg = err.get("message")
            if err_type or err_msg:
                return f"{err_type or 'unknown'}: {err_msg or '(no message)'}"
        return str(e)

    def _call_with_image(
        self,
        client,
        prompt: str,
        system_prompt: str,
        image_block: dict | None,
    ):
        content: list[dict] = []
        if image_block:
            content.append(image_block)
        content.append({"type": "text", "text": prompt})
        return client.messages.create(
            model=_DEFAULT_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )

    def call_llm(
        self,
        *,
        prompt: str,
        image_url: str = "",
        system_prompt: str,
        label: str = "llm",
    ) -> str:
        client = self._ensure_client()

        # Build the URL-source block (preferred — Anthropic fetches the
        # image itself, no 5MB base64 cap) and a base64 fallback. We try
        # URL first; if Anthropic can't reach the URL or rejects it, we
        # fall back to base64 with the bytes we download ourselves.
        url_block = None
        b64_block = None
        b64_error: str | None = None

        if image_url:
            if image_url.lower().startswith(("http://", "https://")):
                url_block = {
                    "type": "image",
                    "source": {"type": "url", "url": image_url},
                }
            try:
                media_type, b64 = self._fetch_image_b64(image_url)
                b64_block = {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                }
            except Exception as e:
                b64_error = str(e)

        attempts = [b for b in (url_block, b64_block) if b]
        if image_url and not attempts:
            raise ProviderError(
                f"Failed to prepare reference image for Anthropic: {b64_error}"
            )

        last_exc: Exception | None = None
        for i, block in enumerate(attempts or [None]):
            try:
                resp = self._call_with_image(client, prompt, system_prompt, block)
                break
            except Exception as e:
                last_exc = e
                if is_censorship_error(e):
                    raise CensorshipError(self._format_error(e)) from e
                # Log the full detail and try the next strategy if any.
                detail = self._format_error(e)
                source_kind = "url" if block is url_block else "base64"
                if i < len(attempts) - 1:
                    self._log("WARN", f"{label} Anthropic {source_kind} source failed ({detail}); retrying with fallback")
                    continue
                # No more strategies left.
                if is_transient(e):
                    raise TransientError(detail) from e
                raise ProviderError(f"{label} Anthropic call failed: {detail}") from e
        else:
            # Either no attempts were made (no image), or none succeeded.
            if last_exc is not None:
                detail = self._format_error(last_exc)
                raise ProviderError(f"{label} Anthropic call failed: {detail}") from last_exc

        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        out = "\n".join(parts).strip()
        if not out:
            raise ProviderError(f"{label}: Anthropic returned empty content")
        return out
