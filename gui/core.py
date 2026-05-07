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
    VIDEO_MODEL_CHOICES,
    VIDEO_MODEL_LABELS,
    VIDEO_MODELS,
    cost_per_image,
    cost_per_video,
    get_active_provider,
    get_active_provider_name,
    get_provider,
    is_censorship_error,
)
from providers.prompts import (
    ADAPT_SYSTEM_PROMPT,
    FUNNEL_LABELS,
    FUNNEL_SEGMENTS,
    FUNNEL_STAGES,
    FUNNEL_SYSTEM_PROMPTS,
    generate_broll_image_prompts as _gen_broll_img_prompts,
    generate_broll_video_prompt as _gen_broll_vid_prompt,
    generate_funnel_creatives as _gen_funnel_creatives,
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

DEFAULT_IMAGE_MODEL = "gpt_image_2"

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
    provider = params.get("provider", "muapi")
    done = sum(1 for r in run.get("results", []) if r.get("status") == "ok")

    if run.get("type") == "broll_videos":
        video_model = params.get("video_model", "kling_3_std")
        duration = int(params.get("duration", 5) or 5)
        return cost_per_video(provider, video_model, duration) * done

    res = params.get("resolution", "1k")
    image_model = params.get("image_model", DEFAULT_IMAGE_MODEL)
    if image_model == "nano-banana-2":
        image_model = "nano_banana_2"
    elif image_model == "nano-banana-pro":
        image_model = "nano_banana_pro"
    elif image_model.startswith("gpt-image"):
        image_model = "gpt_image_2"
    elif image_model not in IMAGE_MODELS:
        image_model = DEFAULT_IMAGE_MODEL
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
                  + sorted(d.glob("adapt_*.png")) + sorted(d.glob("adapt_*.jpg"))
                  + sorted(d.glob("broll_*.png")) + sorted(d.glob("broll_*.jpg"))
                  + sorted(d.glob("broll_*.mp4"))
                  + sorted(d.glob("funnel_*.png")) + sorted(d.glob("funnel_*.jpg")))
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

def _heal_path(p: str) -> str:
    """If a product image path is stale (project moved), try to find it by
    filename inside the current BRANDS_IMG_DIR."""
    if not p:
        return p
    pp = Path(p)
    if pp.exists():
        return p
    candidate = BRANDS_IMG_DIR / pp.name
    if candidate.exists():
        return str(candidate)
    return p


def _migrate_brand(b: dict) -> dict:
    if "product_images" not in b:
        single = b.get("product_image", "")
        b["product_images"] = [single] if single else []
    b["product_images"] = [_heal_path(p) for p in b["product_images"]]
    if "product_image" in b and not b["product_image"] and b["product_images"]:
        b["product_image"] = b["product_images"][0]
    b["product_image"] = _heal_path(b.get("product_image", ""))
    if not b.get("product_image") and b["product_images"]:
        b["product_image"] = b["product_images"][0]
    return b


def load_brands() -> dict[str, dict]:
    if not BRANDS_FILE.exists():
        return {}
    try:
        data = json.loads(BRANDS_FILE.read_text())
    except Exception:
        return {}
    healed = {k: _migrate_brand(v) for k, v in data.items()}
    # Persist the healed paths so we don't redo this on every load.
    if json.dumps(healed, sort_keys=True) != json.dumps(data, sort_keys=True):
        try:
            BRANDS_FILE.write_text(json.dumps(healed, indent=2))
        except Exception:
            pass
    return healed


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


# ─── B-Roll pipeline ────────────────────────────────────────────────────────

DEFAULT_VIDEO_MODEL = "kling_3_std"
BROLL_CATEGORIES = ["usage", "presentation", "ecu", "in_action"]
BROLL_CATEGORY_LABELS = {
    "usage": "USAGE",
    "presentation": "PRESENTATION",
    "ecu": "ECU",
    "in_action": "IN-ACTION",
}


