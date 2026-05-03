"""Anthropic API wrapper for Brand DNA generation and image tagging.

Uses the official `anthropic` SDK, claude-opus-4-7, adaptive thinking, prompt
caching on the system prompt, and structured outputs via `messages.parse()`.
"""
from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .prompts import DNA_SYSTEM_PROMPT, TAGGER_SYSTEM_PROMPT
from .types import CollectedImage, ImageTag


MODEL = "claude-opus-4-7"
MAX_IMAGE_DIM = 1280       # downsize before base64-encoding to control token cost
JPEG_QUALITY = 85


class BrandDNAModel(BaseModel):
    brand_identity: str
    color_palette: str
    typography: str
    tone_of_voice: str
    copy_patterns: str
    visual_style: str
    product: str
    avoid: str
    target_audience: str

    def to_markdown(self) -> str:
        return (
            f"## Brand Identity\n{self.brand_identity.strip()}\n\n"
            f"## Color Palette\n{self.color_palette.strip()}\n\n"
            f"## Typography\n{self.typography.strip()}\n\n"
            f"## Tone of Voice\n{self.tone_of_voice.strip()}\n\n"
            f"## Copy Patterns\n{self.copy_patterns.strip()}\n\n"
            f"## Visual Style\n{self.visual_style.strip()}\n\n"
            f"## Product\n{self.product.strip()}\n\n"
            f"## Avoid\n{self.avoid.strip()}\n\n"
            f"## Target Audience\n{self.target_audience.strip()}\n"
        )


class _TaggedImage(BaseModel):
    tag: ImageTag


class _TaggerResponse(BaseModel):
    tags: list[_TaggedImage]


def _encode_image(path: Path) -> tuple[str, str]:
    """Resize if needed and return (media_type, base64). Falls back to original bytes if PIL is missing."""
    try:
        from PIL import Image
    except ImportError:
        with open(path, "rb") as f:
            return "image/png", base64.b64encode(f.read()).decode("ascii")

    try:
        im = Image.open(path)
    except Exception:
        with open(path, "rb") as f:
            return "image/png", base64.b64encode(f.read()).decode("ascii")

    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / max(w, h)
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = BytesIO()
    im.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return "image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii")


def _image_blocks(images: list[CollectedImage]) -> list[dict]:
    blocks = []
    for img in images:
        try:
            media_type, data = _encode_image(img.path)
        except Exception:
            continue
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })
    return blocks


class AnthropicClient:
    def __init__(self) -> None:
        self._client = None

    @staticmethod
    def is_configured() -> bool:
        return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())

    def _ensure(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def generate_dna(
        self,
        compiled_text: str,
        images: list[CollectedImage],
        on_log=lambda lvl, msg: None,
    ) -> BrandDNAModel:
        client = self._ensure()
        user_content: list[dict] = []
        if compiled_text.strip():
            user_content.append({"type": "text", "text": compiled_text})
        user_content.extend(_image_blocks(images))
        if not user_content:
            raise RuntimeError("No content to analyse — sources produced no text or images.")

        on_log("INFO", f"Calling Claude {MODEL} with {len(images)} images "
                       f"and ~{len(compiled_text)} chars of text")
        response = client.messages.parse(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[{
                "type": "text",
                "text": DNA_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_content}],
            output_format=BrandDNAModel,
        )
        usage = response.usage
        on_log(
            "INFO",
            f"Tokens — input: {usage.input_tokens}, "
            f"cached read: {usage.cache_read_input_tokens}, "
            f"cache write: {usage.cache_creation_input_tokens}, "
            f"output: {usage.output_tokens}",
        )
        return response.parsed_output

    def tag_images(
        self,
        images: list[CollectedImage],
        on_log=lambda lvl, msg: None,
    ) -> list[ImageTag]:
        if not images:
            return []
        client = self._ensure()
        content: list[dict] = [{
            "type": "text",
            "text": (
                f"Classify the {len(images)} images that follow, in order. "
                "Respond with one tag per image."
            ),
        }]
        content.extend(_image_blocks(images))
        on_log("INFO", f"Tagging {len(images)} candidate images via Claude {MODEL}")
        response = client.messages.parse(
            model=MODEL,
            max_tokens=2048,
            output_config={"effort": "low"},
            system=[{
                "type": "text",
                "text": TAGGER_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": content}],
            output_format=_TaggerResponse,
        )
        tags = [t.tag for t in response.parsed_output.tags]
        if len(tags) != len(images):
            on_log("WARN", f"Tagger returned {len(tags)} tags for {len(images)} images; padding with 'other'")
            tags = (tags + ["other"] * len(images))[:len(images)]
        return tags
