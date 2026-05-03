"""Provider error types and helpers."""
from __future__ import annotations


class ProviderError(RuntimeError):
    """Base class for provider-side failures (HTTP errors, malformed responses)."""


class TransientError(ProviderError):
    """Retryable network/server hiccup (DNS, reset, 5xx, timeout)."""


class UploadError(ProviderError):
    """File upload failed."""


class CensorshipError(ProviderError):
    """Image content filter rejected the prompt. Caller may retry with a softened prompt."""


_TRANSIENT_MARKERS = (
    "nameresolutionerror", "max retries", "connection aborted",
    "connection reset", "timed out", "temporary failure", "remote end closed",
)

_CENSORSHIP_MARKERS = (
    "prohibited use", "content policy", "filtered out", "violated",
    "generative ai policy", "safety", "filtered because",
)


def is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _TRANSIENT_MARKERS)


def is_censorship_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _CENSORSHIP_MARKERS)
