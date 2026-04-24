"""Programmatic wrapper around ad_variator.py for the GUI."""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv, set_key

_here = Path(__file__).resolve().parent.parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

import ad_variator as av

load_dotenv()

COST_PER_IMAGE = {"1k": 0.06, "2k": 0.09, "4k": 0.12}
RESOLUTIONS = ["1k", "2k", "4k"]
ASPECTS = ["1:1", "4:5", "9:16", "16:9", "3:2", "2:3", "3:4", "4:3"]
LANGUAGES = ["English", "French", "Spanish", "German", "Italian",
             "Portuguese", "Dutch", "Arabic"]
LANG_SLUG = {
    "English": "en", "French": "fr", "Spanish": "es", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Dutch": "nl", "Arabic": "ar",
}
AD_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

BRANDS_FILE = _here / "brands.json"
BRANDS_IMG_DIR = _here / "brands" / "images"

ADAPT_SYSTEM_PROMPT = """You are an expert ad adaptation prompt engineer for NanoBanana 2 (image-to-image edit mode).

You receive a reference ad image and a Brand DNA (text describing a brand and its product). You must output exactly ONE NanoBanana 2 prompt that recreates the reference ad's composition for the brand described in the Brand DNA.

At generation time NanoBanana will receive:
- Reference image 1: the source ad (composition / layout / framing / text zone placement to replicate)
- Reference images 2, 3, 4, …: the brand's target product forms (pouch, stick, bottle, sachet, capsule, etc.). There may be one or several target product images.

Rules:
1. The first character of your output must be ^ (caret).
2. Explicitly mention "reference image 1" (composition) and "reference images 2+" (target product forms). If you know the count of target product images, cite them precisely (e.g., "reference images 2 and 3").
3. Keep the composition, framing, crop, product placement, and text zone placement IDENTICAL to reference image 1 — including the NUMBER of visible product forms (if the source shows a pouch + a stick, the output must show a pouch + a stick, not just one).
4. Product mapping — CRITICAL:
   - Every visible product in the generated ad MUST come from reference images 2+.
   - If the source ad shows multiple product forms (e.g., pouch + stick packet), match each source form to the closest target form in reference images 2+ (pouch → target pouch, stick → target stick).
   - If the source ad shows a form for which NO equivalent exists in reference images 2+, replace it with the primary target form (reference image 2) OR omit that secondary product entirely — NEVER invent, hallucinate, or keep the source product.
   - Preserve each target product's exact shape, packaging, logo, and color as shown in its reference image.
5. Apply the Brand DNA:
   - Color palette: swap background / accent / gradients to the brand palette.
   - Typography: swap any visible font style to the brand's typography.
   - Copy / headline / CTA: rewrite literal copy (never placeholders) in the brand's tone of voice AND in the target language specified at runtime.
   - Brand marks (wordmark, logo): include only if the DNA specifies them, otherwise none.
6. Strict negatives (repeat them in the prompt): "No foreign brand names. No competitor logos. No secondary products, sachets, sticks, or packaging that are not present in reference images 2+. No invented packaging. No leftover source-ad product."
7. End every prompt with: "Every product shown must exactly match one of reference images 2+. Do not render any product, logo, packaging, or brand mark that is not in reference images 2+."

CONTENT SAFETY (critical — the image model's content filter will reject and return nothing if the prompt violates Google Generative AI policy):
- Never use literal medical / clinical / therapeutic claims. Rewrite them into neutral lifestyle or wellness language BEFORE they appear in the output prompt.
  - "hormonal imbalance" / "hormones changed" → "everyday balance" / "feeling off-sync"
  - "clinically formulated" / "clinically proven" → "expertly crafted" / "thoughtfully made"
  - "cure / treat / heal / diagnose" → "support / help / feel / enjoy"
  - Disease or disorder names (migraine, depression, anxiety, menopause, PMS, insomnia, acne, diabetes, etc.) → generic moods ("tired", "foggy", "restless", "off-balance", "low energy").
- No before/after body transformations. Replace with mood or lifestyle shifts ("tired → bright", "foggy → focused"), NOT physical changes.
- No weight-loss language, no specific body measurements, no body-part focus beyond what the setting requires, no anatomy close-ups.
- No nudity, no suggestive posing, no implied adult content.
- No names of real public figures, athletes, celebrities, politicians.
- No political, religious, violent, weapon, or drug imagery or language.
- If the reference ad's copy contains any of the above, REWRITE it into neutral lifestyle/wellness copy that preserves the emotional beat but strips the medical / anatomical / claim framing.
- Scenes should read as lifestyle photography, not clinical or pharmaceutical documentation.

CLOTHING & SETTING SAFETY (applies to any human figure in the scene):
- Describe every figure as fully dressed in modest, everyday clothing. Default attire: long-sleeve top (shirt, sweater, turtleneck, blouse) + full-length trousers / jeans / midi skirt with opaque tights. Closed shoes.
- If the reference ad shows pajamas, sleepwear, nightgown, lingerie, underwear, tank top, crop top, swimwear, bikini, bare shoulders, bare chest, cleavage, exposed midriff, short shorts, or any revealing outfit → REPLACE it in the output prompt with modest everyday clothing (e.g., "woman in a cream long-sleeve knit sweater and straight-leg jeans").
- No intimate body contact, no embraces on a bed, no suggestive poses. Replace intimate embraces with casual interactions: sitting next to each other on a sofa, standing together in a kitchen, walking side by side.
- Prefer neutral public-ish settings: living room sofa, kitchen, office, studio, park, street. If the reference ad uses a bedroom, bathroom, or bed scene → relocate to a living room sofa, kitchen counter, or studio with neutral furniture. Do NOT describe beds, bedsheets, pillows, bedroom lamps, headboards, or nightstands.

Output: exactly ONE prompt, nothing else. No commentary, no numbering, no headers, no explanations."""


