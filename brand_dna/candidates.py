"""Candidate product image detection — heuristic filter + LLM tagger."""
from __future__ import annotations

from pathlib import Path

from .types import CollectedImage


_MIN_DIM = 300
_MIN_RATIO = 0.5
_MAX_RATIO = 2.0


def _ensure_dims(img: CollectedImage) -> None:
    if img.width and img.height:
        return
    try:
        from PIL import Image
        with Image.open(img.path) as im:
            img.width, img.height = im.size
    except Exception:
        img.width = img.height = 0


def heuristic_filter(images: list[CollectedImage], cap: int = 20) -> list[CollectedImage]:
    """Pick the most plausible product/lifestyle candidates from a flat list.

    Cheap rules: dimensions ≥ 300px, sane aspect ratio, prefer larger images,
    deduplicate by file path. Returns up to `cap` images sorted by area desc.
    """
    seen: set[Path] = set()
    keepers: list[CollectedImage] = []
    for img in images:
        if img.path in seen or not img.path.exists():
            continue
        seen.add(img.path)
        _ensure_dims(img)
        if not img.width or not img.height:
            continue
        if min(img.width, img.height) < _MIN_DIM:
            continue
        ratio = img.width / img.height
        if ratio < _MIN_RATIO or ratio > _MAX_RATIO:
            continue
        keepers.append(img)
    keepers.sort(key=lambda i: i.width * i.height, reverse=True)
    return keepers[:cap]
