"""GUI-side glue: pipelines, persistence, brand library."""
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv, set_key

_here = Path(__file__).resolve().parent.parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

import providers as pv
from providers import (
    CensorshipError,
    IMAGE_MODEL_CHOICES,
    IMAGE_MODEL_LABELS,
    IMAGE_MODELS,
    PROVIDER_LABELS,
    PROVIDERS,
    Provider,
    cost_per_image,
    get_active_provider,
    get_active_provider_name,
    get_provider,
    is_censorship_error,
)
from providers.prompts import (
    ADAPT_SYSTEM_PROMPT,
    generate_prompts as _gen_prompts,
    soften_prompt as _soften,
)

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _user_data_dir() -> Path:
    """Where to store .env, brands.json, brand images, default outputs.

    Frozen (.app inside /Applications): ~/Library/Application Support/Ad Variator
    Source mode: project root (so dev is unchanged).
    """
    if _is_frozen():
        d = Path.home() / "Library" / "Application Support" / "Ad Variator"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return _here


USER_DATA_DIR = _user_data_dir()
ENV_FILE = USER_DATA_DIR / ".env"

# In frozen mode, app.py loaded the env file early; this no-op call is a safety
# net for source-mode runs where .env sits next to the project root.
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# Pricing exposed for the cost-estimate widgets in the UI.
COST_PER_IMAGE = pv.COST_PER_IMAGE
RESOLUTIONS = ["1k", "2k", "4k"]
ASPECTS = ["1:1", "4:5", "9:16", "16:9", "3:2", "2:3", "3:4", "4:3"]
LANGUAGES = ["English", "French", "Spanish", "German", "Italian",
             "Portuguese", "Dutch", "Arabic"]
LANG_SLUG = {
    "English": "en", "French": "fr", "Spanish": "es", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Dutch": "nl", "Arabic": "ar",
}
AD_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

DEFAULT_IMAGE_MODEL = "nano_banana_2"

BRANDS_FILE = USER_DATA_DIR / "brands.json"
BRANDS_IMG_DIR = USER_DATA_DIR / "brands" / "images"


def _safe_name(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s.strip())
    return s.strip("_").lower() or "brand"


# ─── Provider / API key persistence ─────────────────────────────────────────

_PROVIDER_ENV_KEYS = {"muapi": "MUAPI_KEY", "kie": "KIE_API_KEY"}


def get_provider_key(provider: str) -> str:
    env_key = _PROVIDER_ENV_KEYS.get(provider)
    if not env_key:
        return ""
    return (os.getenv(env_key) or "").strip()


def save_provider_key(provider: str, key: str) -> None:
    env_key = _PROVIDER_ENV_KEYS.get(provider)
    if not env_key:
        raise ValueError(f"Unknown provider: {provider!r}")
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), env_key, key.strip())
    os.environ[env_key] = key.strip()


def save_active_provider(name: str) -> None:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name!r}")
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "ACTIVE_PROVIDER", name)
    os.environ["ACTIVE_PROVIDER"] = name


def is_active_provider_configured() -> bool:
    return bool(get_provider_key(get_active_provider_name()))


# Anthropic key for the Brand DNA Generator (separate from the active image provider).

def get_anthropic_key() -> str:
    return (os.getenv("ANTHROPIC_API_KEY") or "").strip()


def save_anthropic_key(key: str) -> None:
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "ANTHROPIC_API_KEY", key.strip())
    os.environ["ANTHROPIC_API_KEY"] = key.strip()


def is_anthropic_configured() -> bool:
    return bool(get_anthropic_key())


# Back-compat shims — call sites in pages.py still use these for the moment.
def save_api_key(key: str) -> None:
    save_provider_key("muapi", key)


def get_api_key() -> str:
    return get_provider_key("muapi")


# ─── Output dir ─────────────────────────────────────────────────────────────

if _is_frozen():
    DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "Ad Variator" / "outputs"
else:
    DEFAULT_OUTPUT_DIR = _here / "outputs"