def _safe_name(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s.strip())
    return s.strip("_").lower() or "brand"


MUAPI_UPLOAD_LIMIT = 10 * 1024 * 1024  # 10 MB


def _prepare_upload(path: Path, tmpdir: Path) -> Path:
    """Return `path` if under the MuAPI size limit, else a compressed JPEG copy."""
    try:
        sz = path.stat().st_size
    except FileNotFoundError:
        return path
    if sz <= MUAPI_UPLOAD_LIMIT:
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
        if tmp.stat().st_size <= MUAPI_UPLOAD_LIMIT:
            return tmp
        quality = max(40, quality - 15)
        max_dim = max(1200, int(max_dim * 0.85))
    return tmp


@contextmanager
def _patched_av(on_log: Callable[[str, str], None]):
    tmpdir = tempfile.TemporaryDirectory(prefix="advar_")
    tmp_path = Path(tmpdir.name)
    orig_log = av.log
    orig_upload = av.upload_image
    orig_call = av.call_prediction
    av.log = lambda lvl, msg: on_log(lvl, msg)

    def _safe_call(model_id, payload, label):
        last_err = None
        for attempt in range(3):
            try:
                return orig_call(model_id, payload, label)
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                transient = any(s in msg for s in (
                    "nameresolutionerror", "max retries", "connection aborted",
                    "connection reset", "timed out", "temporary failure", "remote end closed",
                ))
                if transient and attempt < 2:
                    av.log("WARN", f"{label} network error, retry {attempt+1}/3 in {2**attempt}s")
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise last_err

    def _safe_upload(p):
        p = Path(p)
        prepped = _prepare_upload(p, tmp_path)
        if prepped != p:
            av.log("INFO",
                   f"Compressed {p.name} ({p.stat().st_size/1e6:.1f}MB → "
                   f"{prepped.stat().st_size/1e6:.1f}MB) to fit 10MB limit")
        last_err = None
        for attempt in range(3):
            try:
                return orig_upload(prepped)
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                transient = any(s in msg for s in (
                    "nameresolutionerror", "max retries", "connection aborted",
                    "connection reset", "timed out", "temporary failure", "remote end closed",
                ))
                if transient and attempt < 2:
                    av.log("WARN", f"Upload network error on {p.name}, retry {attempt+1}/3 in {2**attempt}s")
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise last_err  # unreachable

    av.upload_image = _safe_upload
    av.call_prediction = _safe_call
    try:
        yield
    finally:
        av.log = orig_log
        av.upload_image = orig_upload
        av.call_prediction = orig_call
        try: tmpdir.cleanup()
        except Exception: pass


