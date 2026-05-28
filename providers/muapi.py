"""MuAPI implementation of the Provider interface.

Wraps api.muapi.ai/api/v1: multipart upload, POST /{model_slug} for
predictions, GET /predictions/{id}/result for polling.
"""
from __future__ import annotations

import mimetypes
import os
import tempfile
import threading
import socket
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
# Polling cadence for MuAPI prediction status. Lower = faster surface
# once the model is done, but more API calls. 1.5s is a good balance
# (was 3s — felt sluggish for 15-25s NB2 generations).
_POLL_INTERVAL = 1.5
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
    # NOTE: seedance_2 here is the IMAGE-TO-VIDEO slug, exposed in classic
    # Generate / Twin / B-Roll / Adapt flows that already produce a still and
    # animate it. The Swap Product page uses a *different* endpoint:
    # `seedance-v2.0-video-edit` (true video-to-video, preserves source faces +
    # motion + audio sync) — routed via _SWAP_VIDEO_SLUGS below.
    "seedance_2":  "seedance-v2.0-i2v",
    # Google Veo 3.1 — native 1080p, 24fps, 4/6/8s durations, contextual
    # audio synthesised from the prompt. Premium tier.
    "veo_3_1":     "veo3.1-image-to-video",
}
# Video-to-video edit endpoints. Distinct from _VIDEO_SLUGS because the payload
# shape is different (video_urls + images_list referenced via @image1 in the
# prompt). Verified on MuAPI's OpenAPI catalog: max 10MB / 15s source video,
# up to 9 reference images.
_SWAP_VIDEO_SLUGS = {
    "seedance_2": "seedance-v2.0-video-edit",
}
# Fallback aliases used when the primary slug above 404s. Tried automatically
# in order; first non-404 wins. Keep this list short to limit retry latency.
_VIDEO_SLUG_FALLBACKS = {
    "seedance_2": ["seedance-pro-i2v", "seedance-v1.5-pro-i2v"],
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

    def upload_video(self, path: Path) -> str:
        """Upload a video file. Skips the PIL-based image compression path.

        MuAPI rejects uploads >10MB and Seedance v2 video-edit additionally
        rejects videos >15s — we surface a clear, actionable error rather than
        passing those constraints through to a generic 4xx from the API.
        """
        path = Path(path)
        if not path.exists():
            raise UploadError(f"Video file not found: {path}")
        sz = path.stat().st_size
        if sz > _UPLOAD_LIMIT:
            raise UploadError(
                f"Video {path.name} is {sz/1e6:.1f}MB, MuAPI's upload limit is "
                f"{_UPLOAD_LIMIT/1e6:.0f}MB. Trim it (e.g. `ffmpeg -i in.mp4 -t 15 -c:v libx264 "
                f"-crf 28 -preset fast out.mp4`) and retry."
            )
        self._log("INFO", f"Uploading source video: {path.name} ({sz/1e6:.1f}MB)")
        url = self._retry_transient(self._do_upload, path, label=f"upload {path.name}")
        self._log("OK", f"Source video uploaded: {url}")
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
        # Swallow transient network errors at the poll layer (Windows DNS
        # flakes). See forge/providers/muapi.py for the full rationale.
        _POLL_NET_FAILS = 5
        consecutive_net_fails = 0
        while time.time() - start < _POLL_TIMEOUT:
            try:
                r = requests.get(url, headers=self._headers(), timeout=60)
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                socket.gaierror,
                ConnectionResetError,
            ) as e:
                consecutive_net_fails += 1
                if consecutive_net_fails >= _POLL_NET_FAILS:
                    raise ProviderError(
                        f"Poll network error (gave up after "
                        f"{consecutive_net_fails} retries): {e}"
                    )
                self._log("WARN", f"[{label}] poll network hiccup, retrying in {_POLL_INTERVAL}s ({consecutive_net_fails}/{_POLL_NET_FAILS})")
                time.sleep(_POLL_INTERVAL)
                continue
            consecutive_net_fails = 0
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
        product_reference_urls: list[str] = (),
        label: str = "video",
        resolution: str = "",
    ) -> str:
        primary = _VIDEO_SLUGS.get(model)
        if not primary:
            raise ProviderError(f"MuAPI does not support video model {model!r}")
        slugs_to_try = [primary, *_VIDEO_SLUG_FALLBACKS.get(model, [])]

        is_kling = model.startswith("kling_")
        is_seedance = model.startswith("seedance_")
        is_veo = model.startswith("veo_")

        # MuAPI's veo3.1-image-to-video endpoint is fixed at 8 seconds.
        # Anything else returns a 422 literal_error. Force to 8 and log.
        if is_veo:
            d = int(duration)
            if d != 8:
                self._log("INFO", f"[{label}] duration {d}s forced to 8s (Veo 3.1 i2v on MuAPI is fixed at 8s).")
            duration = 8

        # MuAPI's Kling 3 default is "sound on" in practice (despite WaveSpeed
        # docs claiming the opposite), so we always send the boolean explicitly.
        payload: dict = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
            "sound": bool(sound),
        }
        # Pass through an explicit resolution only when the caller asked for
        # one — keeps the existing default behavior on every other workflow.
        if resolution:
            payload["resolution"] = resolution
            self._log("INFO", f"[{label}] resolution: {resolution}")
        self._log("INFO", f"[{label}] sound: {'on' if sound else 'off'}")

        # Product reference locking via Kling's `kling_elements`. Only Kling 3
        # supports this. Seedance has its own multi-image reference path which
        # we don't wire yet (TODO when MuAPI documents it).
        #
        # Empirically (May 2026), Kling 3.0 Standard rejects `kling_elements`
        # with "Unknown error" mid-render whenever the source frame's element
        # is small (e.g. selfie holding a bottle) and the refs are isolated
        # studio shots — the matcher can't track the element and the job dies.
        # We need at least 2 distinct refs and we fall back to no-locking on
        # any mid-render failure further down (see retry block below).
        refs = list(product_reference_urls or [])
        used_locking = False
        if refs and is_kling:
            if len(refs) > 4:
                refs = refs[:4]
            if len(refs) < 2:
                # Kling demands 2-4 element refs; with only 1 unique ref the
                # matcher fails predictably. Skip locking instead of duplicating
                # the same URL twice (which still fails per repro tests).
                self._log(
                    "WARN",
                    f"[{label}] product reference locking: skipped (only {len(refs)} ref, "
                    "need 2 distinct refs for Kling element tracking)",
                )
            else:
                payload["kling_elements"] = [{
                    "name": "product",
                    "description": (
                        "the product with all its visible packaging, logo, "
                        "label text and printed characters preserved exactly"
                    ),
                    "element_input_urls": refs,
                }]
                if "@product" not in payload["prompt"]:
                    payload["prompt"] = payload["prompt"].rstrip() + " @product"
                used_locking = True
                self._log(
                    "INFO",
                    f"[{label}] product reference locking: on ({len(refs)} refs)",
                )
        elif refs and is_seedance:
            self._log("INFO", f"[{label}] product reference: ignored (Seedance lock not yet wired)")

        # Strip orphaned @product tokens whenever locking didn't end up on —
        # Kling fails with an opaque "Unknown error" if the prompt references
        # an element that has no kling_elements entry to resolve it.
        if not used_locking and "@product" in payload["prompt"]:
            cleaned = payload["prompt"].replace(" @product", "").replace("@product", "").rstrip()
            payload["prompt"] = cleaned

        # Visibility: log the prompt + payload shape before submit so failures
        # can be debugged without re-running.
        self._log(
            "INFO",
            f"[{label}] payload: model={primary} duration={int(duration)}s "
            f"aspect={aspect_ratio} sound={'on' if sound else 'off'} "
            f"locking={'on' if used_locking else 'off'}",
        )
        self._log("INFO", f"[{label}] prompt: {payload['prompt'][:240]}…")

        out = None
        last_err: Optional[Exception] = None
        for i, slug in enumerate(slugs_to_try):
            attempt_label = label if i == 0 else f"{label}-fallback{i}"
            try:
                out = self._call_prediction(slug, payload, attempt_label)
                if i > 0:
                    self._log("INFO", f"[{label}] succeeded with fallback slug {slug!r}")
                break
            except ProviderError as e:
                msg = str(e)
                # 1) If kling_elements caused the failure — either rejected at
                #    submit (422) or crashed mid-render with the opaque
                #    "Unknown error" / "Poll failed" we keep seeing on Kling 3 —
                #    retry once stripped on the same slug. Better to ship a
                #    clip without locking than to fail the whole job.
                locking_failure = used_locking and (
                    "422" in msg
                    or "kling_elements" in msg
                    or "extra" in msg.lower()
                    or "unknown error" in msg.lower()
                    or "poll failed" in msg.lower()
                    or "prediction failed" in msg.lower()
                )
                if locking_failure:
                    self._log(
                        "WARN",
                        f"[{attempt_label}] Kling rejected element locking ({msg[:160]}); "
                        "retrying without product reference locking",
                    )
                    payload.pop("kling_elements", None)
                    payload["prompt"] = payload["prompt"].replace(" @product", "").rstrip()
                    used_locking = False
                    try:
                        out = self._call_prediction(slug, payload, attempt_label)
                        break
                    except ProviderError as e2:
                        last_err = e2
                        msg = str(e2)
                # 2) If the slug itself doesn't exist (404 / unknown model),
                #    try the next fallback.
                if "404" in msg or "not found" in msg.lower() or "unknown model" in msg.lower():
                    self._log(
                        "WARN",
                        f"[{attempt_label}] slug {slug!r} returned 404; trying next fallback",
                    )
                    last_err = e
                    continue
                # 3) Anything else: bail.
                raise
        if out is None:
            raise last_err or ProviderError(f"{label}: all slugs failed for model {model!r}")
        url = first_url(out)
        if not url:
            raise ProviderError(f"{label}: no video URL in output: {out}")
        return url

    def call_swap_video(
        self,
        *,
        model: str,
        prompt: str,
        source_video_url: str,
        product_image_url: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        quality: str = "basic",
        label: str = "swap",
    ) -> str:
        """Video-to-video product swap via Seedance v2.0 video-edit.

        Payload shape per MuAPI's OpenAPI:
          - video_urls: [<source>] (exactly 1, ≤10MB, ≤15s)
          - images_list: [<product>] (referenced as @image1 in the prompt)
          - prompt: must contain @image1 telling the model what to replace with
          - duration: 4-15s
          - aspect_ratio, quality: optional

        Faces, motion, lighting and audio sync of the source video are preserved
        — only the targeted product is replaced. Lip-sync stays intact gratuitously
        because the visual side of the source is preserved verbatim.
        """
        slug = _SWAP_VIDEO_SLUGS.get(model)
        if not slug:
            raise ProviderError(
                f"Model {model!r} has no video-edit endpoint. "
                f"Supported swap models: {sorted(_SWAP_VIDEO_SLUGS)}"
            )
        if "@image1" not in prompt:
            # Defensive: if Vision didn't produce a brief that references the
            # product image, the model may regenerate the source product instead
            # of swapping it. Append a minimal hint so the call still produces
            # a meaningful result rather than silently no-oping.
            prompt = prompt.rstrip() + " (replace the held product with @image1)"
            self._log("WARN", f"[{label}] prompt missing @image1; appended fallback hint")

        # Seedance accepts 4..15. Clamp to keep the API from 422-ing.
        duration = max(4, min(15, int(duration)))

        payload: dict = {
            "prompt": prompt,
            "video_urls": [source_video_url],
            "images_list": [product_image_url],
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "quality": quality,
        }
        self._log(
            "INFO",
            f"[{label}] Seedance v2 video-edit · {duration}s · {aspect_ratio} · quality={quality}",
        )
        out = self._call_prediction(slug, payload, label)
        url = first_url(out)
        if not url:
            raise ProviderError(f"{label}: no video URL in swap output: {out}")
        return url