def get_output_dir() -> Path:
    v = (os.getenv("OUTPUT_DIR") or "").strip()
    return Path(v).expanduser() if v else DEFAULT_OUTPUT_DIR


def save_output_dir(path: str) -> None:
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "OUTPUT_DIR", path.strip())
    os.environ["OUTPUT_DIR"] = path.strip()


# ─── Cost helpers ───────────────────────────────────────────────────────────

def cost_for_run(run: dict) -> float:
    params = run.get("params") or {}
    res = params.get("resolution", "1k")
    provider = params.get("provider", "muapi")
    image_model = params.get("image_model", DEFAULT_IMAGE_MODEL)
    if image_model.startswith("nano-banana"):
        image_model = "nano_banana_2"
    elif image_model.startswith("gpt-image"):
        image_model = "gpt_image_2"
    elif image_model not in IMAGE_MODELS:
        image_model = DEFAULT_IMAGE_MODEL
    done = sum(1 for r in run.get("results", []) if r.get("status") == "ok")
    return cost_per_image(provider, image_model, res) * done


def list_runs(root: Optional[Path] = None) -> list[dict]:
    root = root or get_output_dir()
    runs = []
    if not root.exists():
        return runs
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        report_file = d / "report.json"
        if not report_file.exists():
            continue
        try:
            data = json.loads(report_file.read_text())
        except Exception:
            continue
        images = (sorted(d.glob("variation_*.png")) + sorted(d.glob("variation_*.jpg"))
                  + sorted(d.glob("adapt_*.png")) + sorted(d.glob("adapt_*.jpg")))
        runs.append({
            "dir": d,
            "timestamp": data.get("timestamp", d.name),
            "type": data.get("type", "generate"),
            "reference": data.get("reference") or data.get("source_folder", ""),
            "reference_url": data.get("reference_url", ""),
            "brand": data.get("brand", ""),
            "params": data.get("params") or {},
            "results": data.get("results") or [],
            "images": images,
        })
    return runs


# ─── Brand DNA storage ──────────────────────────────────────────────────────

def _migrate_brand(b: dict) -> dict:
    if "product_images" not in b:
        single = b.get("product_image", "")
        b["product_images"] = [single] if single else []
    if "product_image" in b and not b["product_image"] and b["product_images"]:
        b["product_image"] = b["product_images"][0]
    b.setdefault("product_image", b["product_images"][0] if b["product_images"] else "")
    return b


def load_brands() -> dict[str, dict]:
    if not BRANDS_FILE.exists():
        return {}
    try:
        data = json.loads(BRANDS_FILE.read_text())
    except Exception:
        return {}
    return {k: _migrate_brand(v) for k, v in data.items()}


def save_brand(
    name: str,
    dna: str,
    product_image_sources: list[str],
    original_name: Optional[str] = None,
) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Brand name is required.")
    if not dna.strip():
        raise ValueError("Brand DNA text is required.")
    if not product_image_sources:
        raise ValueError("At least one product image is required.")

    BRANDS_IMG_DIR.mkdir(parents=True, exist_ok=True)
    slug = _safe_name(name)
    saved_paths: list[str] = []
    for i, src_str in enumerate(product_image_sources, 1):
        src = Path(src_str).expanduser().resolve()
        if not src.exists():
            raise ValueError(f"Product image not found: {src_str}")
        ext = src.suffix.lower() or ".png"
        dst = BRANDS_IMG_DIR / f"{slug}_{i:02d}{ext}"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        saved_paths.append(str(dst))

    brands = load_brands()
    if original_name and original_name != name and original_name in brands:
        old = brands[original_name]
        for old_p in old.get("product_images", []):
            try:
                p = Path(old_p)
                if p.exists() and p.parent == BRANDS_IMG_DIR and str(p) not in saved_paths:
                    p.unlink()
            except Exception:
                pass
        del brands[original_name]
    else:
        for old_p in brands.get(name, {}).get("product_images", []):
            try:
                p = Path(old_p)
                if p.exists() and p.parent == BRANDS_IMG_DIR and str(p) not in saved_paths:
                    p.unlink()
            except Exception:
                pass

    now = datetime.now().isoformat(timespec="seconds")
    brand = {
        "name": name,
        "dna": dna.strip(),
        "product_images": saved_paths,
        "product_image": saved_paths[0],
        "created_at": brands.get(name, {}).get("created_at", now),
        "updated_at": now,
    }
    brands[name] = brand
    BRANDS_FILE.write_text(json.dumps(brands, indent=2))
    return brand