def run_broll_images(
    brand_name: str,
    specifications: str,
    counts: dict[str, int],
    resolution: str,
    aspect: str,
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
    """Phase 1 of the B-Roll workflow: generate N still images.

    Writes a report.json with type="broll_images" and an entry per image.
    The report is the handoff to phase 2 (animation): each ok entry includes
    the image_url, prompt, and category, ready to be replayed.
    """
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

    total = sum(max(0, int(counts.get(c, 0))) for c in BROLL_CATEGORIES)
    if total <= 0:
        on_log("ERR", "Pick at least one B-roll category count > 0.")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    out_dir = base / f"{ts}_broll_{_safe_name(brand_name)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log("INFO", f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]}")
    breakdown = ", ".join(
        f"{counts.get(c, 0)} {BROLL_CATEGORY_LABELS[c]}" for c in BROLL_CATEGORIES if counts.get(c, 0)
    )
    on_log("INFO", f"Generating {total} B-roll images ({breakdown}, {workers} workers)")

    try:
        on_log("INFO", f"Uploading {len(product_paths)} product reference image(s)...")
        product_urls = [provider.upload_image(pp) for pp in product_paths]
        if should_cancel():
            on_log("WARN", "Cancelled during upload.")
            return out_dir

        on_log("INFO", "Generating B-roll prompts...")
        prompts = _gen_broll_img_prompts(
            provider,
            brand_dna=brand["dna"],
            specifications=specifications,
            counts=counts,
            reference_image_url=product_urls[0],
        )
        if should_cancel():
            on_log("WARN", "Cancelled after prompt generation.")
            return out_dir

        # Tag each prompt with its category so the UI can group by section.
        category_order: list[str] = []
        for c in BROLL_CATEGORIES:
            category_order.extend([c] * max(0, int(counts.get(c, 0))))
        # Defensive: align lengths in case the LLM under/over-produced.
        while len(category_order) < len(prompts):
            category_order.append("usage")
        category_order = category_order[: len(prompts)]

        (out_dir / "prompts.txt").write_text(
            "\n\n".join(
                f"=== {BROLL_CATEGORY_LABELS[cat]} · {i:02d} ===\n{p}"
                for i, (p, cat) in enumerate(zip(prompts, category_order), 1)
            )
        )

        def one(idx: int, prompt: str, category: str) -> dict:
            label = f"broll_{idx:02d}_{category}"
            provider._log("INFO", f"[{label}] generating...")
            softened = False
            try:
                try:
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=product_urls,
                        resolution=resolution, aspect_ratio=aspect, label=label,
                    )
                except CensorshipError:
                    provider._log("WARN", f"[{label}] blocked by content filter — softening")
                    prompt = _soften(provider, prompt, product_urls[0])
                    softened = True
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=product_urls,
                        resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
                    )
                file_name = f"broll_{idx:02d}_{category}.png"
                dest = out_dir / file_name
                provider.download(img_url, dest)
                provider._log(
                    "OK",
                    f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
                )
                return {
                    "index": idx, "category": category, "status": "ok",
                    "prompt": prompt, "image_url": img_url, "file": dest.name,
                    "softened": softened,
                }
            except Exception as e:
                if is_censorship_error(e):
                    provider._log("ERR", f"[{label}] blocked by content filter (after retry).")
                else:
                    provider._log("ERR", f"[{label}] {e}")
                return {
                    "index": idx, "category": category, "status": "error",
                    "prompt": prompt, "error": str(e),
                }

        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [(i + 1, p, c) for i, (p, c) in enumerate(zip(prompts, category_order))]
            for fut in as_completed([pool.submit(one, *j) for j in jobs]):
                if should_cancel():
                    break
                r = fut.result()
                results.append(r)
                on_result(r)

        results.sort(key=lambda r: r["index"])
        report = {
            "type": "broll_images",
            "timestamp": ts,
            "brand": brand_name,
            "brand_dna": brand["dna"],
            "specifications": specifications,
            "product_images": [str(p) for p in product_paths],
            "counts": {c: int(counts.get(c, 0)) for c in BROLL_CATEGORIES},
            "params": {
                "resolution": resolution,
                "aspects": [aspect],
                "aspect_ratio": aspect,
                "workers": workers,
                "provider": provider.name,
                "image_model": image_model,
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"B-roll images done: {ok}/{len(results)} succeeded.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


def run_broll_videos(
    images_run_dir: str,
    approved_indexes: list[int],
    duration: int,
    aspect: str,
    workers: int,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    *,
    video_model: str = DEFAULT_VIDEO_MODEL,
    provider_name: Optional[str] = None,
    sound: bool = False,
) -> Optional[Path]:
    """Phase 2 of the B-Roll workflow: animate approved images into clips.

    Reads images_run_dir/report.json (must be a broll_images run), animates
    every approved image via LLM2 + Kling 3, writes results into a sibling
    directory named <ts>_broll_videos_<brand> alongside the images run.
    """
    images_dir = Path(images_run_dir).expanduser().resolve()
    report_path = images_dir / "report.json"
    if not report_path.exists():
        on_log("ERR", f"No report.json found in {images_dir}")
        return None

    try:
        img_report = json.loads(report_path.read_text())
    except Exception as e:
        on_log("ERR", f"Could not read images report: {e}")
        return None

    if img_report.get("type") != "broll_images":
        on_log("ERR", f"Run at {images_dir} is not a B-roll images run.")
        return None

    brand_name = img_report.get("brand") or ""
    brand_dna = img_report.get("brand_dna") or ""
    img_results = img_report.get("results") or []
    by_index = {r["index"]: r for r in img_results if r.get("status") == "ok"}

    approved: list[dict] = []
    for idx in approved_indexes:
        if idx in by_index:
            entry = by_index[idx]
            local = images_dir / entry.get("file", "")
            if local.exists():
                approved.append({**entry, "_local_path": local})
    if not approved:
        on_log("ERR", "No approved images found to animate.")
        return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None
    if video_model not in VIDEO_MODELS:
        on_log("ERR", f"Unknown video model: {video_model!r}")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = images_dir.parent / f"{ts}_broll_videos_{_safe_name(brand_name) or 'brand'}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log(
        "INFO",
        f"Provider: {provider.display_name} · Model: {VIDEO_MODEL_LABELS[video_model]} · "
        f"{len(approved)} approved clips · {duration}s · {aspect}",
    )

    try:
        # Re-upload approved local images so the video provider has a fresh
        # URL it can read (image URLs in the images report may be transient).
        on_log("INFO", "Uploading approved images to video provider...")
        upload_urls: dict[int, str] = {}

        def upload_one(entry: dict) -> tuple[int, Optional[str]]:
            if should_cancel():
                return entry["index"], None
            try:
                return entry["index"], provider.upload_image(entry["_local_path"])
            except Exception as e:
                provider._log("ERR", f"[broll_v_{entry['index']:02d}] upload {e}")
                return entry["index"], None

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(upload_one, e) for e in approved]):
                idx, url = fut.result()
                if url:
                    upload_urls[idx] = url
        if should_cancel():
            on_log("WARN", "Cancelled during upload.")
            return out_dir

        def animate(entry: dict) -> dict:
            idx = entry["index"]
            category = entry.get("category", "")
            label = f"broll_v_{idx:02d}_{category}"
            ref_url = upload_urls.get(idx)
            if not ref_url:
                return {
                    "index": idx, "category": category, "status": "error",
                    "error": "upload failed", "source_file": entry.get("file"),
                }
            try:
                provider._log("INFO", f"[{label}] generating animation prompt...")
                vid_prompt = _gen_broll_vid_prompt(provider, brand_dna, ref_url)
                if should_cancel():
                    return {"index": idx, "category": category, "status": "cancelled"}
                provider._log("INFO", f"[{label}] rendering Kling clip...")
                video_url = provider.call_video(
                    model=video_model, prompt=vid_prompt, image_url=ref_url,
                    duration=duration, aspect_ratio=aspect, sound=sound, label=label,
                )
                file_name = f"broll_{idx:02d}_{category}.mp4"
                dest = out_dir / file_name
                provider.download(video_url, dest)
                provider._log("OK", f"[{label}] saved {dest.name}")
                return {
                    "index": idx, "category": category, "status": "ok",
                    "prompt": vid_prompt, "video_url": video_url, "file": dest.name,
                    "source_file": entry.get("file"),
                }
            except Exception as e:
                provider._log("ERR", f"[{label}] {e}")
                return {
                    "index": idx, "category": category, "status": "error",
                    "error": str(e), "source_file": entry.get("file"),
                }

        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(animate, e) for e in approved]):
                if should_cancel():
                    break
                r = fut.result()
                results.append(r)
                on_result(r)

        results.sort(key=lambda r: r["index"])
        (out_dir / "video_prompts.txt").write_text(
            "\n\n".join(
                f"=== broll_{r['index']:02d}_{r.get('category', '')} ===\n{r.get('prompt', '')}"
                for r in results if r.get("status") == "ok"
            )
        )
        report = {
            "type": "broll_videos",
            "timestamp": ts,
            "brand": brand_name,
            "brand_dna": brand_dna,
            "images_run": str(images_dir),
            "params": {
                "duration": duration,
                "aspect_ratio": aspect,
                "workers": workers,
                "provider": provider.name,
                "video_model": video_model,
                "sound": bool(sound),
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"B-roll videos done: {ok}/{len(results)} animated.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


# ─── Funnel Ads pipeline ────────────────────────────────────────────────────

FUNNEL_PLATFORMS = ["Meta", "TikTok", "Both"]
FUNNEL_LANGUAGES = ["English", "French", "Both"]
FUNNEL_ASPECTS = ["1:1", "4:5", "9:16"]


def run_funnel_ads(
    brand_name: str,
    funnel_stage: str,
    form_fields: dict,
    resolution: str,
    aspect: str,
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
    """Generate funnel-stage static ads from a Brand DNA via LLM2 + NanoBanana.

    Phase 1 (single LLM call): produce N creative blocks separated by ^.
    Phase 2 (per creative): extract the PROMPT line and render via image model.

    form_fields keys (see providers.prompts.generate_funnel_creatives docstring).
    """
    stage = (funnel_stage or "").upper().strip()
    if stage not in FUNNEL_STAGES:
        on_log("ERR", f"Unknown funnel stage: {funnel_stage!r}")
        return None
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
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

    breakdown = form_fields.get("segment_breakdown") or []
    breakdown = [
        {"name": str(b.get("name", "")).strip(), "count": max(0, int(b.get("count", 0) or 0))}
        for b in breakdown if b.get("name")
    ]
    breakdown = [b for b in breakdown if b["count"] > 0]
    n = sum(b["count"] for b in breakdown)
    if n <= 0:
        on_log("ERR", "Pick at least one segment with count > 0.")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    out_dir = base / f"{ts}_funnel_{stage.lower()}_{_safe_name(brand_name)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log(
        "INFO",
        f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]} · "
        f"Stage: {stage} ({FUNNEL_LABELS.get(stage, stage)})",
    )
    breakdown_str = ", ".join(f"{b['count']} {b['name']}" for b in breakdown)
    on_log(
        "INFO",
        f"Generating {n} {stage} creatives ({breakdown_str}) · "
        f"aspect {aspect} · {form_fields.get('language', 'English')}",
    )

    try:
        on_log("INFO", f"Uploading {len(product_paths)} product reference image(s)...")
        product_urls = [provider.upload_image(pp) for pp in product_paths]
        if should_cancel():
            on_log("WARN", "Cancelled during upload.")
            return out_dir

        on_log("INFO", "Calling LLM2 to generate creative prompts...")
        # Inject the form's aspect into form_fields so the LLM uses the right one in metadata.
        form_with_aspect = {
            **form_fields,
            "aspect_ratio": aspect,
            "n_creatives": n,
            "segment_breakdown": breakdown,
        }
        creatives = _gen_funnel_creatives(
            provider,
            brand_dna=brand["dna"],
            funnel_stage=stage,
            form_fields=form_with_aspect,
            product_image_url=product_urls[0],
        )
        if should_cancel():
            on_log("WARN", "Cancelled after prompt generation.")
            return out_dir

        # Persist the full LLM output (metadata + prompt) for later analysis.
        (out_dir / "prompts.txt").write_text(
            "\n\n".join(
                f"=== CREATIVE {i:02d} ===\n{c['metadata']}"
                for i, c in enumerate(creatives, 1)
            )
        )

        def render_one(idx: int, creative: dict) -> dict:
            prompt = creative["prompt"]
            label = f"funnel_{stage.lower()}_{idx:02d}"
            provider._log("INFO", f"[{label}] rendering...")
            softened = False
            try:
                try:
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=product_urls,
                        resolution=resolution, aspect_ratio=aspect, label=label,
                    )
                except CensorshipError:
                    provider._log("WARN", f"[{label}] blocked by content filter — softening")
                    prompt = _soften(provider, prompt, product_urls[0])
                    softened = True
                    img_url = provider.call_image(
                        model=image_model, prompt=prompt, image_urls=product_urls,
                        resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
                    )
                file_name = f"funnel_{stage.lower()}_{idx:02d}.png"
                dest = out_dir / file_name
                provider.download(img_url, dest)
                provider._log(
                    "OK",
                    f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
                )
                return {
                    "index": idx, "stage": stage, "status": "ok",
                    "prompt": prompt, "metadata": creative["metadata"],
                    "image_url": img_url, "file": dest.name, "softened": softened,
                }
            except Exception as e:
                if is_censorship_error(e):
                    provider._log("ERR", f"[{label}] blocked by content filter (after retry).")
                else:
                    provider._log("ERR", f"[{label}] {e}")
                return {
                    "index": idx, "stage": stage, "status": "error",
                    "prompt": prompt, "metadata": creative["metadata"],
                    "error": str(e),
                }

        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [(i + 1, c) for i, c in enumerate(creatives)]
            for fut in as_completed([pool.submit(render_one, *j) for j in jobs]):
                if should_cancel():
                    break
                r = fut.result()
                results.append(r)
                on_result(r)

        results.sort(key=lambda r: r["index"])
        report = {
            "type": "funnel_ads",
            "timestamp": ts,
            "brand": brand_name,
            "brand_dna": brand["dna"],
            "funnel_stage": stage,
            "funnel_label": FUNNEL_LABELS.get(stage, stage),
            "form_fields": form_with_aspect,
            "product_images": [str(p) for p in product_paths],
            "params": {
                "iterations": n,
                "resolution": resolution,
                "aspects": [aspect],
                "aspect_ratio": aspect,
                "language": form_fields.get("language", "English"),
                "platform": form_fields.get("platform", "Meta"),
                "segment_breakdown": breakdown,
                "workers": workers,
                "provider": provider.name,
                "image_model": image_model,
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"Funnel ads done: {ok}/{len(results)} succeeded.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir
