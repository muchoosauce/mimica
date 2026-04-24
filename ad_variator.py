#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

MUAPI_KEY = os.getenv("MUAPI_KEY")
BASE_URL = "https://api.muapi.ai/api/v1"
LLM_MODEL = "claude-sonnet-4-6"
IMAGE_MODEL = "nano-banana-2-edit"
POLL_TIMEOUT = 300
POLL_INTERVAL = 3

C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_RESET = "\033[0m"
C_DIM = "\033[2m"

SYSTEM_PROMPT = """You are an expert NanoBanana 2 prompt engineer for static ad production. When the user provides a reference ad image and specifies a number of iterations (N), you generate exactly N NanoBanana 2 prompts that produce N totally different ads — different layouts, different compositions, different product placements, different backgrounds — but all sharing the same graphic universe, tone, and visual identity as the reference.

Rules:
1. Product is sacred — Never change the product itself. Describe it with surgical precision in every prompt: shape, color, material, logo position, packaging.
2. Same graphic universe — All N prompts share: same lighting family, same color palette, same photographic style, same tone, same brand feel.
3. Totally different ads — Each variation is a new composition. Different layout, different product placement, different background, different text zone placement.
4. Copy-paste ready — Natural English, detailed and literal. No placeholders, no brackets inside prompts.
5. Every prompt must start with ^ — first character, no space before it.
6. Output is prompts only — no FINGERPRINT, no layout logic, no commentary, no headers, no numbering, no explanations. Just N prompts separated by blank lines.

Internal process (do not output): analyze product lock, graphic universe, original layout. Ensure each prompt differs on: Layout, Composition, Background, Text zone, Visual hierarchy.

Prompt structure (every prompt, in order):
1. ^ as first character
2. Product — exact description from reference
3. Layout & composition — position, framing, camera angle, crop
4. Background & environment
5. Lighting — same family as reference
6. Color & grade — same palette
7. Text zone — reserved negative space, never actual copy
8. End with: "No additional text, no extra logos, no watermarks, no brand names not present in the reference. Maintain exact product appearance from reference image."

CONTENT SAFETY (critical — the image model's content filter will reject and return nothing if the prompt violates Google Generative AI policy):
- No literal medical / clinical / therapeutic claims. Rewrite them into neutral lifestyle or wellness language.
  - "hormonal imbalance" → "everyday balance"; "clinically proven" → "expertly crafted"; "cure / treat / heal" → "support / help".
  - Disease or disorder names (migraine, depression, anxiety, menopause, PMS, insomnia, acne, diabetes, etc.) → generic moods ("tired", "foggy", "restless", "low energy").
- No before/after body transformations. Replace with mood or lifestyle shifts ("tired → bright"), NOT physical changes.
- No weight-loss language, no body measurements, no nudity, no suggestive posing, no anatomy close-ups.
- No names of real public figures. No political, religious, violent, weapon, or drug imagery. """


def log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": C_CYAN, "OK": C_GREEN, "WARN": C_YELLOW, "ERR": C_RED}
    color = colors.get(level, C_RESET)
    print(f"{C_DIM}[{ts}]{C_RESET} {color}{level:<4}{C_RESET} {msg}", flush=True)


def headers():
    return {"x-api-key": MUAPI_KEY}