def delete_brand(name: str):
    brands = load_brands()
    if name in brands:
        for pi in brands[name].get("product_images", []):
            p = Path(pi)
            if p.exists() and p.parent == BRANDS_IMG_DIR:
                try: p.unlink()
                except Exception: pass
        del brands[name]
        BRANDS_FILE.write_text(json.dumps(brands, indent=2))


def list_ads_in_folder(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AD_EXTS and not p.name.startswith(".")
    )


def parse_run_dt(ts: str) -> Optional[datetime]:
    try:
        return datetime.strptime(ts[:15], "%Y%m%d_%H%M%S")
    except Exception:
        return None


def _aspect_slug(a: str) -> str:
    return a.replace(":", "x").replace("/", "x")


# ─── Generate pipeline ──────────────────────────────────────────────────────

def run_generation(
    image_path: str,
    n: int,
    resolution: str,
    aspects: list[str],
    languages: list[str],
    workers: int,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    output_root: Optional[str] = None,
    *,
    image_model: str = DEFAULT_IMAGE_MODEL,
    provider_name: Optional[str] = None,
) -> Optional[Path]:
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    ref_path = Path(image_path).expanduser().resolve()
    if not ref_path.exists():
        on_log("ERR", f"File not found: {ref_path}")
        return None

    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    out_dir = base / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log("INFO", f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]}")

    aspects = aspects or ["1:1"]
    languages = languages or ["English"]

    try:
        ref_url = provider.upload_image(ref_path)
        if should_cancel():
            return out_dir

        prompts_by_lang: dict[str, list[str]] = {}
        for lang in languages:
            if should_cancel():
                return out_dir
            prompts_by_lang[lang] = _gen_prompts(provider, ref_url, n, language=lang)

        (out_dir / "prompts.txt").write_text(
            "\n\n".join(
                f"=== {lang} · Variation {i:02d} ===\n{p}"
                for lang, prompts in prompts_by_lang.items()
                for i, p in enumerate(prompts, 1)
            )
        )

        total = sum(len(p) for p in prompts_by_lang.values()) * len(aspects)
        on_log(
            "INFO",
            f"Generating {total} images "
            f"({n} variations × {len(languages)} lang × {len(aspects)} aspects, {workers} workers)..."
        )

        def one(idx, prompt, aspect, lang):
            bits = []
            if len(languages) > 1: bits.append(LANG_SLUG.get(lang, lang[:2].lower()))
            if len(aspects) > 1: bits.append(_aspect_slug(aspect))
            suffix = ("_" + "_".join(bits)) if bits else ""
            file_name = f"variation_{idx:02d}{suffix}.png"
            label = f"var_{idx:02d}{suffix}"
            provider._log("INFO", f"[{label}] generating ({lang} · {aspect})...")
            softened = False
            try:
                try:
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=[ref_url],
                        resolution=resolution, aspect_ratio=aspect, label=label,
                    )
                except CensorshipError:
                    provider._log("WARN", f"[{label}] blocked by content filter — rewriting prompt and retrying")
                    prompt = _soften(provider, prompt, ref_url)
                    softened = True
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=[ref_url],
                        resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
                    )
                dest = out_dir / file_name
                provider.download(img_url, dest)
                provider._log(
                    "OK",
                    f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
                )
                return {"index": idx, "aspect": aspect, "language": lang, "status": "ok",
                        "prompt": prompt, "image_url": img_url, "file": dest.name,
                        "softened": softened}
            except Exception as e:
                if is_censorship_error(e):
                    provider._log("ERR", f"[{label}] blocked by content filter (after retry). Try softer reference or brand copy.")
                else:
                    provider._log("ERR", f"[{label}] {e}")
                return {"index": idx, "aspect": aspect, "language": lang, "status": "error",
                        "prompt": prompt, "error": str(e)}

        jobs = [
            (i + 1, p, a, lang)
            for lang, prompts in prompts_by_lang.items()
            for i, p in enumerate(prompts)
            for a in aspects
        ]
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, *j) for j in jobs]
            for fut in as_completed(futures):
                if should_cancel():
                    break
                r = fut.result()
                results.append(r)
                on_result(r)

        results.sort(key=lambda r: (r.get("language", ""), r["index"], r.get("aspect", "")))
        report = {
            "type": "generate",
            "timestamp": ts,
            "reference": str(ref_path),
            "reference_url": ref_url,
            "params": {
                "iterations": n,
                "resolution": resolution,
                "aspects": aspects,
                "languages": languages,
                "aspect_ratio": aspects[0] if len(aspects) == 1 else ",".join(aspects),
                "language": languages[0] if len(languages) == 1 else ",".join(languages),
                "workers": workers,
                "provider": provider.name,
                "image_model": image_model,
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"Done: {ok}/{len(results)} succeeded.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


# ─── Adapt pipeline ─────────────────────────────────────────────────────────

def _generate_adapt_prompt(provider: Provider, ad_url: str, brand_dna: str,
                           product_count: int = 1, language: str = "English") -> str:
    if product_count <= 1:
        forms_note = "The brand has 1 target product form (reference image 2)."
    else:
        imgs = ", ".join(str(i) for i in range(2, 2 + product_count))
        forms_note = (
            f"The brand has {product_count} target product forms (reference images {imgs}). "
            f"If the source ad shows several product forms, map each to the closest target form; "
            f"if a source form has no target equivalent, use reference image 2 or omit the secondary product."
        )
    text = provider.call_llm(
        prompt=(
            f"Brand DNA:\n{brand_dna}\n\n"
            f"{forms_note}\n\n"
            f"Target language for every visible text, headline, body copy, tagline and CTA "
            f"inside the generated image: {language}. Write real literal copy in {language}, never placeholders.\n\n"
            "Reference ad is attached. Generate exactly ONE NanoBanana 2 prompt "
            "to recreate its composition for this brand, following all rules."
        ),
        image_url=ad_url,
        system_prompt=ADAPT_SYSTEM_PROMPT,
        label=f"LLM-adapt-{LANG_SLUG.get(language, language[:2].lower())}",
    )
    from providers.parsing import parse_prompts as _parse
    prompts = _parse(text)
    if prompts:
        return prompts[0]
    text = text.strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def _adapt_image(provider: Provider, image_model: str,
                 idx: int, prompt: str, ad_url: str, product_urls: list[str],
                 resolution: str, aspect: str, language: str, out_dir: Path,
                 source_name: str, multi_aspect: bool, multi_lang: bool) -> dict:
    bits = []
    if multi_lang: bits.append(LANG_SLUG.get(language, language[:2].lower()))
    if multi_aspect: bits.append(_aspect_slug(aspect))
    suffix = ("_" + "_".join(bits)) if bits else ""
    label = f"adapt_{idx:02d}{suffix}"
    provider._log("INFO", f"[{label}] generating ({source_name} · {language} · {aspect})...")

    inputs = [ad_url, *product_urls]
    softened = False
    try:
        try:
            img_url = provider.call_image(
                model=image_model, prompt=prompt, image_urls=inputs,
                resolution=resolution, aspect_ratio=aspect, label=label,
            )
        except CensorshipError:
            provider._log("WARN", f"[{label}] blocked by content filter — rewriting prompt and retrying")
            prompt = _soften(provider, prompt, ad_url)
            softened = True
            img_url = provider.call_image(
                model=image_model, prompt=prompt, image_urls=inputs,
                resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
            )
        dest = out_dir / f"adapt_{idx:02d}{suffix}.png"
        provider.download(img_url, dest)
        provider._log(
            "OK",
            f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
        )
        return {
            "index": idx, "aspect": aspect, "language": language, "status": "ok",
            "prompt": prompt, "image_url": img_url, "file": dest.name,
            "source": source_name, "softened": softened,
        }
    except Exception as e:
        if is_censorship_error(e):
            provider._log("ERR", f"[{label}] blocked by content filter (after retry). Simplify brand DNA copy or remove medical claims.")
        else:
            provider._log("ERR", f"[{label}] {e}")
        return {
            "index": idx, "aspect": aspect, "language": language, "status": "error",
            "prompt": prompt, "error": str(e), "source": source_name,
        }


def run_adapt(
    ad_paths: list[str],
    brand_name: str,
    resolution: str,
    aspects: list[str],
    languages: list[str],
    workers: int,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    output_root: Optional[str] = None,
    *,
    image_model: str = DEFAULT_IMAGE_MODEL,
    provider_name: Optional[str] = None,
) -> Optional[Path]:
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return None

    brands = load_brands()
    brand = brands.get(brand_name)
    if not brand:
        on_log("ERR", f"Brand '{brand_name}' not found.")
        return None

    product_paths_raw = brand.get("product_images") or ([brand.get("product_image")] if brand.get("product_image") else [])
    product_paths = [Path(p) for p in product_paths_raw if p and Path(p).exists()]
    if not product_paths:
        on_log("ERR", "Brand has no product image on disk.")
        return None

    ads: list[Path] = []
    for p in ad_paths:
        pp = Path(p).expanduser().resolve()
        if pp.is_file() and pp.suffix.lower() in AD_EXTS:
            ads.append(pp)
    if not ads:
        on_log("ERR", "No images to adapt.")
        return None

    aspects = aspects or ["1:1"]
    languages = languages or ["English"]
    multi_aspect = len(aspects) > 1
    multi_lang = len(languages) > 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    out_dir = base / f"{ts}_adapt_{_safe_name(brand_name)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log("INFO", f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]}")
    on_log(
        "INFO",
        f"Adapting {len(ads)} ads × {len(languages)} lang × {len(aspects)} aspect"
        f"{'s' if multi_aspect else ''} for '{brand_name}' ({workers} workers)",
    )

    try:
        on_log("INFO", f"Uploading {len(product_paths)} target product image(s)...")
        product_urls: list[str] = []
        for pp in product_paths:
            product_urls.append(provider.upload_image(pp))

        # Stage 1: upload each ad once.
        ad_urls: dict[int, str] = {}
        def upload_one(pair):
            idx, ad = pair
            if should_cancel(): return idx, None
            try:
                return idx, provider.upload_image(ad)
            except Exception as e:
                provider._log("ERR", f"[upload_{idx:02d}] {e}")
                return idx, None

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(upload_one, (i + 1, ad)) for i, ad in enumerate(ads)]):
                idx, url = fut.result()
                if url: ad_urls[idx] = url
        if should_cancel():
            on_log("WARN", "Cancelled during upload.")
            return out_dir

        # Stage 2: generate 1 prompt per (ad, language).
        prompts: dict[tuple[int, str], str] = {}
        def gen_prompt(triple):
            idx, ad_url, lang = triple
            if should_cancel(): return idx, lang, None
            try:
                return idx, lang, _generate_adapt_prompt(
                    provider, ad_url, brand["dna"],
                    product_count=len(product_urls), language=lang
                )
            except Exception as e:
                provider._log("ERR", f"[prompt_{idx:02d}_{LANG_SLUG.get(lang, lang[:2].lower())}] {e}")
                return idx, lang, None

        triples = [(i, ad_urls[i], lang) for i in ad_urls for lang in languages]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(gen_prompt, tr) for tr in triples]):
                idx, lang, prompt = fut.result()
                if prompt: prompts[(idx, lang)] = prompt
        if should_cancel():
            on_log("WARN", "Cancelled during prompt generation.")
            return out_dir

        # Stage 3: generate 1 image per (ad, language, aspect).
        jobs = []
        source_by_idx = {i + 1: ad.name for i, ad in enumerate(ads)}
        for (idx, lang), prompt in prompts.items():
            for aspect in aspects:
                jobs.append((idx, prompt, lang, aspect, source_by_idx[idx]))

        results = []
        def gen_img(job):
            idx, prompt, lang, aspect, source_name = job
            if should_cancel():
                return {"index": idx, "aspect": aspect, "language": lang,
                        "status": "cancelled", "source": source_name, "prompt": prompt}
            return _adapt_image(provider, image_model, idx, prompt, ad_urls[idx], product_urls,
                                resolution, aspect, lang, out_dir, source_name,
                                multi_aspect, multi_lang)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(gen_img, j) for j in jobs]):
                r = fut.result()
                results.append(r)
                on_result(r)

        for i, ad in enumerate(ads, 1):
            for lang in languages:
                if (i, lang) not in prompts:
                    for aspect in aspects:
                        results.append({
                            "index": i, "aspect": aspect, "language": lang,
                            "status": "error", "source": ad.name, "prompt": "",
                            "error": "prep failed (upload or LLM)",
                        })

        results.sort(key=lambda r: (r["index"], r.get("language", ""), r.get("aspect", "")))
        (out_dir / "prompts.txt").write_text(
            "\n\n".join(
                f"=== {source_by_idx[idx]} · {lang} ===\n{p}"
                for (idx, lang), p in sorted(prompts.items())
            )
        )

        report = {
            "type": "adapt",
            "timestamp": ts,
            "source_paths": [str(a) for a in ads],
            "brand": brand_name,
            "brand_dna": brand["dna"],
            "product_images": [str(p) for p in product_paths],
            "params": {
                "iterations": len(ads),
                "resolution": resolution,
                "aspects": aspects,
                "languages": languages,
                "aspect_ratio": aspects[0] if len(aspects) == 1 else ",".join(aspects),
                "language": languages[0] if len(languages) == 1 else ",".join(languages),
                "workers": workers,
                "provider": provider.name,
                "image_model": image_model,
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"Done: {ok}/{len(results)} adapted.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


# ─── Fix pipeline ───────────────────────────────────────────────────────────

FIX_SYSTEM_PROMPT = """You are a surgical image-fix prompt engineer for NanoBanana 2 (image-to-image edit mode).

Inputs at generation time:
- Reference image 1: the CURRENT output (contains a specific issue the user wants fixed)
- Reference images 2+: the brand's target product forms (one or several — pouch, stick, bottle, sachet, bottle cap, etc.)
- A user issue description (short text)

Your output is exactly ONE NanoBanana 2 prompt that performs a SURGICAL fix and nothing more.

Rules:
1. First character must be ^ (caret).
2. Explicitly reference "reference image 1" (the current output to preserve) and "reference images 2+" (target products).
3. ALL non-issue elements from reference image 1 must be preserved UNCHANGED: composition, layout, framing, crop, background, text zones, copy (wording, font, placement, color), typography, color palette, lighting, mood, all non-product props.
4. The ONLY modification is the specific issue described by the user:
   - If the issue is product size / scale / position / orientation → fix only that aspect of the product.
   - If the issue is product design / packaging / logo → re-render the product to match reference images 2+ exactly.
   - If the issue is text overlap / text clipping / text occlusion → reposition or resize ONLY the conflicting element so the text is legible; keep the text content identical.
   - If the issue is color drift on a specific element → fix only that element's color.
   - If the issue is a missing element → add only that element.
5. Do NOT restyle, do NOT redesign, do NOT rewrite copy, do NOT re-layout, do NOT change framing, do NOT swap background, do NOT alter any other element.
6. End every prompt with: "Preserve every element of reference image 1 exactly as shown, including all copy, typography, colors, background, and layout. The only change is the fix described above. Do not redesign, do not re-layout, do not re-word anything else."

CONTENT SAFETY (same rules as the adapt pipeline):
- No medical / clinical / hormonal / anatomical claims in copy (rewrite if present already).
- All figures fully dressed in modest everyday clothing; no bedrooms, no bathrooms, no intimate embraces; neutral settings (sofa, kitchen, studio, outdoors).

Output: exactly ONE prompt, nothing else."""


def _generate_fix_prompt(provider: Provider, brand_dna: str, issue: str,
                         product_count: int = 1, language: str = "English") -> str:
    if product_count <= 1:
        forms_note = "The brand has 1 target product form (reference image 2)."
    else:
        imgs = ", ".join(str(i) for i in range(2, 2 + product_count))
        forms_note = f"The brand has {product_count} target product forms (reference images {imgs})."
    text = provider.call_llm(
        prompt=(
            f"Brand DNA (for context only — do NOT re-apply to the image):\n{brand_dna}\n\n"
            f"{forms_note}\n\n"
            f"Copy language (already correct in reference image 1, keep as-is): {language}.\n\n"
            f"Issue to fix (user-reported):\n{issue.strip()}\n\n"
            "Generate ONE NanoBanana 2 prompt that performs the surgical fix described, "
            "following all rules. At generation time the image model will see: "
            "reference image 1 (the current output to preserve) and reference images 2+ "
            f"({product_count} target product form(s)). Refer to them in the prompt."
        ),
        image_url="",
        system_prompt=FIX_SYSTEM_PROMPT,
        label="LLM-fix",
    )
    text = text.strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def _next_fixed_path(original: Path) -> Path:
    stem, ext = original.stem, original.suffix or ".png"
    parent = original.parent
    if not (parent / f"{stem}_fixed{ext}").exists():
        return parent / f"{stem}_fixed{ext}"
    i = 2
    while (parent / f"{stem}_fixed_{i}{ext}").exists():
        i += 1
    return parent / f"{stem}_fixed_{i}{ext}"


def _render_fix(provider: Provider, image_model: str,
                prompt: str, img_url: str, product_urls: list[str],
                resolution: str, aspect: str, label: str) -> tuple[str, str, bool]:
    """Run the image model with content-filter softening. Returns (img_url, final_prompt, softened)."""
    inputs = [img_url, *product_urls]
    try:
        out_url = provider.call_image(
            model=image_model, prompt=prompt, image_urls=inputs,
            resolution=resolution, aspect_ratio=aspect, label=label,
        )
        return out_url, prompt, False
    except CensorshipError:
        provider._log("WARN", f"[{label}] blocked by content filter — softening and retrying")
        softer = _soften(provider, prompt, img_url)
        out_url = provider.call_image(
            model=image_model, prompt=softer, image_urls=inputs,
            resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
        )
        return out_url, softer, True


def run_fix(
    image_path: str,
    brand_name: str,
    issue: str,
    resolution: str,
    aspect: str,
    language: str,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    should_cancel: Callable[[], bool] = lambda: False,
    *,
    image_model: str = DEFAULT_IMAGE_MODEL,
    provider_name: Optional[str] = None,
) -> Optional[Path]:
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return None

    brands = load_brands()
    brand = brands.get(brand_name)
    if not brand:
        on_log("ERR", f"Brand '{brand_name}' not found.")
        return None
    product_paths = [Path(p) for p in brand.get("product_images", []) if Path(p).exists()]
    if not product_paths:
        on_log("ERR", "Brand has no product image on disk.")
        return None

    src = Path(image_path).expanduser().resolve()
    if not src.exists():
        on_log("ERR", f"Image not found: {src}")
        return None
    if not issue.strip():
        on_log("ERR", "Describe what needs to be fixed.")
        return None

    dest = _next_fixed_path(src)
    on_log("INFO", f"Fix → {dest.name}")
    on_log("INFO", f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]}")

    try:
        on_log("INFO", "Uploading current output...")
        img_url = provider.upload_image(src)
        if should_cancel(): return None

        on_log("INFO", f"Uploading {len(product_paths)} product image(s)...")
        product_urls = [provider.upload_image(pp) for pp in product_paths]
        if should_cancel(): return None

        on_log("INFO", "Generating fix prompt...")
        prompt = _generate_fix_prompt(
            provider, brand["dna"], issue,
            product_count=len(product_urls), language=language,
        )
        if should_cancel(): return None

        on_log("INFO", f"Rendering fix ({aspect} · {resolution})...")
        out_url, final_prompt, softened = _render_fix(
            provider, image_model, prompt, img_url, product_urls,
            resolution, aspect, "fix",
        )
        provider.download(out_url, dest)
        on_log("OK", f"Saved {dest.name}" + (" (after softening)" if softened else ""))
        on_result({
            "status": "ok", "file": dest.name, "path": str(dest),
            "source": src.name, "issue": issue, "prompt": final_prompt,
            "softened": softened, "provider": provider.name, "image_model": image_model,
        })
        return dest
    except Exception as e:
        on_log("ERR", str(e))
        on_result({"status": "error", "error": str(e), "source": src.name, "issue": issue})
        return None


def run_batch_fix(
    image_paths: list[str],
    brand_name: str,
    issue: str,
    resolution: str,
    aspect: str,
    language: str,
    workers: int,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    should_cancel: Callable[[], bool] = lambda: False,
    *,
    image_model: str = DEFAULT_IMAGE_MODEL,
    provider_name: Optional[str] = None,
) -> list[Path]:
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return []
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return []

    brands = load_brands()
    brand = brands.get(brand_name)
    if not brand:
        on_log("ERR", f"Brand '{brand_name}' not found.")
        return []
    product_paths = [Path(p) for p in brand.get("product_images", []) if Path(p).exists()]
    if not product_paths:
        on_log("ERR", "Brand has no product image on disk.")
        return []

    srcs: list[Path] = []
    for p in image_paths:
        pp = Path(p).expanduser().resolve()
        if pp.is_file() and pp.suffix.lower() in AD_EXTS:
            srcs.append(pp)
    if not srcs:
        on_log("ERR", "No valid images to fix.")
        return []
    if not issue.strip():
        on_log("ERR", "Describe what needs to be fixed.")
        return []

    on_log("INFO", f"Batch fix: {len(srcs)} images for '{brand_name}' ({workers} workers)")
    on_log("INFO", f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]}")

    try:
        on_log("INFO", f"Uploading {len(product_paths)} brand product image(s)...")
        product_urls = [provider.upload_image(pp) for pp in product_paths]
        if should_cancel(): return []

        def process(src: Path) -> dict:
            if should_cancel():
                return {"status": "cancelled", "source": src.name}
            dest = _next_fixed_path(src)
            label = f"fix_{src.stem}"
            try:
                img_url = provider.upload_image(src)
                if should_cancel():
                    return {"status": "cancelled", "source": src.name}
                prompt = _generate_fix_prompt(
                    provider, brand["dna"], issue,
                    product_count=len(product_urls), language=language,
                )
                if should_cancel():
                    return {"status": "cancelled", "source": src.name}
                out_url, final_prompt, softened = _render_fix(
                    provider, image_model, prompt, img_url, product_urls,
                    resolution, aspect, label,
                )
                provider.download(out_url, dest)
                provider._log(
                    "OK",
                    f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
                )
                return {
                    "status": "ok", "source": src.name, "file": dest.name,
                    "path": str(dest), "issue": issue, "prompt": final_prompt,
                    "softened": softened,
                }
            except Exception as e:
                provider._log("ERR", f"[{label}] {e}")
                return {"status": "error", "source": src.name, "error": str(e),
                        "issue": issue, "prompt": ""}

        results: list[Path] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(process, s) for s in srcs]):
                r = fut.result()
                on_result(r)
                if r.get("status") == "ok" and r.get("path"):
                    results.append(Path(r["path"]))

        ok = len(results)
        on_log("OK", f"Batch fix done: {ok}/{len(srcs)} fixed.")
        return results
    except Exception as e:
        on_log("ERR", str(e))
        return []
