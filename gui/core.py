"""GUI-side glue: pipelines, persistence, brand library."""
import json
import os
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# Serializes Animation state.json mutations so parallel shot generators
# don't clobber each other's writes. Held only across the brief
# load → mutate → save cycle, not during the long-running Kling calls.
_animation_state_lock = threading.Lock()

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
    analyze_image_for_twin as _analyze_twin,
    analyze_for_twin_video as _analyze_twin_video,
    analyze_for_axis as _iterate_analyze,
    analyze_video_for_swap as _analyze_swap,
    generate_animation_character_prompt as _gen_anim_char_prompt,
    generate_broll_image_prompts as _gen_broll_img_prompts,
    generate_broll_video_prompt as _gen_broll_vid_prompt,
    generate_funnel_creatives as _gen_funnel_creatives,
    generate_prompts as _gen_prompts,
    parse_animation_brief as _parse_animation_brief,
    refine_animation_shot_image_prompt as _refine_anim_img,
    refine_animation_shot_video_prompt as _refine_anim_vid,
    soften_prompt as _soften,
)

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _legacy_data_roots() -> list[Path]:
    """Candidate folders that may hold pre-migration user data.

    `_here` is always checked first. If we're running from a git worktree under
    `<repo>/.claude/worktrees/<name>`, also check the parent repo so a launch
    from a worktree still surfaces the user's real brands.
    """
    roots = [_here]
    parts = _here.parts
    if ".claude" in parts:
        i = parts.index(".claude")
        if i + 1 < len(parts) and parts[i + 1] == "worktrees" and i > 0:
            roots.append(Path(*parts[:i]))
    return roots


def _migrate_legacy_user_data(target: Path) -> None:
    """One-time copy/merge of brands.json / brands images / .env from legacy
    project-root locations to ~/Library/Application Support/Ad Variator.

    Before, source-mode runs stored user data inside the project folder, so
    every fresh clone or worktree appeared to "wipe" brands. The fix is a
    single canonical location. Brands are merged across legacy roots — names
    already present in the target win; brand-only-in-legacy is recovered.
    Images and .env are copied non-destructively (target wins on conflict).
    """
    # brands.json — merge legacy entries into target without overwriting
    target_file = target / "brands.json"
    try:
        merged: dict = {}
        if target_file.exists():
            merged.update(json.loads(target_file.read_text()))
        added = False
        for legacy in _legacy_data_roots():
            src = legacy / "brands.json"
            if not src.exists():
                continue
            try:
                data = json.loads(src.read_text())
            except Exception:
                continue
            for name, brand in data.items():
                if name not in merged:
                    merged[name] = brand
                    added = True
        if added or (merged and not target_file.exists()):
            target_file.write_text(json.dumps(merged, indent=2))
    except Exception:
        pass

    # brand images — copy any legacy file whose filename isn't already there
    target_imgs = target / "brands" / "images"
    target_imgs.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in target_imgs.iterdir()} if target_imgs.exists() else set()
    for legacy in _legacy_data_roots():
        src_imgs = legacy / "brands" / "images"
        if not src_imgs.exists():
            continue
        for src in src_imgs.iterdir():
            if src.is_file() and src.name not in existing:
                try:
                    shutil.copy2(src, target_imgs / src.name)
                    existing.add(src.name)
                except Exception:
                    pass

    # .env — only copy when target has none (don't clobber API keys)
    target_env = target / ".env"
    if not target_env.exists():
        for legacy in _legacy_data_roots():
            src = legacy / ".env"
            if src.exists():
                try:
                    shutil.copy2(src, target_env)
                    break
                except Exception:
                    pass


def _user_data_dir() -> Path:
    """Single canonical location for .env, brands.json, brand images.

    Always ~/Library/Application Support/Ad Variator — same location whether
    launched from a worktree, a fresh clone, or the frozen .app. This prevents
    "lost" brands when running the app from a different checkout.
    """
    d = Path.home() / "Library" / "Application Support" / "Ad Variator"
    d.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_user_data(d)
    return d


USER_DATA_DIR = _user_data_dir()
ENV_FILE = USER_DATA_DIR / ".env"

# In frozen mode, app.py loaded the env file early; this no-op call is a safety
# net for source-mode runs where .env sits next to the project root.
load_dotenv(ENV_FILE if ENV_FILE.exists() else None, override=True)

USER_PROFILE_FILE = USER_DATA_DIR / "user.json"


def load_user_name() -> Optional[str]:
    if not USER_PROFILE_FILE.exists():
        return None
    try:
        data = json.loads(USER_PROFILE_FILE.read_text())
    except Exception:
        return None
    name = (data.get("name") or "").strip()
    return name or None


def save_user_name(name: str) -> None:
    name = (name or "").strip()
    if not name:
        return
    USER_PROFILE_FILE.write_text(json.dumps({"name": name}, indent=2))

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
            data = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        images = (sorted(d.glob("variation_*.png")) + sorted(d.glob("variation_*.jpg"))
                  + sorted(d.glob("adapt_*.png")) + sorted(d.glob("adapt_*.jpg"))
                  + sorted(d.glob("broll_*.png")) + sorted(d.glob("broll_*.jpg"))
                  + sorted(d.glob("broll_*.mp4"))
                  + sorted(d.glob("funnel_*.png")) + sorted(d.glob("funnel_*.jpg"))
                  + sorted(d.glob("twin_*.png")) + sorted(d.glob("twin_*.jpg")))
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
        data = json.loads(BRANDS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    healed = {k: _migrate_brand(v) for k, v in data.items()}
    # Persist the healed paths so we don't redo this on every load.
    if json.dumps(healed, sort_keys=True) != json.dumps(data, sort_keys=True):
        try:
            BRANDS_FILE.write_text(json.dumps(healed, indent=2), encoding="utf-8")
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
    BRANDS_FILE.write_text(json.dumps(brands, indent=2), encoding="utf-8")
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
        BRANDS_FILE.write_text(json.dumps(brands, indent=2), encoding="utf-8")


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
            ), encoding="utf-8")

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
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
            ), encoding="utf-8")

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
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
BROLL_CATEGORIES = ["usage", "presentation", "ecu", "in_action", "selfie"]
BROLL_CATEGORY_LABELS = {
    "usage": "USAGE",
    "presentation": "PRESENTATION",
    "ecu": "ECU",
    "in_action": "IN-ACTION",
    "selfie": "SELFIE",
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
            ), encoding="utf-8")

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
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
    lock_product_reference: bool = True,
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
        img_report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        on_log("ERR", f"Could not read images report: {e}")
        return None

    if img_report.get("type") not in ("broll_images", "twin_images"):
        on_log("ERR", f"Run at {images_dir} is not a B-roll or Twin images run.")
        return None

    brand_name = img_report.get("brand") or img_report.get("source_label") or "twin"
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

        # Optionally upload the brand's product reference images so the video
        # provider can lock the product (logo / labels / printed text)
        # visually across the clip via Kling's element reference system.
        product_ref_urls: list[str] = []
        if lock_product_reference:
            product_paths_raw = img_report.get("product_images") or []
            product_paths = [Path(p) for p in product_paths_raw if p and Path(p).exists()]
            if product_paths:
                on_log(
                    "INFO",
                    f"Uploading {len(product_paths)} product reference image(s) for locking...",
                )
                for pp in product_paths[:4]:  # cap at 4 (Kling element max)
                    if should_cancel():
                        break
                    try:
                        product_ref_urls.append(provider.upload_image(pp))
                    except Exception as e:
                        on_log("WARN", f"Skipped product ref {pp.name}: {e}")
                if not product_ref_urls:
                    on_log(
                        "WARN",
                        "Product reference upload failed — continuing without locking.",
                    )
            else:
                on_log(
                    "INFO",
                    "No product images on disk for this run — locking disabled.",
                )
        if should_cancel():
            on_log("WARN", "Cancelled during product reference upload.")
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
                    duration=duration, aspect_ratio=aspect, sound=sound,
                    product_reference_urls=product_ref_urls, label=label,
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
            ), encoding="utf-8")
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
                "lock_product_reference": bool(lock_product_reference),
                "product_reference_count": len(product_ref_urls),
                "llm_model": "claude-sonnet-4-6",
            },
            "results": results,
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
            ), encoding="utf-8")

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
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"Funnel ads done: {ok}/{len(results)} succeeded.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


# ─── Twin pipeline ──────────────────────────────────────────────────────────

def run_twin_analyze(
    image_path: str,
    hint: str,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
) -> Optional[str]:
    """Phase A of Twin: vision-LLM analyzes the reference and returns ONE
    text-to-image prompt. The user reviews/edits it before phase B.
    Returns the generated prompt string, or None on error.
    """
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    src = Path(image_path).expanduser().resolve()
    if not src.exists():
        on_log("ERR", f"File not found: {src}")
        return None

    try:
        on_log("INFO", f"Uploading reference: {src.name}")
        ref_url = provider.upload_image(src)
        on_log("INFO", "Analyzing image with vision LLM...")
        prompt = _analyze_twin(provider, ref_url, hint=hint)
        on_log("OK", f"Analysis done · {len(prompt)} chars · {len(prompt.split())} words")
        return prompt
    except Exception as e:
        on_log("ERR", str(e))
        return None


def run_twin_generate(
    image_path: str,
    prompt: str,
    n_variants: int,
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
    hint: str = "",
) -> Optional[Path]:
    """Phase B of Twin: render N variants of the (edited) prompt via pure
    text-to-image — the reference is intentionally NOT passed to the image
    model so the result is a re-creation, not an edit.

    Writes report.json with type="twin_images" so phase 2 (video animation)
    can pick it up via run_broll_videos.
    """
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}")
        return None
    n = max(1, int(n_variants or 1))
    if not (prompt or "").strip():
        on_log("ERR", "Empty prompt — nothing to generate.")
        return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    src = Path(image_path).expanduser().resolve()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    label_root = _safe_name(src.stem) or "twin"
    out_dir = base / f"{ts}_twin_{label_root}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")
    on_log(
        "INFO",
        f"Provider: {provider.display_name} · Model: {IMAGE_MODEL_LABELS[image_model]} · "
        f"text-to-image · {n} variant{'s' if n > 1 else ''} · {aspect} · {resolution}",
    )

    # Persist the prompt for inspection / re-runs.
    (out_dir / "prompt.txt").write_text(prompt.strip() + "\n", encoding="utf-8")

    def render_one(idx: int) -> dict:
        label = f"twin_{idx:02d}"
        provider._log("INFO", f"[{label}] rendering...")
        local_prompt = prompt
        softened = False
        try:
            try:
                img_url = provider.call_image_t2i(
                    model=image_model, prompt=local_prompt,
                    resolution=resolution, aspect_ratio=aspect, label=label,
                )
            except CensorshipError:
                provider._log("WARN", f"[{label}] blocked by content filter — softening")
                local_prompt = _soften(provider, local_prompt, "")
                softened = True
                img_url = provider.call_image_t2i(
                    model=image_model, prompt=local_prompt,
                    resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
                )
            file_name = f"twin_{idx:02d}.png"
            dest = out_dir / file_name
            provider.download(img_url, dest)
            provider._log(
                "OK",
                f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""),
            )
            # Use category="twin" so the approval/animation grid stays consistent
            # with the B-Roll plumbing that expects a category field.
            return {
                "index": idx, "category": "twin", "status": "ok",
                "prompt": local_prompt, "image_url": img_url, "file": dest.name,
                "softened": softened,
            }
        except Exception as e:
            if is_censorship_error(e):
                provider._log("ERR", f"[{label}] blocked by content filter (after retry).")
            else:
                provider._log("ERR", f"[{label}] {e}")
            return {
                "index": idx, "category": "twin", "status": "error",
                "prompt": local_prompt, "error": str(e),
            }

    results: list[dict] = []
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(render_one, i + 1) for i in range(n)]):
                if should_cancel():
                    break
                r = fut.result()
                results.append(r)
                on_result(r)

        results.sort(key=lambda r: r["index"])
        report = {
            "type": "twin_images",
            "timestamp": ts,
            "source_label": label_root,
            "reference_image": str(src),
            "prompt": prompt,
            "hint": hint,
            "params": {
                "iterations": n,
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
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        ok = sum(1 for r in results if r.get("status") == "ok")
        on_log("OK", f"Twin done: {ok}/{len(results)} succeeded.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        return out_dir


# ─── Twin VIDEO pipeline (UGC hook clone with brand product injection) ──────
#
# Different intent from Twin (image): we take a frame from the user's old UGC
# ad and clone the scene into a NEW 5-10s clip with their new brand product
# injected. Two phases:
#   A. analyze — Vision LLM looks at the frame + the brand DNA → returns
#      {scene, action} prompts the user can review/edit.
#   B. generate — image gen with the product as ref produces a fresh starting
#      frame, then Kling 3.0 animates it with the action prompt + product
#      locking. Output is a single mp4 + report.json so it shows in History.

def run_twin_video_analyze(
    frame_path: str,
    brand_name: str,
    hint: str,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
) -> Optional[dict]:
    """Phase A — analyze a UGC frame and return {scene, action, brand_dna,
    product_paths} for the user to review before generating.
    Returns None on error.
    """
    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    src = Path(frame_path).expanduser().resolve()
    if not src.exists():
        on_log("ERR", f"File not found: {src}")
        return None

    brands = load_brands()
    brand = brands.get(brand_name)
    if not brand:
        on_log("ERR", f"Brand '{brand_name}' not found.")
        return None
    product_paths = [Path(p) for p in brand.get("product_images", []) if Path(p).exists()]
    if not product_paths:
        on_log("ERR", f"Brand '{brand_name}' has no product images on disk.")
        return None

    brand_dna = (brand.get("dna") or "").strip()
    # The vision LLM only needs a tight product description, not the whole DNA
    # (which can be 5000+ chars and dilutes the analysis). Pull a couple of
    # paragraphs around "Product" / "packaging" if present, else fall back to
    # the first 1200 chars.
    product_blurb = _extract_product_blurb(brand_dna) or brand_dna[:1200]

    try:
        on_log("INFO", f"Uploading reference frame: {src.name}")
        frame_url = provider.upload_image(src)
        on_log("INFO", "Analyzing frame + product with vision LLM...")
        out = _analyze_twin_video(
            provider, frame_url=frame_url,
            product_description=product_blurb, hint=hint,
        )
        on_log(
            "OK",
            f"Analysis done · scene {len(out['scene'].split())} words · "
            f"action {len(out['action'].split())} words",
        )
        out["brand_dna"] = brand_dna
        out["product_paths"] = [str(p) for p in product_paths]
        out["frame_path"] = str(src)
        return out
    except Exception as e:
        on_log("ERR", str(e))
        return None


def _extract_product_blurb(dna: str) -> str:
    """Pull the section of a Brand DNA describing packaging/product cues, if
    present. Looks for headings like '## Product', '## Packaging', etc.
    """
    if not dna:
        return ""
    lines = dna.splitlines()
    keep: list[str] = []
    grabbing = False
    for line in lines:
        ls = line.strip().lower()
        if ls.startswith("##") or ls.startswith("# "):
            grabbing = any(
                k in ls for k in
                ("product", "packaging", "visual style", "signature", "pack")
            )
            if grabbing:
                keep.append(line)
                continue
            if keep and not grabbing:
                break
        elif grabbing:
            keep.append(line)
    return "\n".join(keep).strip()


def run_twin_video_generate(
    frame_path: str,
    scene_prompt: str,
    action_prompt: str,
    brand_name: str,
    duration: int,
    aspect: str,
    sound: bool,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    output_root: Optional[str] = None,
    *,
    image_model: str = DEFAULT_IMAGE_MODEL,
    video_model: str = DEFAULT_VIDEO_MODEL,
    provider_name: Optional[str] = None,
) -> Optional[Path]:
    """Backward-compat wrapper: render the starting frame, then animate it.
    Most callers should now go through `run_twin_video_render_frame` followed
    by `run_twin_video_animate` so the user can validate the still before
    paying for a Kling render.
    """
    out = run_twin_video_render_frame(
        frame_path=frame_path,
        scene_prompt=scene_prompt,
        brand_name=brand_name,
        aspect=aspect,
        on_log=on_log, on_out_dir=on_out_dir,
        should_cancel=should_cancel,
        output_root=output_root,
        image_model=image_model,
        provider_name=provider_name,
    )
    if not out or out.get("status") != "ok":
        return out.get("out_dir") if out else None
    res = run_twin_video_animate(
        out_dir=out["out_dir"],
        image_url=out["image_url"],
        action_prompt=action_prompt,
        brand_name=brand_name,
        product_urls=out["product_urls"],
        duration=duration, aspect=aspect, sound=sound,
        on_log=on_log, on_result=on_result,
        should_cancel=should_cancel,
        scene_prompt_used=out["scene_prompt_used"],
        source_frame=Path(frame_path).expanduser().resolve(),
        image_model=image_model, video_model=video_model,
        provider_name=provider_name,
    )
    return res or out["out_dir"]


def run_twin_video_render_frame(
    frame_path: str,
    scene_prompt: str,
    brand_name: str,
    aspect: str,
    on_log: Callable[[str, str], None],
    *,
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    output_root: Optional[str] = None,
    image_model: str = DEFAULT_IMAGE_MODEL,
    resolution: str = "1k",
    provider_name: Optional[str] = None,
    out_dir: Optional[Path] = None,
    product_urls: Optional[list[str]] = None,
    source_frame_url: Optional[str] = None,
) -> Optional[dict]:
    """Phase B-1: edit the source frame to swap the held product for the
    user's brand product. Returns {out_dir, image_url, image_path,
    product_urls, source_frame_url, scene_prompt_used, status}.

    The source frame is uploaded once and reused on re-renders; same for
    product refs. `out_dir`, `product_urls`, and `source_frame_url` can be
    passed in to avoid re-uploading on iteration.
    """
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}"); return None
    if not (scene_prompt or "").strip():
        on_log("ERR", "Empty scene prompt."); return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings."); return None

    brands = load_brands()
    brand = brands.get(brand_name)
    if not brand:
        on_log("ERR", f"Brand '{brand_name}' not found."); return None
    product_paths = [Path(p) for p in brand.get("product_images", []) if Path(p).exists()]
    if not product_paths:
        on_log("ERR", f"Brand '{brand_name}' has no product images on disk.")
        return None

    src = Path(frame_path).expanduser().resolve()

    # First-time call → create output dir, snapshot prompts + source frame.
    # Re-render → reuse the existing dir, just overwrite generated_frame.png.
    if out_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(output_root).expanduser() if output_root else get_output_dir()
        label = _safe_name(brand_name) or "brand"
        out_dir = base / f"{ts}_twin_video_{label}"
        out_dir.mkdir(parents=True, exist_ok=True)
        on_out_dir(out_dir)
        on_log("INFO", f"Output: {out_dir}")
        if src.exists():
            try:
                shutil.copy2(src, out_dir / f"source_frame{src.suffix or '.png'}")
            except Exception:
                pass
    (out_dir / "scene_prompt.txt").write_text(scene_prompt.strip() + "\n", encoding="utf-8")

    on_log(
        "INFO",
        f"Provider: {provider.display_name} · Image: {IMAGE_MODEL_LABELS[image_model]} · {aspect}",
    )

    try:
        # Upload the source frame the FIRST time only. NanoBanana 2 edit
        # treats image 1 as the canvas to preserve, image 2+ as references —
        # so the source has to be passed first and the product after.
        if not source_frame_url:
            if not src.exists():
                on_log("ERR", f"Source frame missing on disk: {src}")
                return {"out_dir": out_dir, "status": "error",
                        "error": "source frame missing", "product_urls": product_urls or []}
            on_log("INFO", f"Uploading source frame: {src.name}")
            source_frame_url = provider.upload_image(src)

        if not product_urls:
            on_log("INFO", f"Uploading {len(product_paths)} product reference image(s)...")
            product_urls = []
            for pp in product_paths[:4]:
                if should_cancel():
                    return {"out_dir": out_dir, "status": "cancelled",
                            "product_urls": product_urls,
                            "source_frame_url": source_frame_url}
                try:
                    product_urls.append(provider.upload_image(pp))
                except Exception as e:
                    on_log("WARN", f"Skipped product ref {pp.name}: {e}")
            if not product_urls:
                on_log("ERR", "No product references uploaded — abort.")
                return {"out_dir": out_dir, "status": "error",
                        "error": "no product refs", "product_urls": [],
                        "source_frame_url": source_frame_url}

        if should_cancel():
            return {"out_dir": out_dir, "status": "cancelled",
                    "product_urls": product_urls,
                    "source_frame_url": source_frame_url}

        # NanoBanana 2 edit semantics: image 1 = the canvas to preserve, the
        # rest = refs to compose into that canvas. So source first, then the
        # product so it can be swapped in via the @product token in the prompt.
        edit_image_urls = [source_frame_url, *product_urls]

        on_log("INFO", "Editing source frame: swapping the held product...")
        local_scene = scene_prompt
        try:
            start_img_url = provider.call_image(
                model=image_model, prompt=local_scene,
                image_urls=edit_image_urls,
                resolution=resolution,
                aspect_ratio=aspect, label="twin-vid-edit",
            )
        except CensorshipError:
            on_log("WARN", "Edit blocked by content filter — softening prompt")
            local_scene = _soften(provider, local_scene, "")
            start_img_url = provider.call_image(
                model=image_model, prompt=local_scene,
                image_urls=edit_image_urls,
                resolution=resolution,
                aspect_ratio=aspect, label="twin-vid-edit-retry",
            )

        frame_dest = out_dir / "generated_frame.png"
        try:
            provider.download(start_img_url, frame_dest)
            on_log("OK", f"Edited frame ready: {frame_dest.name}")
        except Exception as e:
            on_log("WARN", f"Could not save frame locally: {e}")

        return {
            "out_dir": out_dir,
            "status": "ok",
            "image_url": start_img_url,
            "image_path": frame_dest if frame_dest.exists() else None,
            "product_urls": product_urls,
            "source_frame_url": source_frame_url,
            "scene_prompt_used": local_scene,
        }
    except Exception as e:
        on_log("ERR", f"Image edit failed: {e}")
        return {"out_dir": out_dir, "status": "error", "error": str(e),
                "product_urls": product_urls or [],
                "source_frame_url": source_frame_url}


def run_twin_video_animate(
    out_dir: Path,
    image_url: str,
    action_prompt: str,
    brand_name: str,
    product_urls: list[str],
    duration: int,
    aspect: str,
    sound: bool,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    *,
    should_cancel: Callable[[], bool] = lambda: False,
    scene_prompt_used: str = "",
    source_frame: Optional[Path] = None,
    image_model: str = DEFAULT_IMAGE_MODEL,
    video_model: str = DEFAULT_VIDEO_MODEL,
    video_resolution: str = "",
    provider_name: Optional[str] = None,
) -> Optional[Path]:
    """Phase B-2: animate a previously-rendered starting frame into a Kling
    clip. Writes report.json with type='twin_video' on completion.
    """
    if video_model not in VIDEO_MODELS:
        on_log("ERR", f"Unknown video model: {video_model!r}"); return None
    if not (action_prompt or "").strip():
        on_log("ERR", "Empty action prompt."); return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)

    out_dir = Path(out_dir)
    (out_dir / "action_prompt.txt").write_text(action_prompt.strip() + "\n", encoding="utf-8")
    ts = out_dir.name.split("_")[0:2]  # "YYYYMMDD_HHMMSS"
    ts = "_".join(ts) if len(ts) == 2 else datetime.now().strftime("%Y%m%d_%H%M%S")

    result_entry: dict = {
        "index": 1, "category": "twin_video", "status": "pending",
        "scene_prompt": scene_prompt_used, "action_prompt": action_prompt,
        "image_url": image_url,
    }

    try:
        on_log("INFO", "Animating with Kling...")
        clip_url = provider.call_video(
            model=video_model, prompt=action_prompt,
            image_url=image_url,
            duration=int(duration), aspect_ratio=aspect, sound=bool(sound),
            product_reference_urls=product_urls, label="twin-video",
            resolution=video_resolution,
        )
        clip_dest = out_dir / "clip.mp4"
        provider.download(clip_url, clip_dest)
        on_log("OK", f"Clip saved: {clip_dest.name}")

        result_entry.update({
            "status": "ok",
            "video_url": clip_url,
            "file": clip_dest.name,
        })
        on_result(result_entry)
        _write_twin_video_report(
            out_dir, ts, brand_name, video_model, image_model,
            duration, aspect, sound, [result_entry],
            source_frame or out_dir,
        )
        on_log("OK", "Twin video done.")
        return out_dir
    except Exception as e:
        on_log("ERR", str(e))
        result_entry["status"] = "error"; result_entry["error"] = str(e)
        on_result(result_entry)
        _write_twin_video_report(
            out_dir, ts, brand_name, video_model, image_model,
            duration, aspect, sound, [result_entry],
            source_frame or out_dir,
        )
        return out_dir


# ─── Iteration pipeline (single-axis static ad iteration) ──────────────────
#
# MVP V1 — Headline axis only. The user batches N source images, each gets
# a per-image "iterate headline ×K" config, the page runs them in parallel.
# For each source image:
#   1. Upload to provider
#   2. Vision LLM extracts the headline + style and returns K variants
#   3. For each variant, call NanoBanana 2 edit with [source, ...] + an
#      explicit "replace only the main headline" prompt
#   4. Download each variant to outputs/<ts>_iterate_headline_<stem>/

def run_iterate(
    image_path: str,
    axis: str,
    n_variants: int,
    on_log: Callable[[str, str], None],
    on_result: Callable[[dict], None],
    *,
    on_out_dir: Callable[[Path], None] = lambda _p: None,
    should_cancel: Callable[[], bool] = lambda: False,
    output_root: Optional[str] = None,
    image_model: str = DEFAULT_IMAGE_MODEL,
    resolution: str = "1k",
    provider_name: Optional[str] = None,
    targets: Optional[list[dict]] = None,
) -> Optional[Path]:
    """Run a single-axis iteration on one source image. Dispatches by
    `axis` to the right analyzer + edit prompt from ITERATION_AXES.

    `targets`, when provided, is an explicit list of catalog entries
    [{"slug", "label", "hint"}, ...]. The Vision-LLM analyzer is bypassed
    and these entries become the variants directly — used by the catalog-
    axis UI where the user multi-selects which sub-options to iterate.
    When None, falls back to the LLM analyzer for open-axis behavior.
    """
    from providers.prompts import ITERATION_AXES
    if axis not in ITERATION_AXES:
        on_log("ERR", f"Unknown axis: {axis!r}"); return None
    axis_meta = ITERATION_AXES[axis]
    # When the user picks targets explicitly, N is derived from that list.
    if targets:
        n = len(targets)
    else:
        n = max(1, int(n_variants or 1))

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set."); return None
    if image_model not in IMAGE_MODELS:
        on_log("ERR", f"Unknown image model: {image_model!r}"); return None

    src = Path(image_path).expanduser().resolve()
    if not src.exists():
        on_log("ERR", f"Source image not found: {src}"); return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    stem = _safe_name(src.stem) or "iter"
    out_dir = base / f"{ts}_iterate_{axis}_{stem}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")

    # 1) Upload source once, reused across all variants.
    try:
        on_log("INFO", f"Uploading source: {src.name}")
        src_url = provider.upload_image(src)
    except Exception as e:
        on_log("ERR", f"Upload failed: {e}"); return out_dir
    if should_cancel():
        return out_dir

    # 2) Build the list of variant strings.
    # If explicit catalog targets were picked → use them directly (no LLM).
    # Otherwise → call the axis's Vision-LLM analyzer (open-axis path).
    if targets:
        variants = [f"{t.get('label', '')} — {t.get('hint', '')}" for t in targets]
        detected = "(explicit catalog targets)"
        style_summary = ", ".join(t.get("slug", "") for t in targets)
        analysis = {
            "detected": detected, "style_summary": style_summary,
            "variants": variants, "explicit_targets": targets,
        }
        on_log("OK", f"Using {len(variants)} explicit target(s) from catalog.")
    else:
        try:
            on_log("INFO", f"Analyzing {axis_meta['describe']} + generating {n} variants...")
            analysis = _iterate_analyze(provider, src_url, axis, n)
        except Exception as e:
            on_log("ERR", f"{axis} analysis failed: {e}"); return out_dir
        variants = analysis.get("variants") or []
        detected = analysis.get("detected", "")
        style_summary = analysis.get("style_summary", "")
        on_log(
            "OK",
            f"Detected: \"{str(detected)[:80]}\" · {style_summary[:80]} · "
            f"{len(variants)} variants ready",
        )
    try:
        (out_dir / "analysis.json").write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        shutil.copy2(src, out_dir / f"source{src.suffix or '.png'}")
    except Exception:
        pass

    # 3) Render each variant via image-to-image edit. The source remains
    # image_urls[0] for every variant — the model treats it as the canvas
    # and applies the axis-specific edit instruction on top.
    aspect = "1:1"  # provider derives true ratio from the source frame anyway.
    edit_template = axis_meta["edit_prompt"]

    def render_one(idx: int, variant: str) -> dict:
        label = f"iter_{axis[:4]}_{idx:02d}"
        prompt = edit_template.format(variant=variant)
        try:
            on_log("INFO", f"[{label}] editing source ({axis})...")
            try:
                img_url = provider.call_image(
                    model=image_model, prompt=prompt, image_urls=[src_url],
                    resolution=resolution, aspect_ratio=aspect, label=label,
                )
            except CensorshipError:
                on_log("WARN", f"[{label}] blocked by content filter — softening prompt")
                soft = _soften(provider, prompt, src_url)
                img_url = provider.call_image(
                    model=image_model, prompt=soft, image_urls=[src_url],
                    resolution=resolution, aspect_ratio=aspect, label=label + "-retry",
                )
            file_name = f"variant_{idx:02d}.png"
            dest = out_dir / file_name
            provider.download(img_url, dest)
            on_log("OK", f"[{label}] saved {dest.name}")
            return {
                "index": idx, "status": "ok", "variant": variant,
                "image_url": img_url, "file": dest.name,
            }
        except Exception as e:
            on_log("ERR", f"[{label}] {e}")
            return {
                "index": idx, "status": "error", "variant": variant,
                "error": str(e),
            }

    results: list[dict] = []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(render_one, i + 1, variants[i]) for i in range(len(variants))]
            for f in as_completed(futs):
                if should_cancel():
                    break
                r = f.result()
                results.append(r)
                on_result(r)
    except Exception as e:
        on_log("ERR", str(e))

    results.sort(key=lambda r: r["index"])
    report = {
        "type": f"iterate_{axis}",
        "timestamp": ts,
        "source": str(src),
        "axis": axis,
        "detected": detected,
        "style_summary": style_summary,
        "params": {
            "iterations": n,
            "image_model": image_model,
            "resolution": resolution,
            "provider": provider.name,
        },
        "results": results,
    }
    try:
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass
    ok = sum(1 for r in results if r.get("status") == "ok")
    on_log("OK", f"Done · {ok}/{len(results)} variants succeeded.")
    return out_dir