def upload_image(path: Path) -> str:
    log("INFO", f"Uploading reference image: {path.name}")
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    with open(path, "rb") as f:
        files = {"file": (path.name, f, mime)}
        r = requests.post(f"{BASE_URL}/upload_file", headers=headers(), files=files, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Upload failed ({r.status_code}): {r.text}")
    data = r.json()
    url = (
        data.get("url")
        or data.get("file_url")
        or (data.get("data") or {}).get("url")
        or (data.get("result") or {}).get("url")
    )
    if not url:
        raise RuntimeError(f"Upload succeeded but no URL found in response: {data}")
    log("OK", f"Reference uploaded: {url}")
    return url


def extract_output(data: dict):
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


def poll_prediction(prediction_id: str, label: str):
    start = time.time()
    url = f"{BASE_URL}/predictions/{prediction_id}/result"
    while time.time() - start < POLL_TIMEOUT:
        r = requests.get(url, headers=headers(), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Poll failed ({r.status_code}): {r.text}")
        data = r.json()
        status = (data.get("status") or data.get("state") or "").lower()
        if status in ("succeeded", "success", "completed", "done"):
            out = extract_output(data)
            if out is None:
                raise RuntimeError(f"Completed but no output: {data}")
            return out
        if status in ("failed", "error", "canceled", "cancelled"):
            err = data.get("error") or data.get("message") or data
            raise RuntimeError(f"Prediction failed: {err}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Timeout ({POLL_TIMEOUT}s) waiting for {label}")


def call_prediction(model_id: str, payload: dict, label: str):
    url = f"{BASE_URL}/{model_id}"
    r = requests.post(url, headers={**headers(), "Content-Type": "application/json"},
                      json=payload, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"{label} request failed ({r.status_code}): {r.text}")
    data = r.json()
    status = (data.get("status") or data.get("state") or "").lower()
    if status in ("succeeded", "success", "completed", "done"):
        out = extract_output(data)
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
        return poll_prediction(pid, label)
    out = extract_output(data)
    if out is not None:
        return out
    raise RuntimeError(f"{label}: no id to poll and no output in response: {data}")


def generate_prompts(ref_url: str, n: int, language: str = "English") -> list[str]:
    log("INFO", f"Requesting {n} prompts from {LLM_MODEL} ({language})")
    lang_directive = (
        f"\n\nTarget language for every visible text, headline, tagline, body copy and CTA "
        f"inside the generated images: {language}. Write real literal copy in {language}, never placeholders."
    )
    payload = {
        "prompt": f"Reference ad image attached. Generate exactly {n} NanoBanana 2 prompts following all rules.{lang_directive}",
        "image_url": ref_url,
        "system_prompt": SYSTEM_PROMPT,
    }
    out = call_prediction(LLM_MODEL, payload, "LLM")
    text = _coerce_text(out)
    prompts = _parse_prompts(text)
    if len(prompts) < n:
        log("WARN", f"Only parsed {len(prompts)}/{n} prompts; retrying split")
        prompts = _fallback_split(text, n)
    if len(prompts) > n:
        prompts = prompts[:n]
    if len(prompts) == 0:
        raise RuntimeError(f"Could not parse any prompts from LLM output:\n{text}")
    log("OK", f"Parsed {len(prompts)} prompts")
    return prompts


def _coerce_text(out) -> str:
    if isinstance(out, str):
        return out
    if isinstance(out, list):
        parts = []
        for item in out:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
        return "\n".join(p for p in parts if p)
    if isinstance(out, dict):
        return out.get("text") or out.get("content") or json.dumps(out)
    return str(out)


def _parse_prompts(text: str) -> list[str]:
    matches = re.findall(r"\^[^\^]+", text, flags=re.DOTALL)
    return [m.strip() for m in matches if m.strip().startswith("^")]


def _fallback_split(text: str, n: int) -> list[str]:
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    prompts = []
    for c in chunks:
        if not c.startswith("^"):
            c = "^" + c.lstrip("^").lstrip()
        prompts.append(c)
    return prompts[:n]


def generate_image(idx: int, prompt: str, ref_url: str, resolution: str,
                   aspect: str, output_dir: Path) -> dict:
    label = f"var_{idx:02d}"
    log("INFO", f"[{label}] Generating image...")
    payload = {
        "prompt": prompt,
        "images_list": [ref_url],
        "resolution": resolution,
        "aspect_ratio": aspect,
        "output_format": "png",
    }
    try:
        out = call_prediction(IMAGE_MODEL, payload, label)
        img_url = _first_url(out)
        if not img_url:
            raise RuntimeError(f"No image URL in output: {out}")
        dest = output_dir / f"variation_{idx:02d}.png"
        _download(img_url, dest)
        log("OK", f"[{label}] Saved {dest.name}")
        return {"index": idx, "status": "ok", "prompt": prompt, "image_url": img_url, "file": dest.name}
    except Exception as e:
        log("ERR", f"[{label}] {e}")
        return {"index": idx, "status": "error", "prompt": prompt, "error": str(e)}


def _first_url(out):
    if isinstance(out, str):
        return out if out.startswith("http") else None
    if isinstance(out, list):
        for item in out:
            if isinstance(item, str) and item.startswith("http"):
                return item
            if isinstance(item, dict):
                u = item.get("url") or item.get("image_url") or item.get("output")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    if isinstance(out, dict):
        for k in ("url", "image_url", "output", "image"):
            v = out.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, list):
                r = _first_url(v)
                if r:
                    return r
    return None


def _download(url: str, dest: Path):
    r = requests.get(url, timeout=180, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)


def main():
    parser = argparse.ArgumentParser(description="Generate N ad variations from 1 reference image via MuAPI")
    parser.add_argument("-i", "--image", required=True, help="Path to reference ad image")
    parser.add_argument("-n", "--iterations", type=int, required=True, help="Number of variations (1-15)")
    parser.add_argument("-r", "--resolution", choices=["1k", "2k", "4k"], default="1k")
    parser.add_argument("-a", "--aspect", default="1:1", help="Aspect ratio (e.g. 1:1, 4:5, 9:16, 16:9)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers for image gen")
    args = parser.parse_args()

    if not MUAPI_KEY:
        log("ERR", "MUAPI_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    if not (1 <= args.iterations <= 15):
        log("ERR", "iterations must be between 1 and 15")
        sys.exit(1)

    ref_path = Path(args.image).expanduser().resolve()
    if not ref_path.exists():
        log("ERR", f"Reference image not found: {ref_path}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    log("INFO", f"Output directory: {out_dir}")

    try:
        ref_url = upload_image(ref_path)
    except Exception as e:
        log("ERR", f"Upload failed: {e}")
        sys.exit(1)

    try:
        prompts = generate_prompts(ref_url, args.iterations)
    except Exception as e:
        log("ERR", f"Prompt generation failed: {e}")
        sys.exit(1)

    prompts_file = out_dir / "prompts.txt"
    with open(prompts_file, "w") as f:
        for i, p in enumerate(prompts, 1):
            f.write(f"=== Variation {i:02d} ===\n{p}\n\n")
    log("OK", f"Wrote {prompts_file.name}")

    log("INFO", f"Generating {len(prompts)} images with {args.workers} workers...")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(generate_image, i + 1, p, ref_url, args.resolution, args.aspect, out_dir): i
            for i, p in enumerate(prompts)
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r["index"])

    report = {
        "timestamp": ts,
        "reference": str(ref_path),
        "reference_url": ref_url,
        "params": {
            "iterations": args.iterations,
            "resolution": args.resolution,
            "aspect_ratio": args.aspect,
            "workers": args.workers,
            "llm_model": LLM_MODEL,
            "image_model": IMAGE_MODEL,
        },
        "results": results,
    }
    report_file = out_dir / "report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count
    log("OK", f"Done: {ok_count} succeeded, {err_count} failed → {out_dir}")
    if err_count:
        sys.exit(2)


if __name__ == "__main__":
    main()
