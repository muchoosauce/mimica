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
    "connection reset", "timed out", "timeout", "temporary failure",
    "remote end closed",
    # Opaque upstream-server failures we've seen returned by MuAPI/Kie when
    # an internal job dies for no documented reason — almost always retryable.
    "unknown error", "internal server error", "internal error",
    "service unavailable", "bad gateway", "gateway timeout",
    # Anthropic-direct transients — overload, rate limits, 429/529.
    "overloaded", "rate limit", "rate_limit", "too many requests",
    "529", "apiconnectionerror", "apitimeouterror",
)

_CENSORSHIP_MARKERS = (
    "prohibited use", "content policy", "content policies", "filtered out",
    "violated", "may violate", "generative ai policy", "safety",
    "filtered because", "openai's content", "moderation", "blocked by",
)


def is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _TRANSIENT_MARKERS)


def is_censorship_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _CENSORSHIP_MARKERS)
