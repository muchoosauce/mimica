"""MuAPI implementation of the Provider interface.

Wraps api.muapi.ai/api/v1: multipart upload, POST /{model_slug} for
predictions, GET /predictions/{id}/result for polling.
"""
from __future__ import annotations

import mimetypes
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from .base import Provider
from .errors import (
    CensorshipError,
    ProviderError,
    UploadError,
    is_censorship_error,
)
from .parsing import coerce_text, first_url


load_dotenv()


_BASE_URL = "https://api.muapi.ai/api/v1"
# Bumped from 300 to 600s to match Kie and give Claude vision calls breathing
# room when MuAPI's queue is backed up.
_POLL_TIMEOUT = 600
_POLL_INTERVAL = 3
_UPLOAD_LIMIT = 10 * 1024 * 1024  # MuAPI rejects >10MB uploads


_IMAGE_SLUGS = {
    "nano_banana_2":   "nano-banana-2-edit",
    "nano_banana_pro": "nano-banana-pro-edit",
    "gpt_image_2":     "gpt-image-2-image-to-image",
}
# Pure text-to-image variants (no input reference image). Used by the Twin
# workflow. Slugs follow MuAPI's convention: same family but no `-edit` /
# different mode suffix.
_T2I_IMAGE_SLUGS = {
    "nano_banana_2":   "nano-banana-2",
    "nano_banana_pro": "nano-banana-pro",
    "gpt_image_2":     "gpt-image-2-text-to-image",
}
# Per-model accepted aspect ratios. Used to remap unsupported user choices
# to the closest neighbour so the API doesn't reject the request.
_GPT_IMAGE_2_ASPECTS = {"auto", "1:1", "16:9", "9:16", "4:3", "3:4"}
_GPT_IMAGE_2_ASPECT_FALLBACK = {
    "4:5": "3:4",   # vertical feed → closest portrait
    "5:4": "4:3",
    "2:3": "3:4",
    "3:2": "4:3",
}
_VIDEO_SLUGS = {
    "kling_3_std": "kling-v3.0-standard-image-to-video",
    "kling_3_pro": "kling-v3.0-pro-image-to-video",
}
_LLM_SLUG = "claude-sonnet-4-6"