# Backward-compat alias for any external callers that still target the
# old single-axis entry point.
def run_iterate_headline(image_path, n_variants, on_log, on_result, **kwargs):
    return run_iterate(image_path, "headline", n_variants, on_log, on_result, **kwargs)


def _write_twin_video_report(
    out_dir: Path, ts: str, brand_name: str, video_model: str,
    image_model: str, duration: int, aspect: str, sound: bool,
    results: list[dict], source_frame: Path,
) -> None:
    report = {
        "type": "twin_video",
        "timestamp": ts,
        "brand": brand_name,
        "source_frame": str(source_frame),
        "params": {
            "duration": int(duration),
            "aspect_ratio": aspect,
            "sound": bool(sound),
            "image_model": image_model,
            "video_model": video_model,
            "provider": get_active_provider_name(),
            "iterations": 1,
        },
        "results": results,
    }
    try:
        (out_dir / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ─── Swap product pipeline (Seedance v2 video-to-video) ─────────────────────
#
# Workflow:
#   1. ffmpeg extracts up to 4 keyframes from the source video.
#   2. Compose a vertical strip (2x2 source grid above the user's packshot)
#      so a single Vision call sees both the ad and the product to inject.
#   3. Claude Vision writes a swap brief that references the packshot via
#      `@image1` (Seedance's templating syntax).
#   4. Upload source video + packshot to MuAPI.
#   5. Call `seedance-v2.0-video-edit` — preserves source faces / motion /
#      audio, replaces only the targeted product.
#   6. Download the output mp4 to the run folder.

_SWAP_KEYFRAME_COUNT = 4         # 2x2 grid for Vision
_SWAP_DEFAULT_DURATION = 5       # Seedance accepts 4-15
_SWAP_MAX_VIDEO_BYTES = 10 * 1024 * 1024
_SWAP_MAX_VIDEO_SECONDS = 15.0


def _have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _probe_video(path: Path) -> dict:
    """Return {duration_sec, width, height} via ffprobe. Raises on failure."""
    import subprocess
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_streams", "-show_format", str(path),
        ],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {(proc.stderr or '').strip()[-300:]}")
    data = json.loads(proc.stdout)
    duration = float(data.get("format", {}).get("duration") or 0.0)
    w = h = 0
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            w = int(s.get("width") or 0)
            h = int(s.get("height") or 0)
            break
    return {"duration_sec": duration, "width": w, "height": h}


