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

from .anthropic_llm import AnthropicLLM
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

IMAGE_MODELS = ["gpt_image_2", "nano_banana_2", "nano_banana_pro"]
IMAGE_MODEL_LABELS = {
    "nano_banana_2":   "Nano Banana 2",
    "nano_banana_pro": "Nano Banana Pro",
    "gpt_image_2":     "GPT Image 2",
}
IMAGE_MODEL_CHOICES = [(m, IMAGE_MODEL_LABELS[m]) for m in IMAGE_MODELS]

VIDEO_MODELS = ["kling_3_std", "kling_3_pro"]
VIDEO_MODEL_LABELS = {
    "kling_3_std": "Kling 3.0 Standard",
    "kling_3_pro": "Kling 3.0 Pro",
}
VIDEO_MODEL_CHOICES = [(m, VIDEO_MODEL_LABELS[m]) for m in VIDEO_MODELS]


# Pricing per image (USD). Keyed by (provider, image_model). Each value is a
# {resolution -> price} dict. Verified on each provider's pricing page.
# MuAPI gpt-image-2 is a flat rate regardless of resolution.
COST_PER_IMAGE: dict[tuple[str, str], dict[str, float]] = {
    ("muapi", "nano_banana_2"):   {"1k": 0.06, "2k": 0.09, "4k": 0.12},
    ("muapi", "nano_banana_pro"): {"1k": 0.10, "2k": 0.13, "4k": 0.18},
    ("muapi", "gpt_image_2"):     {"1k": 0.09, "2k": 0.09, "4k": 0.09},
    ("kie",   "nano_banana_2"):   {"1k": 0.04, "2k": 0.06, "4k": 0.09},
    ("kie",   "nano_banana_pro"): {"1k": 0.07, "2k": 0.10, "4k": 0.14},
    ("kie",   "gpt_image_2"):     {"1k": 0.03, "2k": 0.05, "4k": 0.08},
}


def cost_per_image(provider: str, model: str, resolution: str) -> float:
    table = COST_PER_IMAGE.get((provider, model)) or COST_PER_IMAGE[("muapi", "nano_banana_2")]
    return table.get(resolution, table.get("1k", 0.06))


# Pricing per second of generated video (USD). Kling tasks bill on output
# duration; the UI multiplies by clip length × clip count.
COST_PER_VIDEO_SECOND: dict[tuple[str, str], float] = {
    ("muapi", "kling_3_std"): 0.06,
    ("muapi", "kling_3_pro"): 0.18,
    ("kie",   "kling_3_std"): 0.04,
    ("kie",   "kling_3_pro"): 0.14,
}


def cost_per_video(provider: str, model: str, duration_s: int) -> float:
    rate = COST_PER_VIDEO_SECOND.get((provider, model), 0.10)
    return rate * max(1, duration_s)


def _attach_anthropic_llm_route(provider: Provider) -> Provider:
    """If ANTHROPIC_API_KEY is configured, replace `provider.call_llm` with a
    routed version that tries Anthropic direct first and falls back to the
    underlying provider's LLM endpoint when Anthropic itself fails.

    Image generation, video generation, and uploads are unaffected — those
    still hit MuAPI/Kie. Only LLM calls are rerouted.
    """
    if not AnthropicLLM.is_configured():
        return provider

    anth = AnthropicLLM()
    original_call_llm = provider.call_llm
    fallback_label = provider.display_name

    def routed_call_llm(*, prompt, image_url="", system_prompt, label="llm"):
        # Mirror logger so Anthropic INFO/WARN/ERR show up in the GUI's
        # activity panel via the underlying provider's _on_log.
        anth.set_logger(provider._on_log)
        try:
            provider._log("INFO", f"[{label}] LLM via Anthropic direct")
            return anth.call_llm(
                prompt=prompt, image_url=image_url,
                system_prompt=system_prompt, label=f"{label}-anth",
            )
        except CensorshipError:
            # Same content rules apply on MuAPI/Kie's claude wrapper, retrying
            # there is pointless. Surface the error to let the soften path run.
            raise
        except Exception as e:
            provider._log(
                "WARN",
                f"[{label}] Anthropic failed ({e.__class__.__name__}: "
                f"{str(e)[:120]}); falling back to {fallback_label}",
            )
            return original_call_llm(
                prompt=prompt, image_url=image_url,
                system_prompt=system_prompt, label=label,
            )

    provider.call_llm = routed_call_llm  # type: ignore[method-assign]
    return provider


def get_provider(name: str, on_log: Optional[Callable[[str, str], None]] = None) -> Provider:
    name = (name or "").lower().strip()
    if name == "muapi":
        p: Provider = MuApiProvider()
    elif name == "kie":
        p = KieProvider()
    else:
        raise ValueError(f"Unknown provider: {name!r}. Expected one of {PROVIDERS}.")
    p = _attach_anthropic_llm_route(p)
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
    "VIDEO_MODELS",
    "VIDEO_MODEL_LABELS",
    "VIDEO_MODEL_CHOICES",
    "COST_PER_IMAGE",
    "COST_PER_VIDEO_SECOND",
    "cost_per_image",
    "cost_per_video",
    "ProviderError",
    "TransientError",
    "CensorshipError",
    "UploadError",
    "is_censorship_error",
]