def save_api_key(key: str):
    env_path = _here / ".env"
    env_path.touch(exist_ok=True)
    set_key(str(env_path), "MUAPI_KEY", key.strip())
    os.environ["MUAPI_KEY"] = key.strip()
    av.MUAPI_KEY = key.strip()


def get_api_key() -> str:
    return os.getenv("MUAPI_KEY") or av.MUAPI_KEY or ""


DEFAULT_OUTPUT_DIR = _here / "outputs"


def get_output_dir() -> Path:
    v = (os.getenv("OUTPUT_DIR") or "").strip()
    return Path(v).expanduser() if v else DEFAULT_OUTPUT_DIR


def save_output_dir(path: str):
    env_path = _here / ".env"
    env_path.touch(exist_ok=True)
    set_key(str(env_path), "OUTPUT_DIR", path.strip())
    os.environ["OUTPUT_DIR"] = path.strip()


def cost_for_run(run: dict) -> float:
    res = (run.get("params") or {}).get("resolution", "1k")
    done = sum(1 for r in run.get("results", []) if r.get("status") == "ok")
    return COST_PER_IMAGE.get(res, 0.06) * done


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
        # clean old brand's images not reused
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
        # clean this brand's images that are no longer referenced
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
) -> Optional[Path]:
    if not av.MUAPI_KEY:
        av.MUAPI_KEY = get_api_key()
    if not av.MUAPI_KEY:
        on_log("ERR", "MUAPI_KEY not set. Open Settings and add your key.")
        return None

    ref_path = Path(image_path).expanduser().resolve()
    if not ref_path.exists():
        on_log("ERR", f"File not found: {ref_path}")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else get_output_dir()
    out_dir = base / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    on_out_dir(out_dir)
    on_log("INFO", f"Output: {out_dir}")

    aspects = aspects or ["1:1"]
    languages = languages or ["English"]
    variant = len(aspects) > 1 or len(languages) > 1

    with _patched_av(on_log):
        try:
            ref_url = av.upload_image(ref_path)
            if should_cancel():
                return out_dir

            prompts_by_lang: dict[str, list[str]] = {}
            for lang in languages:
                if should_cancel():
                    return out_dir
                prompts_by_lang[lang] = av.generate_prompts(ref_url, n, language=lang)

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
                def _payload(p):
                    return {
                        "prompt": p, "images_list": [ref_url],
                        "resolution": resolution, "aspect_ratio": aspect,
                        "output_format": "png",
                    }
                label = f"var_{idx:02d}{suffix}"
                av.log("INFO", f"[{label}] generating ({lang} · {aspect})...")
                softened = False
                try:
                    try:
                        out = av.call_prediction(av.IMAGE_MODEL, _payload(prompt), label)
                    except Exception as e:
                        if _is_censorship_error(e):
                            av.log("WARN", f"[{label}] blocked by content filter — rewriting prompt and retrying")
                            try:
                                prompt = _soften_prompt(prompt, ref_url)
                                softened = True
                                out = av.call_prediction(av.IMAGE_MODEL, _payload(prompt), label + "-retry")
                            except Exception as e2:
                                raise e2 from e
                        else:
                            raise
                    img_url = av._first_url(out)
                    if not img_url:
                        raise RuntimeError(f"No image URL in output: {out}")
                    dest = out_dir / file_name
                    av._download(img_url, dest)
                    av.log("OK", f"[{label}] saved {dest.name}" + (" (after softening)" if softened else ""))
                    return {"index": idx, "aspect": aspect, "language": lang, "status": "ok",
                            "prompt": prompt, "image_url": img_url, "file": dest.name,
                            "softened": softened}
                except Exception as e:
                    if _is_censorship_error(e):
                        av.log("ERR", f"[{label}] blocked by content filter (after retry). Try softer reference or brand copy.")
                    else:
                        av.log("ERR", f"[{label}] {e}")
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
                    "llm_model": av.LLM_MODEL,
                    "image_model": av.IMAGE_MODEL,
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