def _extract_keyframes(video_path: Path, target_dir: Path, n: int) -> list[Path]:
    """Spread n keyframes evenly between 5% and 95% of the video duration."""
    import subprocess
    info = _probe_video(video_path)
    duration = info["duration_sec"]
    if duration <= 0:
        raise RuntimeError(f"Video has zero duration: {video_path.name}")
    target_dir.mkdir(parents=True, exist_ok=True)
    margin = duration * 0.05
    span = max(0.1, duration - 2 * margin)
    out: list[Path] = []
    for i in range(n):
        t = margin + (span * i / max(1, n - 1)) if n > 1 else duration / 2.0
        kf = target_dir / f"frame_{i:02d}.png"
        proc = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", f"{max(0.0, t):.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(kf),
            ],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0 or not kf.exists():
            raise RuntimeError(
                f"ffmpeg frame extract @ {t:.2f}s failed: "
                f"{(proc.stderr or '').strip()[-300:]}"
            )
        out.append(kf)
    return out


def _compose_swap_grid(keyframes: list[Path], product: Path, target: Path) -> Path:
    """Build a 2x3 grid of keyframes + product packshot for Vision analysis.

    Cells are 540x960 (vertical 9:16) with letterboxing — final image is
    1080x2880, well below Anthropic's ~1568px long-edge resize threshold
    so we don't waste bytes on pixels that get dropped server-side. Saved
    as JPEG quality 4 (≈85%) to keep payloads under ~1MB even for busy
    keyframes; PNG was producing 6-10MB outputs that tripped Anthropic's
    base64 size limit on the swap workflow.
    """
    import subprocess
    if not keyframes:
        raise RuntimeError("compose: no keyframes")
    target.parent.mkdir(parents=True, exist_ok=True)

    cell_w, cell_h = 540, 960
    inputs: list[str] = []
    # 4 keyframes (pad by repeating last if fewer than 4) + 1 product = 5 inputs.
    cells = list(keyframes[:4])
    while len(cells) < 4:
        cells.append(keyframes[-1])
    # The product is duplicated to fill the bottom row cleanly (2x3 grid).
    for img in cells + [product, product]:
        inputs.extend(["-i", str(img)])

    n_cells = 6  # 2 cols x 3 rows
    scale_chain = []
    for i in range(n_cells):
        scale_chain.append(
            f"[{i}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
            f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}]"
        )
    full_inputs = "".join(f"[v{i}]" for i in range(n_cells))
    layout_parts = []
    for r in range(3):
        for c in range(2):
            layout_parts.append(f"{c * cell_w}_{r * cell_h}")
    layout = "|".join(layout_parts)
    filter_complex = (
        ";".join(scale_chain)
        + f";{full_inputs}xstack=inputs={n_cells}:layout={layout}[out]"
    )
    # -q:v 4 maps to ~85% JPEG quality (1=best, 31=worst). High enough for
    # Vision to read product details, small enough to stay well under
    # Anthropic's 5MB base64 cap as a safety net.
    proc = subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
         "-map", "[out]", "-q:v", "4", str(target)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(
            f"ffmpeg grid composition failed: {(proc.stderr or '').strip()[-300:]}"
        )
    return target


