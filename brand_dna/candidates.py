"""Candidate product image detection — heuristic filter + LLM tagger."""
from __future__ import annotations

from io import BytesIO

from .types import CollectedImage


_MIN_DIM = 300
_MIN_RATIO = 0.5
_MAX_RATIO = 2.0


def _ensure_dims(img: CollectedImage) -> None:
    if img.width and img.height:
        return
    try:
        from PIL import Image
        source = BytesIO(img.data) if img.data is not None else img.path
        with Image.open(source) as im:
            img.width, img.height = im.size
    except Exception:
        img.width = img.height = 0


def heuristic_filter(images: list[CollectedImage], cap: int = 20) -> list[CollectedImage]:
    """Pick the most plausible product/lifestyle candidates from a flat list.

    Cheap rules: dimensions ≥ 300px, sane aspect ratio, prefer larger images,
    deduplicate by source. Returns up to `cap` images sorted by area desc.
    Handles both on-disk images (`path` set) and in-memory site images
    (`data` set).
    """
    seen: set = set()
    keepers: list[CollectedImage] = []
    for img in images:
        if img.data is not None:
            key = ("data", id(img))
        elif img.path is not None:
            if not img.path.exists():
                continue
            key = ("path", img.path)
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
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