def _generate_adapt_prompt(ad_url: str, brand_dna: str, product_count: int = 1,
                            language: str = "English") -> str:
    if product_count <= 1:
        forms_note = "The brand has 1 target product form (reference image 2)."
    else:
        imgs = ", ".join(str(i) for i in range(2, 2 + product_count))
        forms_note = (
            f"The brand has {product_count} target product forms (reference images {imgs}). "
            f"If the source ad shows several product forms, map each to the closest target form; "
            f"if a source form has no target equivalent, use reference image 2 or omit the secondary product."
        )
    payload = {
        "prompt": (
            f"Brand DNA:\n{brand_dna}\n\n"
            f"{forms_note}\n\n"
            f"Target language for every visible text, headline, body copy, tagline and CTA "
            f"inside the generated image: {language}. Write real literal copy in {language}, never placeholders.\n\n"
            "Reference ad is attached. Generate exactly ONE NanoBanana 2 prompt "
            "to recreate its composition for this brand, following all rules."
        ),
        "image_url": ad_url,
        "system_prompt": ADAPT_SYSTEM_PROMPT,
    }
    out = av.call_prediction(av.LLM_MODEL, payload, f"LLM-adapt-{LANG_SLUG.get(language, language[:2].lower())}")
    text = av._coerce_text(out)
    prompts = av._parse_prompts(text)
    if prompts:
        return prompts[0]
    text = text.strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def _is_censorship_error(e: Exception) -> bool:
    m = str(e).lower()
    return any(s in m for s in (
        "prohibited use", "content policy", "filtered out", "violated",
        "generative ai policy", "safety", "filtered because",
    ))


_SOFTENER_SYSTEM = """You rewrite image-generation prompts to pass strict Google Generative AI content filters.

Your first attempt triggered the filter. Rewrite the prompt so it passes, by applying ALL of the following transformations:

1. Strip all medical / clinical / therapeutic / hormonal / disease / anatomical / weight-loss / before-after-body language. Replace with neutral lifestyle or wellness wording.

2. DRESS every human figure in modest, fully covered everyday clothing. REPLACE — aggressively:
   - Pajamas / sleepwear / nightgown / lingerie / underwear → long-sleeve button-up shirt + full-length trousers, OR a long-sleeve knit sweater + straight-leg jeans. Neutral colors (beige, cream, grey, soft blue).
   - Tank top / crop top / low necklines / bikini / swimwear / tube top → crewneck or turtleneck long-sleeve top, no skin exposure.
   - Bare shoulders / bare chest / cleavage / exposed midriff / bare legs → fully covered: long sleeves, high neckline, long pants or opaque tights.
   - Any hint of nudity, implied nudity, or revealing outfit → fully dressed in everyday casual or business casual. Closed shoes.

3. RELOCATE intimate / private settings to neutral public-ish ones:
   - Bedroom / bed / bedsheets / pillows / headboard / nightstand → living room sofa, kitchen counter, office desk, outdoor park bench, studio with neutral backdrop.
   - Bathroom / bath / shower / mirror-in-bathrobe → kitchen sink, vanity counter with a mug, neutral studio.

4. DE-INTIMIZE poses and interactions:
   - Intimate embrace / hug on bed / romantic pose → sitting side by side on a sofa, standing casually in a kitchen, walking in a park, smiling toward camera from a distance.
   - Suggestive expressions / smoldering looks → natural warm smile, everyday calm expression.

5. Keep unchanged: composition structure, product description, brand palette, typography direction, copy language, text zone placement, brand intent, and the list of product references (reference image 1, reference images 2+).

6. Keep the ^ first character.

7. Output ONLY the rewritten prompt. No explanations, no headers, no commentary."""