def _swap_aspect_for(width: int, height: int) -> str:
    """Map the source video shape to one of Seedance's accepted aspects."""
    if not width or not height:
        return "9:16"
    r = width / height
    if r < 0.7:    return "9:16"
    if r < 0.95:  return "3:4"
    if r < 1.1:   return "1:1"
    if r < 1.5:   return "4:3"
    return "16:9"


def run_swap_analyze(
    source_video_path: str,
    product_image_path: str,
    extra_hint: str,
    on_log: Callable[[str, str], None],
    *,
    output_root: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Optional[dict]:
    """Phase A: prepare the swap. Extracts keyframes, composes the analysis
    grid, runs Claude Vision and returns the swap brief.

    Returns a dict {brief, work_dir, source_path, product_path, video_info}
    so phase B can pick up where we left off without re-extracting frames.
    Returns None on error.
    """
    if not _have_ffmpeg():
        on_log("ERR", "ffmpeg / ffprobe not found on PATH. Install via `brew install ffmpeg`.")
        return None

    src = Path(source_video_path).expanduser().resolve()
    prod = Path(product_image_path).expanduser().resolve()
    if not src.exists():
        on_log("ERR", f"Source video not found: {src}"); return None
    if not prod.exists():
        on_log("ERR", f"Product image not found: {prod}"); return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    # Probe early so we can warn the user before paying for Vision.
    try:
        info = _probe_video(src)
    except Exception as e:
        on_log("ERR", str(e)); return None

    duration = info["duration_sec"]
    size_mb = src.stat().st_size / 1e6
    on_log(
        "INFO",
        f"Source: {src.name} · {duration:.1f}s · {info['width']}x{info['height']} · {size_mb:.1f}MB",
    )
    if duration > _SWAP_MAX_VIDEO_SECONDS:
        on_log("ERR", (
            f"Source is {duration:.1f}s, Seedance video-edit accepts max "
            f"{_SWAP_MAX_VIDEO_SECONDS:.0f}s. Trim and retry."
        ))
        return None
    if size_mb * 1e6 > _SWAP_MAX_VIDEO_BYTES:
        on_log("ERR", (
            f"Source is {size_mb:.1f}MB, MuAPI's upload cap is "
            f"{_SWAP_MAX_VIDEO_BYTES/1e6:.0f}MB. Compress and retry."
        ))
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    label_root = _safe_name(src.stem) or "swap"
    work_dir = base / f"{ts}_swap_{label_root}"
    work_dir.mkdir(parents=True, exist_ok=True)
    on_log("INFO", f"Output: {work_dir}")

    try:
        on_log("INFO", "Extracting keyframes for Vision analysis…")
        kf_dir = work_dir / "_keyframes"
        keyframes = _extract_keyframes(src, kf_dir, _SWAP_KEYFRAME_COUNT)
        on_log("OK", f"{len(keyframes)} keyframes extracted")

        on_log("INFO", "Composing analysis grid (source 2x2 + packshot)…")
        grid = _compose_swap_grid(keyframes, prod, work_dir / "_grid.jpg")
        grid_url = provider.upload_image(grid)

        on_log("INFO", "Claude Vision is writing the swap brief…")
        brief = _analyze_swap(provider, grid_url, extra_hint=extra_hint)
        (work_dir / "brief.txt").write_text(brief.strip() + "\n", encoding="utf-8")
        on_log(
            "OK",
            f"Brief ready · {len(brief)} chars · {len(brief.split())} words",
        )
        return {
            "brief": brief,
            "work_dir": str(work_dir),
            "source_path": str(src),
            "product_path": str(prod),
            "video_info": info,
        }
    except Exception as e:
        on_log("ERR", str(e))
        return None


def run_swap_generate(
    work_dir: str,
    source_path: str,
    product_path: str,
    brief: str,
    duration_s: int,
    on_log: Callable[[str, str], None],
    *,
    aspect_ratio: Optional[str] = None,
    quality: str = "basic",
    provider_name: Optional[str] = None,
    video_info: Optional[dict] = None,
) -> Optional[Path]:
    """Phase B: upload source + packshot, call Seedance video-edit, save the mp4.

    Returns the output mp4 path, or None on error.
    """
    src = Path(source_path)
    prod = Path(product_path)
    out_dir = Path(work_dir)
    if not src.exists() or not prod.exists() or not out_dir.exists():
        on_log("ERR", "Missing source / product / work folder — re-run analysis.")
        return None

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        on_log("ERR", f"{provider.display_name} key not set. Open Settings.")
        return None

    info = video_info or _probe_video(src)
    aspect = aspect_ratio or _swap_aspect_for(info.get("width", 0), info.get("height", 0))

    try:
        source_url = provider.upload_video(src)
        product_url = provider.upload_image(prod)

        on_log("INFO", "Calling Seedance v2.0 video-edit…")
        out_url = provider.call_swap_video(
            model="seedance_2",
            prompt=brief,
            source_video_url=source_url,
            product_image_url=product_url,
            duration=duration_s,
            aspect_ratio=aspect,
            quality=quality,
            label="swap",
        )
        dest = out_dir / "swap.mp4"
        provider.download(out_url, dest)
        on_log("OK", f"Saved: {dest}")

        # Persist a tiny report for the History page (and future re-runs).
        report = {
            "type": "swap_video",
            "timestamp": out_dir.name.split("_")[0:2],
            "source_video": str(src),
            "product_image": str(prod),
            "brief": brief,
            "params": {
                "provider": provider.name,
                "model": "seedance_2",
                "endpoint": "seedance-v2.0-video-edit",
                "duration": int(duration_s),
                "aspect_ratio": aspect,
                "quality": quality,
                "llm_model": "claude-sonnet-4-6",
            },
            "results": [{"status": "ok", "file": dest.name, "url": out_url}],
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return dest
    except Exception as e:
        on_log("ERR", str(e))
        return None


# ─── Animation pipeline (multi-shot narrative video) ────────────────────────
#
# Architecture: each project lives in its own folder under outputs/, with a
# `state.json` that tracks progress across the 6 UI panels (brief → scenario
# → characters → anchor → shots → export). The state file is the source of
# truth for resume-on-reboot.
#
# state.json schema (stable; UI reads/writes it as the single contract):
# {
#   "type": "animation",
#   "version": 1,
#   "status": "brief|scenario|characters|anchor|shots|done",
#   "timestamp": "20260508_104614",
#   "project_name": "...",
#   "brand": "...",
#   "image_model": "nano_banana_2",
#   "video_model": "kling_3_std",
#   "aspect_ratio": "9:16",
#   "default_duration": 4,
#   "brief_text": "...",
#   "product": {"name": "...", "image": "/abs/path"},
#   "style_refs": ["/abs/path", ...],
#   "scenario": { ... output of parse_animation_brief ... },
#   "characters": {
#       "<id>": {
#         "id": "...", "description": "...", "prompt": "...",
#         "image": "characters/<id>.png", "status": "draft|approved|failed"
#       }
#   },
#   "shots": {
#       "<id>": {
#         "id": 1, "duration": 3, "description": "...", "characters": [...],
#         "shows_product": true, "image_prompt": "...", "video_prompt": "...",
#         "image_status": "pending|generating|review|approved|failed",
#         "video_status": "pending|generating|review|approved|failed",
#         "image_file": "shots/shot_001.png",
#         "video_file": "shots/shot_001.mp4",
#         "image_error": "...", "video_error": "..."
#       }
#   }
# }


ANIMATION_DEFAULT_DURATION = 5
ANIMATION_DURATION_MIN = 5
ANIMATION_DURATION_MAX = 10
# Kling 3.0 endpoints only render at 5s or 10s — anything in-between gets
# auto-rounded or 422'd by MuAPI. Surface a finite set in the UI rather
# than a freeform spinbox so users can't pick durations Kling silently
# coerces away.
ANIMATION_DURATION_CHOICES = [5, 10]
ANIMATION_ASPECTS = ["9:16", "1:1", "16:9", "4:5"]


def _animation_root() -> Path:
    return get_output_dir()


def _new_animation_dir(project_name: str) -> tuple[Path, str]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _safe_name(project_name) or "animation"
    out_dir = _animation_root() / f"{ts}_animation_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "characters").mkdir(exist_ok=True)
    (out_dir / "shots").mkdir(exist_ok=True)
    return out_dir, ts


def load_animation_state(project_dir: Path) -> dict:
    state_path = Path(project_dir) / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_animation_state(project_dir: Path, state: dict) -> None:
    state_path = Path(project_dir) / "state.json"
    state_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _atomic_update_shot(project_dir: Path, shot_id: int, updates: dict) -> dict:
    """Atomically merge `updates` into state.shots[<shot_id>] and persist.
    Used by parallel shot workers so simultaneous saves can't lose each
    other's status / file deltas through a stale read."""
    with _animation_state_lock:
        state = load_animation_state(project_dir) or {}
        shots = state.setdefault("shots", {})
        shot = shots.setdefault(str(shot_id), {})
        # Drop None values to avoid wiping fields on partial updates.
        for k, v in updates.items():
            if v is not None:
                shot[k] = v
        save_animation_state(project_dir, state)
        return state


def list_animation_projects(root: Optional[Path] = None) -> list[dict]:
    """List all animation projects sorted by most recent. Each entry has
    `dir`, `state` (the loaded dict), and `mtime`."""
    root = root or _animation_root()
    if not root.exists():
        return []
    out: list[dict] = []
    for d in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir() or "_animation_" not in d.name:
            continue
        state = load_animation_state(d)
        if not state or state.get("type") != "animation":
            continue
        out.append({"dir": d, "state": state, "mtime": d.stat().st_mtime})
    return out


def latest_unfinished_animation() -> Optional[dict]:
    """Returns the most recent animation project where status != 'done',
    or None. Used by the AnimationPage to offer a resume button."""
    for entry in list_animation_projects():
        if (entry["state"].get("status") or "") != "done":
            return entry
    return None


def _round_duration(value) -> int:
    """Snap any incoming duration to the nearest Kling-supported choice
    (currently {5, 10}). Anything < 8 → 5, anything ≥ 8 → 10.
    Older state.json files (with values 3, 4, 6, 7) are coerced on load
    so Kling never receives a duration it would silently round itself.
    """
    try:
        d = int(round(float(value)))
    except Exception:
        d = ANIMATION_DEFAULT_DURATION
    if d < 8:
        return 5
    return 10


def create_animation_project(
    *,
    project_name: str,
    brand_name: str,
    brief_text: str,
    image_model: str,
    video_model: str,
    aspect_ratio: str,
    product_name: str = "",
    product_image: Optional[str] = None,
    style_refs: Optional[list[str]] = None,
    default_duration: int = ANIMATION_DEFAULT_DURATION,
    style: str = "realistic",
    style_custom_image: Optional[str] = None,
) -> Path:
    """Create a fresh project on disk with status='brief'. Copies the product
    and style-ref images into the project folder so the run is self-contained
    (and resumable even if the original files are moved)."""
    if not project_name.strip():
        raise ValueError("Project name is required.")
    if image_model not in IMAGE_MODELS:
        raise ValueError(f"Unknown image model: {image_model!r}")
    if video_model not in VIDEO_MODELS:
        raise ValueError(f"Unknown video model: {video_model!r}")

    out_dir, ts = _new_animation_dir(project_name)
    refs_dir = out_dir / "refs"
    refs_dir.mkdir(exist_ok=True)

    saved_product: dict = {"name": product_name.strip(), "image": ""}
    if product_image and Path(product_image).exists():
        src = Path(product_image)
        dst = refs_dir / f"product{src.suffix.lower() or '.png'}"
        try:
            shutil.copy2(src, dst)
            saved_product["image"] = str(dst)
        except Exception:
            pass

    saved_refs: list[str] = []
    for i, p in enumerate(style_refs or [], 1):
        sp = Path(p)
        if not sp.exists():
            continue
        dp = refs_dir / f"style_{i:02d}{sp.suffix.lower() or '.png'}"
        try:
            shutil.copy2(sp, dp)
            saved_refs.append(str(dp))
        except Exception:
            pass

    # Custom style ref image — copied into refs/ so the project stays
    # self-contained and resumable even if the user's source file moves.
    saved_custom_style = ""
    if style == "custom" and style_custom_image and Path(style_custom_image).exists():
        src = Path(style_custom_image)
        dst = refs_dir / f"style_custom{src.suffix.lower() or '.jpg'}"
        try:
            shutil.copy2(src, dst)
            saved_custom_style = str(dst)
        except Exception:
            pass

    state = {
        "type": "animation",
        "version": 1,
        "status": "brief",
        "timestamp": ts,
        "project_name": project_name.strip(),
        "brand": brand_name,
        "image_model": image_model,
        "video_model": video_model,
        "aspect_ratio": aspect_ratio,
        "default_duration": _round_duration(default_duration),
        "brief_text": brief_text,
        "product": saved_product,
        "style_refs": saved_refs,
        "style": style or "realistic",
        "style_custom_image": saved_custom_style,
        "scenario": {},
        "characters": {},
        "shots": {},
    }
    save_animation_state(out_dir, state)
    return out_dir


def run_animation_parse(
    project_dir: Path,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
) -> dict:
    """Step 1: parse the brief into a structured scenario via Claude.
    Mutates state.json: sets status='scenario', scenario={...},
    seeds characters{} and shots{} skeletons. Returns the new state."""
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    if not state:
        raise ValueError(f"No state.json in {project_dir}")
    brand = load_brands().get(state.get("brand", "")) or {}
    brand_dna = brand.get("dna", "")

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        raise RuntimeError(f"{provider.display_name} key not set.")

    on_log("INFO", f"Provider: {provider.display_name} · Model: claude-sonnet-4-6 (or Opus via Anthropic direct)")
    scenario = _parse_animation_brief(
        provider,
        brief_text=state.get("brief_text", ""),
        brand_dna=brand_dna,
        aspect_ratio=state.get("aspect_ratio", "9:16"),
        product_name=(state.get("product") or {}).get("name", ""),
    )

    # Seed characters/shots from scenario.
    characters: dict = {}
    for c in scenario.get("characters") or []:
        cid = (c.get("id") or "").strip()
        if not cid:
            continue
        characters[cid] = {
            "id": cid,
            "description": c.get("description", ""),
            "prompt": "",
            "image": "",
            "status": "draft",
        }
    shots: dict = {}
    for s in scenario.get("shots") or []:
        sid = int(s.get("id"))
        shots[str(sid)] = {
            "id": sid,
            "duration": _round_duration(s.get("duration", state.get("default_duration", 4))),
            "description": s.get("description", ""),
            "characters": [c for c in (s.get("characters") or []) if isinstance(c, str)],
            "shows_product": bool(s.get("shows_product", False)),
            "image_prompt": s.get("image_prompt", ""),
            "video_prompt": s.get("video_prompt", ""),
            "image_status": "pending",
            "video_status": "pending",
            "image_file": "",
            "video_file": "",
        }

    state["scenario"] = scenario
    state["characters"] = characters
    state["shots"] = shots
    state["status"] = "scenario"
    save_animation_state(project_dir, state)
    on_log("OK", f"Scenario parsed · {len(shots)} shots · {len(characters)} character(s)")
    return state


def run_animation_character(
    project_dir: Path,
    character_id: str,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
    image_model: Optional[str] = None,
    resolution: str = "1k",
) -> dict:
    """Step 2: generate (or regenerate) a single character portrait.
    Mutates state.characters[id] with image path + status."""
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    if not state:
        raise ValueError(f"No state.json in {project_dir}")
    char = state.get("characters", {}).get(character_id)
    if not char:
        raise ValueError(f"Character {character_id!r} not in scenario.")

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        raise RuntimeError(f"{provider.display_name} key not set.")
    img_model = image_model or state.get("image_model", DEFAULT_IMAGE_MODEL)
    aspect = state.get("aspect_ratio", "9:16")
    style = (state.get("scenario") or {}).get("style", "")

    label = f"char-{character_id}"
    on_log("INFO", f"[{label}] generating portrait prompt...")
    prompt = _gen_anim_char_prompt(
        provider,
        description=char.get("description", ""),
        style=style,
        aspect_ratio=aspect,
    )
    char["prompt"] = prompt
    char["status"] = "generating"
    save_animation_state(project_dir, state)

    try:
        on_log("INFO", f"[{label}] rendering portrait via {IMAGE_MODEL_LABELS.get(img_model, img_model)}...")
        # Use text-to-image when supported; fall back to call_image with no
        # input refs if the provider doesn't expose a separate t2i route.
        img_url = None
        if hasattr(provider, "call_image_t2i"):
            try:
                img_url = provider.call_image_t2i(
                    model=img_model, prompt=prompt,
                    resolution=resolution, aspect_ratio=aspect,
                    output_format="png", label=label,
                )
            except Exception as e:
                provider._log("WARN", f"[{label}] t2i failed ({e}); falling back to call_image with empty refs")
        if img_url is None:
            img_url = provider.call_image(
                model=img_model, prompt=prompt, image_urls=[],
                resolution=resolution, aspect_ratio=aspect, label=label,
            )
        dest = project_dir / "characters" / f"{character_id}.png"
        provider.download(img_url, dest)
        char["image"] = str(dest.relative_to(project_dir))
        char["status"] = "draft"
        on_log("OK", f"[{label}] saved {dest.name}")
    except Exception as e:
        char["status"] = "failed"
        char["error"] = str(e)
        on_log("ERR", f"[{label}] {e}")
    save_animation_state(project_dir, state)
    return state


def approve_animation_character(project_dir: Path, character_id: str) -> dict:
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    char = (state.get("characters") or {}).get(character_id)
    if not char:
        raise ValueError(f"Character {character_id!r} not found.")
    char["status"] = "approved"
    # Promote project status if all characters approved.
    chars = state.get("characters") or {}
    if chars and all((c.get("status") == "approved") for c in chars.values()):
        state["status"] = "characters"
    save_animation_state(project_dir, state)
    return state


def run_animation_shot_image(
    project_dir: Path,
    shot_id: int,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
    use_anchor: bool = True,
    resolution: str = "1k",
) -> dict:
    """Step 3 (anchor) and step 4 (other shots): generate one shot's image.

    For shot 1 (the anchor), we don't pass any anchor_image — the result IS
    the anchor. For shots 2..N, we pass shot 1's approved image as a style
    reference (`use_anchor=True`).
    """
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    if not state:
        raise ValueError(f"No state.json in {project_dir}")
    shots = state.get("shots") or {}
    shot = shots.get(str(shot_id))
    if not shot:
        raise ValueError(f"Shot {shot_id} not in scenario.")

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        raise RuntimeError(f"{provider.display_name} key not set.")
    img_model = state.get("image_model", DEFAULT_IMAGE_MODEL)
    aspect = state.get("aspect_ratio", "9:16")
    style = (state.get("scenario") or {}).get("style", "")

    # Build the list of input reference images (in order: anchor, characters,
    # product). The model receives them as `image_urls` (NB2/NB Pro accept up
    # to 8, GPT Image 2 up to 16).
    refs: list[Path] = []
    is_anchor_shot = (shot_id == 1)
    # Style ref is only attached to the anchor — subsequent shots inherit
    # the look through `anchor` itself, which already carries the styled
    # subject and setting. This keeps Kling's input clean for non-anchor
    # renders and avoids fighting between style ref and the anchor.
    style_key = (state.get("style") or "").strip()
    if is_anchor_shot and style_key and style_key != "realistic":
        if style_key == "custom":
            ref_path = state.get("style_custom_image") or ""
        else:
            from providers.prompts import resolve_style_ref
            ref_path = resolve_style_ref(style_key)
        if ref_path and Path(ref_path).exists():
            refs.append(Path(ref_path))
    if use_anchor and not is_anchor_shot:
        anchor = shots.get("1") or {}
        anchor_path = project_dir / anchor.get("image_file", "") if anchor.get("image_file") else None
        if anchor_path and anchor_path.exists():
            refs.append(anchor_path)
    for cid in (shot.get("characters") or []):
        c = (state.get("characters") or {}).get(cid)
        if not c:
            continue
        cp = project_dir / c.get("image", "") if c.get("image") else None
        if cp and cp.exists():
            refs.append(cp)
    if shot.get("shows_product"):
        prod = (state.get("product") or {}).get("image", "")
        if prod and Path(prod).exists():
            refs.append(Path(prod))

    label = f"shot_{shot_id:03d}"
    on_log("INFO", f"[{label}] refining image prompt with {len(refs)} reference(s)...")
    refined_prompt = _refine_anim_img(
        provider,
        draft_image_prompt=shot.get("image_prompt", ""),
        style=style,
        aspect_ratio=aspect,
        character_ids=shot.get("characters") or [],
        shows_product=bool(shot.get("shows_product")),
        has_anchor=(use_anchor and not is_anchor_shot and len([r for r in refs]) > 0
                    and (not is_anchor_shot)),
    )
    # Style guard rail — wrap the refined prompt in an explicit
    # style-transfer instruction so NanoBanana doesn't copy the SUBJECT of
    # the style reference (the model would otherwise pull the old-lady-in-
    # pink-robe character through every shot just because she's in the ref).
    if style_key and style_key != "realistic":
        from providers.prompts import ANIMATION_STYLES
        style_prefix = (
            (ANIMATION_STYLES.get(style_key) or {}).get("prompt", "")
            if style_key != "custom" else ""
        )
        # The first image_urls slot is the style reference (anchor only) or
        # the anchor itself (later shots inherit through it). Either way the
        # leak protection wording is the same: technique only, never subject.
        leak_guard = (
            "STYLE TRANSFER: the first reference image attached carries the "
            "rendering technique to apply (medium, materials, lighting "
            "treatment, color rendering). Do NOT copy its subject, "
            "character, pose, clothing, props, or setting — those come "
            "ONLY from the SCENE description below."
        )
        descriptor = f" Aesthetic: {style_prefix}" if style_prefix else ""
        refined_prompt = f"{leak_guard}{descriptor} SCENE: {refined_prompt}".strip()
    _atomic_update_shot(project_dir, shot_id, {
        "image_prompt": refined_prompt,
        "image_status": "generating",
    })
    shot["image_prompt"] = refined_prompt
    shot["image_status"] = "generating"

    try:
        # Upload refs.
        ref_urls: list[str] = []
        for p in refs:
            try:
                ref_urls.append(provider.upload_image(p))
            except Exception as e:
                provider._log("WARN", f"[{label}] skipped ref {p.name}: {e}")

        on_log("INFO", f"[{label}] rendering image via {IMAGE_MODEL_LABELS.get(img_model, img_model)}...")
        if ref_urls:
            img_url = provider.call_image(
                model=img_model, prompt=refined_prompt, image_urls=ref_urls,
                resolution=resolution, aspect_ratio=aspect, label=label,
            )
        else:
            # Anchor shot 1 with no references: text-to-image when available.
            if hasattr(provider, "call_image_t2i"):
                img_url = provider.call_image_t2i(
                    model=img_model, prompt=refined_prompt,
                    resolution=resolution, aspect_ratio=aspect,
                    output_format="png", label=label,
                )
            else:
                img_url = provider.call_image(
                    model=img_model, prompt=refined_prompt, image_urls=[],
                    resolution=resolution, aspect_ratio=aspect, label=label,
                )

        dest = project_dir / "shots" / f"shot_{shot_id:03d}.png"
        provider.download(img_url, dest)
        on_log("OK", f"[{label}] saved {dest.name}")
        return _atomic_update_shot(project_dir, shot_id, {
            "image_file": str(dest.relative_to(project_dir)),
            "image_status": "review",
            "image_error": "",
        })
    except Exception as e:
        on_log("ERR", f"[{label}] {e}")
        return _atomic_update_shot(project_dir, shot_id, {
            "image_status": "failed",
            "image_error": str(e),
        })


def approve_animation_shot_image(project_dir: Path, shot_id: int) -> dict:
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    shot = (state.get("shots") or {}).get(str(shot_id))
    if not shot:
        raise ValueError(f"Shot {shot_id} not found.")
    shot["image_status"] = "approved"
    # If this is shot 1 and we were on 'characters' status, promote to anchor approved.
    if shot_id == 1 and state.get("status") in ("characters", "anchor"):
        state["status"] = "anchor"
    save_animation_state(project_dir, state)
    return state


def run_animation_shot_video(
    project_dir: Path,
    shot_id: int,
    on_log: Callable[[str, str], None],
    *,
    provider_name: Optional[str] = None,
) -> dict:
    """Step 5: generate one shot's video clip via Kling 3 / Seedance 2.
    The shot's image must be approved first."""
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    if not state:
        raise ValueError(f"No state.json in {project_dir}")
    shot = (state.get("shots") or {}).get(str(shot_id))
    if not shot:
        raise ValueError(f"Shot {shot_id} not found.")
    if shot.get("image_status") != "approved":
        raise ValueError(f"Shot {shot_id}: image not approved yet.")
    img_path = project_dir / shot.get("image_file", "")
    if not img_path.exists():
        raise ValueError(f"Shot {shot_id}: image file missing on disk.")

    provider = get_provider(provider_name) if provider_name else get_active_provider()
    provider.set_logger(on_log)
    if not provider.is_configured():
        raise RuntimeError(f"{provider.display_name} key not set.")
    video_model = state.get("video_model", DEFAULT_VIDEO_MODEL)
    aspect = state.get("aspect_ratio", "9:16")
    duration = _round_duration(shot.get("duration", ANIMATION_DEFAULT_DURATION))

    label = f"shot_{shot_id:03d}_v"
    on_log("INFO", f"[{label}] refining video prompt...")
    refined_prompt = _refine_anim_vid(
        provider,
        draft_video_prompt=shot.get("video_prompt", ""),
        description=shot.get("description", ""),
        duration=duration,
        aspect_ratio=aspect,
        shows_product=bool(shot.get("shows_product")),
    )
    _atomic_update_shot(project_dir, shot_id, {
        "video_prompt": refined_prompt,
        "video_status": "generating",
    })
    shot["video_prompt"] = refined_prompt
    shot["video_status"] = "generating"

    try:
        on_log("INFO", f"[{label}] uploading frame...")
        ref_url = provider.upload_image(img_path)
        on_log("INFO", f"[{label}] rendering {duration}s clip via {VIDEO_MODEL_LABELS.get(video_model, video_model)}...")

        # Product reference locking (Kling only). Pass product image if present.
        prod_refs: list[str] = []
        prod_path = (state.get("product") or {}).get("image", "")
        if shot.get("shows_product") and prod_path and Path(prod_path).exists():
            try:
                prod_refs.append(provider.upload_image(Path(prod_path)))
            except Exception as e:
                provider._log("WARN", f"[{label}] product ref upload failed: {e}")

        video_url = provider.call_video(
            model=video_model, prompt=refined_prompt, image_url=ref_url,
            duration=duration, aspect_ratio=aspect, sound=False,
            product_reference_urls=prod_refs, label=label,
        )
        dest = project_dir / "shots" / f"shot_{shot_id:03d}.mp4"
        provider.download(video_url, dest)
        on_log("OK", f"[{label}] saved {dest.name}")
        return _atomic_update_shot(project_dir, shot_id, {
            "video_file": str(dest.relative_to(project_dir)),
            "video_status": "approved",
            "video_error": "",
        })
    except Exception as e:
        on_log("ERR", f"[{label}] {e}")
        return _atomic_update_shot(project_dir, shot_id, {
            "video_status": "failed",
            "video_error": str(e),
        })


def finalize_animation_project(project_dir: Path) -> dict:
    """Promote status to 'done' if all shots have an approved video."""
    project_dir = Path(project_dir)
    state = load_animation_state(project_dir)
    shots = state.get("shots") or {}
    if shots and all(s.get("video_status") == "approved" for s in shots.values()):
        state["status"] = "done"
        save_animation_state(project_dir, state)
    return state
