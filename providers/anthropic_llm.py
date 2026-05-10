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

    # Anthropic Vision rejects base64 image content > 5 MB. We pre-compress
    # so the fallback path actually works on big brand product PNGs (we've
    # seen 8-15 MB exports) — otherwise the request errors out with
    # "Image exceeds 5 MB maximum" right after the URL fetch fails.
    _ANTHROPIC_BASE64_LIMIT = 5 * 1024 * 1024

    @classmethod
    def _fetch_image_b64(cls, image_url: str) -> tuple[str, str]:
        """Download `image_url` and return (media_type, base64), recompressed
        to fit Anthropic's 5MB cap on inline base64 images.

        Anthropic only accepts image/png, image/jpeg, image/webp, image/gif —
        anything else gets normalized to image/png. If the raw bytes exceed
        the cap we re-encode through PIL as JPEG with progressive quality /
        dimension reductions until it fits.
        """
        r = requests.get(image_url, timeout=60)
        r.raise_for_status()
        media_type = (r.headers.get("Content-Type") or "image/png").split(";")[0].strip().lower()
        if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            media_type = "image/png"
        raw = r.content
        if len(raw) <= cls._ANTHROPIC_BASE64_LIMIT:
            return media_type, base64.b64encode(raw).decode("ascii")

        # Over the cap — re-encode to JPEG with descending quality until it
        # fits. Same pattern as the upload compression in muapi.py.
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            max_dim = 2400
            quality = 85
            for _ in range(6):
                w, h = im.size
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    im_s = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                else:
                    im_s = im
                buf = io.BytesIO()
                im_s.save(buf, "JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                if len(data) <= cls._ANTHROPIC_BASE64_LIMIT:
                    return "image/jpeg", base64.b64encode(data).decode("ascii")
                quality = max(40, quality - 15)
                max_dim = max(1200, int(max_dim * 0.85))
            # Last attempt's bytes — Anthropic may still reject, but the
            # caller will see a clear error rather than us silently sending
            # an over-cap payload.
            return "image/jpeg", base64.b64encode(data).decode("ascii")
        except ImportError:
            # PIL missing — surface the size issue with a clear message.
            raise RuntimeError(
                f"Image is {len(raw)/1e6:.1f} MB, over Anthropic's 5 MB cap, "
                "and PIL is not available to recompress."
            )

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