def _soften_prompt(prompt: str, ad_url: str) -> str:
    payload = {
        "prompt": "Rewrite this NanoBanana prompt to pass content filters:\n\n" + prompt,
        "image_url": ad_url,
        "system_prompt": _SOFTENER_SYSTEM,
    }
    out = av.call_prediction(av.LLM_MODEL, payload, "LLM-soften")
    text = av._coerce_text(out).strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def _adapt_image(idx: int, prompt: str, ad_url: str, product_urls: list[str],
                 resolution: str, aspect: str, language: str, out_dir: Path,
                 source_name: str, multi_aspect: bool, multi_lang: bool) -> dict:
    bits = []
    if multi_lang: bits.append(LANG_SLUG.get(language, language[:2].lower()))
    if multi_aspect: bits.append(_aspect_slug(aspect))
    suffix = ("_" + "_".join(bits)) if bits else ""
    label = f"adapt_{idx:02d}{suffix}"
    av.log("INFO", f"[{label}] generating ({source_name} · {language} · {aspect})...")

    def _payload(p):
        return {
            "prompt": p,
            "images_list": [ad_url, *product_urls],
            "resolution": resolution,
            "aspect_ratio": aspect,
            "output_format": "png",
        }

    attempts = [("initial", prompt)]
    try:
        try:
            out = av.call_prediction(av.IMAGE_MODEL, _payload(prompt), label)
        except Exception as e:
            if _is_censorship_error(e):
                av.log("WARN", f"[{label}] blocked by content filter — rewriting prompt and retrying")
                try:
                    softer = _soften_prompt(prompt, ad_url)
                    attempts.append(("softened", softer))
                    out = av.call_prediction(av.IMAGE_MODEL, _payload(softer), label + "-retry")
                    prompt = softer
                except Exception as e2:
                    raise e2 from e
            else:
                raise
        img_url = av._first_url(out)
        if not img_url:
            raise RuntimeError(f"No image URL in output: {out}")
        dest = out_dir / f"adapt_{idx:02d}{suffix}.png"
        av._download(img_url, dest)
        av.log("OK", f"[{label}] saved {dest.name}" + (" (after softening)" if len(attempts) > 1 else ""))
        return {
            "index": idx, "aspect": aspect, "language": language, "status": "ok",
            "prompt": prompt, "image_url": img_url, "file": dest.name,
            "source": source_name, "softened": len(attempts) > 1,
        }
    except Exception as e:
        if _is_censorship_error(e):
            av.log("ERR", f"[{label}] blocked by content filter (after retry). Simplify brand DNA copy or remove medical claims.")
        else:
            av.log("ERR", f"[{label}] {e}")
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
) -> Optional[Path]:
    if not av.MUAPI_KEY:
        av.MUAPI_KEY = get_api_key()
    if not av.MUAPI_KEY:
        on_log("ERR", "MUAPI_KEY not set. Open Settings and add your key.")
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
    on_log(
        "INFO",
        f"Adapting {len(ads)} ads × {len(languages)} lang × {len(aspects)} aspect"
        f"{'s' if multi_aspect else ''} for '{brand_name}' ({workers} workers)",
    )

    with _patched_av(on_log):
        try:
            on_log("INFO", f"Uploading {len(product_paths)} target product image(s)...")
            product_urls: list[str] = []
            for pp in product_paths:
                product_urls.append(av.upload_image(pp))

            # Stage 1: upload each ad once.
            ad_urls: dict[int, str] = {}
            def upload_one(pair):
                idx, ad = pair
                if should_cancel(): return idx, None
                try:
                    return idx, av.upload_image(ad)
                except Exception as e:
                    av.log("ERR", f"[upload_{idx:02d}] {e}")
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
                        ad_url, brand["dna"],
                        product_count=len(product_urls), language=lang
                    )
                except Exception as e:
                    av.log("ERR", f"[prompt_{idx:02d}_{LANG_SLUG.get(lang, lang[:2].lower())}] {e}")
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
                return _adapt_image(idx, prompt, ad_urls[idx], product_urls,
                                    resolution, aspect, lang, out_dir, source_name,
                                    multi_aspect, multi_lang)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                for fut in as_completed([pool.submit(gen_img, j) for j in jobs]):
                    r = fut.result()
                    results.append(r)
                    on_result(r)

            # Mark ads/langs that never produced prompts
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
                    "llm_model": av.LLM_MODEL,
                    "image_model": av.IMAGE_MODEL,
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
