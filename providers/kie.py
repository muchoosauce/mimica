"""Kie.ai implementation of the Provider interface.

Wraps:
  - api.kie.ai/api/v1/jobs/createTask     (task creation)
  - api.kie.ai/api/v1/jobs/recordInfo     (task polling)
  - kieai.redpandaai.co/api/file-base64-upload  (file upload, separate domain)
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from .base import Provider
from .errors import (
    CensorshipError,
    ProviderError,
    UploadError,
    is_censorship_error,
)


load_dotenv()


_BASE_URL = "https://api.kie.ai/api/v1"
_UPLOAD_BASE64_URL = "https://kieai.redpandaai.co/api/file-base64-upload"
_UPLOAD_PATH = "ad-variator/uploads"

_POLL_TIMEOUT = 600  # Kie tasks can queue longer than MuAPI predictions
_POLL_INTERVAL = 4
_UPLOAD_LIMIT = 30 * 1024 * 1024  # base64 endpoint accepts up to ~32MB raw


_IMAGE_SLUGS = {
    "nano_banana_2": "nano-banana-2",
    "gpt_image_2":   "gpt-image-2-image-to-image",
}
# Per-model cap on input images. gpt-image-2-image-to-image documents max 16.
_IMAGE_INPUT_CAPS = {
    "nano_banana_2": 14,
    "gpt_image_2":   16,
}
_LLM_SLUG = "claude-sonnet-4-6"


def _normalize_resolution(res: str) -> str:
    return res.upper() if res and res[-1].lower() == "k" else (res or "1K")


class KieProvider(Provider):
    name = "kie"
    display_name = "Kie"

    def __init__(self) -> None:
        super().__init__()

    def _api_key(self) -> str:
        return (os.getenv("KIE_API_KEY") or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def _headers(self, json_body: bool = True) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._api_key()}"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

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
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        body = {
            "base64Data": f"data:{mime};base64,{b64}",
            "uploadPath": _UPLOAD_PATH,
            "fileName": path.name,
        }
        r = requests.post(
            _UPLOAD_BASE64_URL,
            headers=self._headers(json_body=True),
            json=body,
            timeout=180,
        )
        if r.status_code >= 400:
            raise UploadError(f"Kie upload failed ({r.status_code}): {r.text}")
        data = r.json()
        url = (
            data.get("url")
            or data.get("downloadUrl")
            or data.get("fileUrl")
            or (data.get("data") or {}).get("url")
            or (data.get("data") or {}).get("downloadUrl")
            or (data.get("data") or {}).get("fileUrl")
        )
        if not url:
            raise UploadError(f"Kie upload succeeded but no URL in response: {data}")
        return url

    def upload_image(self, path: Path) -> str:
        path = Path(path)
        self._log("INFO", f"Uploading reference image: {path.name}")
        with tempfile.TemporaryDirectory(prefix="advar_kie_") as tmpdir:
            tmp_path = Path(tmpdir)
            prepped = self._prepare_upload(path, tmp_path)
            if prepped != path:
                self._log(
                    "INFO",
                    f"Compressed {path.name} ({path.stat().st_size/1e6:.1f}MB → "
                    f"{prepped.stat().st_size/1e6:.1f}MB)",
                )
            url = self._retry_transient(self._do_upload, prepped, label=f"upload {path.name}")
        self._log("OK", f"Reference uploaded: {url}")
        return url

    # ── Task lifecycle ──────────────────────────────────────────────────────

    def _do_create_task(self, model_slug: str, input_payload: dict, label: str,
                        with_callback: bool = False) -> str:
        body: dict[str, Any] = {"model": model_slug, "input": input_payload}
        if with_callback:
            body["callBackUrl"] = ""
        r = requests.post(
            f"{_BASE_URL}/jobs/createTask",
            headers=self._headers(json_body=True),
            json=body,
            timeout=120,
        )
        if r.status_code >= 400:
            raise ProviderError(f"{label} createTask failed ({r.status_code}): {r.text}")
        data = r.json()
        if data.get("code") and data.get("code") != 200:
            raise ProviderError(f"{label} createTask error: {data}")
        task_id = (data.get("data") or {}).get("taskId") or data.get("taskId")
        if not task_id:
            raise ProviderError(f"{label}: no taskId in response: {data}")
        return task_id

    def _create_task(self, model_slug: str, input_payload: dict, label: str) -> str:
        return self._retry_transient(
            self._do_create_task, model_slug, input_payload, label, label=label
        )

    def _do_poll_task(self, task_id: str, label: str) -> dict:
        r = requests.get(
            f"{_BASE_URL}/jobs/recordInfo",
            headers=self._headers(json_body=False),
            params={"taskId": task_id},
            timeout=60,
        )
        if r.status_code >= 400:
            raise ProviderError(f"{label} poll failed ({r.status_code}): {r.text}")
        return r.json()

    def _poll_task(self, task_id: str, label: str) -> dict:
        start = time.time()
        while time.time() - start < _POLL_TIMEOUT:
            data = self._retry_transient(
                self._do_poll_task, task_id, label, label=f"{label} poll"
            )
            inner = data.get("data") or {}
            state = (inner.get("state") or "").lower()
            if state == "success":
                return inner
            if state == "fail":
                err = inner.get("failMsg") or inner.get("failCode") or data
                raise ProviderError(f"{label} task failed: {err}")
            time.sleep(_POLL_INTERVAL)
        raise ProviderError(f"Timeout ({_POLL_TIMEOUT}s) waiting for {label}")

    @staticmethod
    def _parse_result_urls(record: dict) -> list[str]:
        raw = record.get("resultJson")
        if not raw:
            return []
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return []
        else:
            parsed = raw
        urls = parsed.get("resultUrls") if isinstance(parsed, dict) else None
        return [u for u in (urls or []) if isinstance(u, str)]

    # ── Image input shaping ─────────────────────────────────────────────────

    def _image_input(self, model: str, prompt: str, image_urls: list[str],
                     resolution: str, aspect_ratio: str, output_format: str) -> dict:
        cap = _IMAGE_INPUT_CAPS.get(model)
        if cap and len(image_urls) > cap:
            raise ProviderError(
                f"Kie {model!r} accepts at most {cap} input images, got {len(image_urls)}."
            )
        common = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": _normalize_resolution(resolution),
        }
        if model == "nano_banana_2":
            return {
                **common,
                "image_input": list(image_urls),
                "output_format": output_format,
            }
        if model == "gpt_image_2":
            return {
                **common,
                "input_urls": list(image_urls),
            }
        raise ProviderError(f"Kie does not support image model {model!r}")

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
            raise ProviderError(f"Kie does not support image model {model!r}")
        input_payload = self._image_input(
            model, prompt, image_urls, resolution, aspect_ratio, output_format
        )
        try:
            task_id = self._create_task(slug, input_payload, label)
            record = self._poll_task(task_id, label)
        except ProviderError as e:
            if is_censorship_error(e):
                raise CensorshipError(str(e)) from e
            raise
        urls = self._parse_result_urls(record)
        if not urls:
            raise ProviderError(f"{label}: success without resultUrls in record: {record}")
        return urls[0]

    # NOTE: Kie's input schema for claude-sonnet-4-6 is not explicitly documented
    # in the public API reference. The shape below mirrors MuAPI's LLM payload
    # ({prompt, image_url, system_prompt}) wrapped in Kie's standard `input` field.
    # If Kie returns 400 on first run, log the body and adjust this single method.
    def _llm_input(self, prompt: str, image_url: str, system_prompt: str) -> dict:
        out: dict = {"prompt": prompt, "system_prompt": system_prompt}
        if image_url:
            out["image_url"] = image_url
        return out

    def call_llm(
        self,
        *,
        prompt: str,
        image_url: str = "",
        system_prompt: str,
        label: str = "llm",
    ) -> str:
        input_payload = self._llm_input(prompt, image_url, system_prompt)
        try:
            task_id = self._create_task(_LLM_SLUG, input_payload, label)
            record = self._poll_task(task_id, label)
        except ProviderError as e:
            if is_censorship_error(e):
                raise CensorshipError(str(e)) from e
            raise

        # Try resultJson first (image-style envelope), then known text fields.
        raw = record.get("resultJson")
        if isinstance(raw, str) and raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                for k in ("text", "content", "output", "result", "message", "completion"):
                    v = parsed.get(k)
                    if isinstance(v, str) and v:
                        return v
                if isinstance(parsed.get("choices"), list) and parsed["choices"]:
                    msg = parsed["choices"][0].get("message") or {}
                    if isinstance(msg.get("content"), str):
                        return msg["content"]
                return json.dumps(parsed)

        for k in ("text", "content", "output", "result", "message", "completion"):
            v = record.get(k)
            if isinstance(v, str) and v:
                return v
        raise ProviderError(f"{label}: could not extract text from Kie record: {record}")
