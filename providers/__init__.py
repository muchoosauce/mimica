"""Provider abstraction for image-generation backends (MuAPI, Kie).

Public surface:
    Provider                — ABC implemented by MuApiProvider and KieProvider
    get_provider(name, ...) — factory by provider name ("muapi" | "kie")
    get_active_provider(...) — reads ACTIVE_PROVIDER env var, defaults to "muapi"

    PROVIDERS               — list of supported provider names
    PROVIDER_LABELS         — display names
    IMAGE_MODELS            — canonical image model names
    IMAGE_MODEL_LABELS      — display names
    IMAGE_MODEL_CHOICES     — list of (slug, label) pairs for UI dropdowns

    COST_PER_IMAGE          — pricing map keyed by (provider, image_model, resolution)
    cost_per_image(provider, model, resolution) -> float

Errors:
    ProviderError, TransientError, CensorshipError, UploadError, is_censorship_error
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from .base import Provider
from .errors import (
    CensorshipError,
    ProviderError,
    TransientError,
    UploadError,
    is_censorship_error,
)
from .muapi import MuApiProvider
from .kie import KieProvider


PROVIDERS = ["muapi", "kie"]
PROVIDER_LABELS = {"muapi": "MuAPI", "kie": "Kie"}

IMAGE_MODELS = ["nano_banana_2", "gpt_image_2"]
IMAGE_MODEL_LABELS = {
    "nano_banana_2": "Nano Banana 2",
    "gpt_image_2": "GPT Image 2",
}
IMAGE_MODEL_CHOICES = [(m, IMAGE_MODEL_LABELS[m]) for m in IMAGE_MODELS]


# Pricing per image (USD). Keyed by (provider, image_model). Each value is a
# {resolution -> price} dict. Verified on each provider's pricing page.
# MuAPI gpt-image-2 is a flat rate regardless of resolution.
COST_PER_IMAGE: dict[tuple[str, str], dict[str, float]] = {
    ("muapi", "nano_banana_2"): {"1k": 0.06, "2k": 0.09, "4k": 0.12},
    ("muapi", "gpt_image_2"):   {"1k": 0.09, "2k": 0.09, "4k": 0.09},
    ("kie",   "nano_banana_2"): {"1k": 0.04, "2k": 0.06, "4k": 0.09},
    ("kie",   "gpt_image_2"):   {"1k": 0.03, "2k": 0.05, "4k": 0.08},
}


def cost_per_image(provider: str, model: str, resolution: str) -> float:
    table = COST_PER_IMAGE.get((provider, model)) or COST_PER_IMAGE[("muapi", "nano_banana_2")]
    return table.get(resolution, table.get("1k", 0.06))


def get_provider(name: str, on_log: Optional[Callable[[str, str], None]] = None) -> Provider:
    name = (name or "").lower().strip()
    if name == "muapi":
        p = MuApiProvider()
    elif name == "kie":
        p = KieProvider()
    else:
        raise ValueError(f"Unknown provider: {name!r}. Expected one of {PROVIDERS}.")
    if on_log is not None:
        p.set_logger(on_log)
    return p


def get_active_provider_name() -> str:
    name = (os.getenv("ACTIVE_PROVIDER") or "muapi").lower().strip()
    return name if name in PROVIDERS else "muapi"


def get_active_provider(on_log: Optional[Callable[[str, str], None]] = None) -> Provider:
    return get_provider(get_active_provider_name(), on_log=on_log)


__all__ = [
    "Provider",
    "MuApiProvider",
    "KieProvider",
    "get_provider",
    "get_active_provider",
    "get_active_provider_name",
    "PROVIDERS",
    "PROVIDER_LABELS",
    "IMAGE_MODELS",
    "IMAGE_MODEL_LABELS",
    "IMAGE_MODEL_CHOICES",
    "COST_PER_IMAGE",
    "cost_per_image",
    "ProviderError",
    "TransientError",
    "CensorshipError",
    "UploadError",
    "is_censorship_error",
]