class MuApiProvider(Provider):
    name = "muapi"
    display_name = "MuAPI"

    def __init__(self) -> None:
        super().__init__()

    def _api_key(self) -> str:
        return (os.getenv("MUAPI_KEY") or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key()}

    # ── Upload ──────────────────────────────────────────────────────────────

    def _prepare_upload(self, path: Path, tmpdir: Path) -> Path:
        try:
            sz = path.stat().st_size
        except FileNotFoundError:
            return path
        if sz <= _UPLOAD_LIMIT:
            return path
        try:
            from PIL import Image
        except ImportError:
            return path
        try:
            im = Image.open(path)
        except Exception:
            return path
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        tmp = tmpdir / f"{path.stem}_{threading.get_ident()}.jpg"
        max_dim = 2400
        quality = 85
        for _ in range(6):
            w, h = im.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                im_s = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            else:
                im_s = im
            im_s.save(tmp, "JPEG", quality=quality, optimize=True)
            if tmp.stat().st_size <= _UPLOAD_LIMIT:
                return tmp
            quality = max(40, quality - 15)
            max_dim = max(1200, int(max_dim * 0.85))
        return tmp

    def _do_upload(self, path: Path) -> str:
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        with open(path, "rb") as f:
            files = {"file": (path.name, f, mime)}
            r = requests.post(
                f"{_BASE_URL}/upload_file",
                headers=self._headers(),
                files=files,
                timeout=120,
            )
        if r.status_code >= 400:
            raise UploadError(f"Upload failed ({r.status_code}): {r.text}")
        data = r.json()
        url = (
            data.get("url")
            or data.get("file_url")
            or (data.get("data") or {}).get("url")
            or (data.get("result") or {}).get("url")
        )
        if not url:
            raise UploadError(f"Upload succeeded but no URL found in response: {data}")
        return url

    def upload_image(self, path: Path) -> str:
        path = Path(path)
        self._log("INFO", f"Uploading reference image: {path.name}")
        with tempfile.TemporaryDirectory(prefix="advar_muapi_") as tmpdir:
            tmp_path = Path(tmpdir)
            prepped = self._prepare_upload(path, tmp_path)
            if prepped != path:
                self._log(
                    "INFO",
                    f"Compressed {path.name} ({path.stat().st_size/1e6:.1f}MB → "
                    f"{prepped.stat().st_size/1e6:.1f}MB) to fit 10MB limit",
                )
            url = self._retry_transient(self._do_upload, prepped, label=f"upload {path.name}")
        self._log("OK", f"Reference uploaded: {url}")
        return url

    # ── Predictions ─────────────────────────────────────────────────────────

    def _extract_output(self, data: dict):
        if not isinstance(data, dict):
            return None
        for key in ("output", "result", "outputs", "text", "response", "content", "message"):
            if key in data and data[key] is not None:
                return data[key]
        inner = data.get("data")
        if isinstance(inner, dict):
            for key in ("output", "result", "text", "response", "content", "message"):
                if key in inner and inner[key] is not None:
                    return inner[key]
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            if "content" in msg:
                return msg["content"]
        return None

    def _poll(self, prediction_id: str, label: str):
        start = time.time()
        url = f"{_BASE_URL}/predictions/{prediction_id}/result"
        while time.time() - start < _POLL_TIMEOUT:
            r = requests.get(url, headers=self._headers(), timeout=60)
            if r.status_code >= 400:
                raise ProviderError(f"Poll failed ({r.status_code}): {r.text}")
            data = r.json()
            status = (data.get("status") or data.get("state") or "").lower()
            if status in ("succeeded", "success", "completed", "done"):
                out = self._extract_output(data)
                if out is None:
                    raise ProviderError(f"Completed but no output: {data}")
                return out
            if status in ("failed", "error", "canceled", "cancelled"):
                err = data.get("error") or data.get("message") or data
                raise ProviderError(f"Prediction failed: {err}")
            time.sleep(_POLL_INTERVAL)
        raise ProviderError(f"Timeout ({_POLL_TIMEOUT}s) waiting for {label}")

    def _do_call_prediction(self, model_slug: str, payload: dict, label: str):
        url = f"{_BASE_URL}/{model_slug}"
        r = requests.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if r.status_code >= 400:
            raise ProviderError(f"{label} request failed ({r.status_code}): {r.text}")
        data = r.json()
        status = (data.get("status") or data.get("state") or "").lower()
        if status in ("succeeded", "success", "completed", "done"):
            out = self._extract_output(data)
            if out is not None:
                return out
        pid = (
            data.get("request_id")
            or data.get("id")
            or data.get("prediction_id")
            or (data.get("data") or {}).get("request_id")
            or (data.get("data") or {}).get("id")
        )
        if pid:
            return self._poll(pid, label)
        out = self._extract_output(data)
        if out is not None:
            return out
        raise ProviderError(f"{label}: no id to poll and no output in response: {data}")

    def _call_prediction(self, model_slug: str, payload: dict, label: str):
        try:
            return self._retry_transient(
                self._do_call_prediction, model_slug, payload, label, label=label
            )
        except ProviderError as e:
            if is_censorship_error(e):
                raise CensorshipError(str(e)) from e
            raise

    # ── Public API ──────────────────────────────────────────────────────────

    def call_image(
        self,
        *,
        model: str,
        prompt: str,
        image_urls: list[str],
        resolution: str,
        aspect_ratio: str,
        output_format: str = "png",
        label: str = "image",
    ) -> str:
        slug = _IMAGE_SLUGS.get(model)
        if not slug:
            raise ProviderError(f"MuAPI does not support image model {model!r}")
        # nano-banana-2-edit accepts lowercase ("1k"); gpt-image-2-image-to-image
        # accepts uppercase ("1K"). Cast per model to avoid 422.
        if model == "gpt_image_2":
            normalized_res = (
                resolution.upper() if resolution and resolution[-1].lower() == "k"
                else (resolution or "1K")
            )
        else:
            normalized_res = (
                resolution.lower() if resolution and resolution[-1].lower() == "k"
                else (resolution or "1k")
            )
        # Remap aspects the upstream model can't accept (see _GPT_IMAGE_2_*).
        normalized_aspect = aspect_ratio
        if model == "gpt_image_2" and aspect_ratio not in _GPT_IMAGE_2_ASPECTS:
            fallback = _GPT_IMAGE_2_ASPECT_FALLBACK.get(aspect_ratio)
            if fallback:
                self._log(
                    "WARN",
                    f"[{label}] GPT Image 2 doesn't accept {aspect_ratio} — using {fallback}",
                )
                normalized_aspect = fallback
            else:
                self._log(
                    "WARN",
                    f"[{label}] GPT Image 2 doesn't accept {aspect_ratio} — falling back to 1:1",
                )
                normalized_aspect = "1:1"
        payload = {
            "prompt": prompt,
            "images_list": list(image_urls),
            "resolution": normalized_res,
            "aspect_ratio": normalized_aspect,
            "output_format": output_format,
        }
        out = self._call_prediction(slug, payload, label)
        url = first_url(out)
        if not url:
            raise ProviderError(f"{label}: no image URL in output: {out}")
        return url

    def call_llm(
        self,
        *,
        prompt: str,
        image_url: str = "",
        system_prompt: str,
        label: str = "llm",
    ) -> str:
        payload: dict = {"prompt": prompt, "system_prompt": system_prompt}
        if image_url:
            payload["image_url"] = image_url
        out = self._call_prediction(_LLM_SLUG, payload, label)
        return coerce_text(out)

    def call_image_t2i(
        self,
        *,
        model: str,
        prompt: str,
        resolution: str,
        aspect_ratio: str,
        output_format: str = "png",
        label: str = "image-t2i",
    ) -> str:
        slug = _T2I_IMAGE_SLUGS.get(model)
        if not slug:
            raise ProviderError(f"MuAPI does not support text-to-image for model {model!r}")
        if model == "gpt_image_2":
            normalized_res = (
                resolution.upper() if resolution and resolution[-1].lower() == "k"
                else (resolution or "1K")
            )
        else:
            normalized_res = (
                resolution.lower() if resolution and resolution[-1].lower() == "k"
                else (resolution or "1k")
            )
        normalized_aspect = aspect_ratio
        if model == "gpt_image_2" and aspect_ratio not in _GPT_IMAGE_2_ASPECTS:
            fallback = _GPT_IMAGE_2_ASPECT_FALLBACK.get(aspect_ratio)
            if fallback:
                self._log(
                    "WARN",
                    f"[{label}] GPT Image 2 doesn't accept {aspect_ratio} — using {fallback}",
                )
                normalized_aspect = fallback
            else:
                self._log(
                    "WARN",
                    f"[{label}] GPT Image 2 doesn't accept {aspect_ratio} — falling back to 1:1",
                )
                normalized_aspect = "1:1"
        payload = {
            "prompt": prompt,
            "resolution": normalized_res,
            "aspect_ratio": normalized_aspect,
            "output_format": output_format,
        }
        out = self._call_prediction(slug, payload, label)
        url = first_url(out)
        if not url:
            raise ProviderError(f"{label}: no image URL in output: {out}")
        return url

    def call_video(
        self,
        *,
        model: str,
        prompt: str,
        image_url: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        sound: bool = False,
        label: str = "video",
    ) -> str:
        slug = _VIDEO_SLUGS.get(model)
        if not slug:
            raise ProviderError(f"MuAPI does not support video model {model!r}")
        # MuAPI's Kling 3 default is "sound on" in practice (despite WaveSpeed
        # docs claiming the opposite), so we always send the boolean explicitly.
        payload: dict = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
            "sound": bool(sound),
        }
        self._log("INFO", f"[{label}] sound: {'on' if sound else 'off'}")
        out = self._call_prediction(slug, payload, label)
        url = first_url(out)
        if not url:
            raise ProviderError(f"{label}: no video URL in output: {out}")
        return url
