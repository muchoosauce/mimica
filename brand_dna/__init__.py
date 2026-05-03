"""Brand DNA Generator — orchestrates URL scraping, document parsing, creative
ingestion, and Claude vision analysis to produce a structured Brand DNA brief.

Public surface:
    Sources, BrandDNAResult, CollectedImage   — see types.py
    generate(sources, output_root, on_log) -> BrandDNAResult

Requires `ANTHROPIC_API_KEY` in the environment (no fallback).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .types import (
    BrandDNAResult,
    CollectedImage,
    ParsedDocument,
    ScrapedSite,
    Sources,
)


_PER_BUCKET_CAP = 10
_TOTAL_IMAGE_CAP = 30


def generate(
    sources: Sources,
    output_root: Optional[Path] = None,
    on_log: Callable[[str, str], None] = lambda lvl, msg: None,
    should_cancel: Callable[[], bool] = lambda: False,
) -> BrandDNAResult:
    """Run the full Brand DNA pipeline. Synchronous; call from a worker thread."""
    from .anthropic_client import AnthropicClient
    from .candidates import heuristic_filter
    from .documents import parse_document, stage_creative
    from .scraper import scrape_site

    if not AnthropicClient.is_configured():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it in Settings before running the Brand DNA generator."
        )
    if sources.is_empty():
        raise ValueError("Provide at least one source (URL, creative file, or document).")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_root).expanduser() if output_root else Path("outputs")
    out_dir = base / f"brand_dna_{ts}"
    img_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    on_log("INFO", f"Brand DNA run output: {out_dir}")

    # 1. Stage creatives (copy into the run dir)
    creative_images: list[CollectedImage] = []
    for cf in sources.creative_files:
        if should_cancel():
            return _abort(out_dir)
        cf = Path(cf)
        if not cf.exists():
            on_log("WARN", f"Creative not found: {cf}")
            continue
        try:
            ci = stage_creative(cf, img_dir)
            creative_images.append(ci)
            on_log("OK", f"Staged creative {cf.name}")
        except Exception as e:
            on_log("ERR", f"Failed staging creative {cf.name}: {e}")

    # 2. Parse documents
    documents: list[ParsedDocument] = []
    for df in sources.document_files:
        if should_cancel():
            return _abort(out_dir)
        df = Path(df)
        if not df.exists():
            on_log("WARN", f"Document not found: {df}")
            continue
        on_log("INFO", f"Parsing document {df.name}")
        parsed = parse_document(df, img_dir)
        if parsed.error:
            on_log("ERR", f"  {parsed.error}")
        else:
            on_log("OK", f"  {len(parsed.text)} chars + {len(parsed.images)} images")
        documents.append(parsed)

    # 3. Scrape URLs
    sites: list[ScrapedSite] = []
    for url in sources.urls:
        if should_cancel():
            return _abort(out_dir)
        site_dir = img_dir / _safe_slug(url)
        site_dir.mkdir(parents=True, exist_ok=True)
        site = scrape_site(url, site_dir, on_log)
        sites.append(site)

    if should_cancel():
        return _abort(out_dir)

    # 4. Pick images for Claude (≤10 per bucket, ≤30 total)
    url_pick = _pick_url_images(sites, _PER_BUCKET_CAP)
    creative_pick = creative_images[:_PER_BUCKET_CAP]
    doc_pick = _pick_doc_images(documents, _PER_BUCKET_CAP)
    selected = (url_pick + creative_pick + doc_pick)[:_TOTAL_IMAGE_CAP]
    on_log("INFO", f"Sending {len(selected)} images to Claude "
                   f"(URL: {len(url_pick)}, creative: {len(creative_pick)}, doc: {len(doc_pick)})")

    # 5. Compile text
    text_parts: list[str] = []
    for site in sites:
        if site.error:
            text_parts.append(f"# Source URL: {site.url}\n[scrape error: {site.error}]")
            continue
        if site.pages:
            text_parts.append(f"# Source URL: {site.url}\n{site.all_text()}")
    for doc in documents:
        if doc.error:
            text_parts.append(f"# Document: {doc.path.name}\n[parse error: {doc.error}]")
            continue
        if doc.text:
            text_parts.append(f"# Document: {doc.path.name}\n{doc.text}")
    if creative_images:
        text_parts.append(
            f"# Creative assets: {len(creative_images)} images provided "
            "(see attached images — analyse them for visual style, palette, layout, product)."
        )
    compiled = "\n\n".join(text_parts).strip()
    on_log("INFO", f"Compiled text: {len(compiled)} chars")

    # 6. Call Claude for the DNA
    client = AnthropicClient()
    if should_cancel():
        return _abort(out_dir)
    dna_model = client.generate_dna(compiled, selected, on_log=on_log)
    dna_md = dna_model.to_markdown()
    (out_dir / "dna.md").write_text(dna_md)
    on_log("OK", "Brand DNA generated")

    # 7. Heuristic-filter all collected non-screenshot images, then LLM-tag them
    candidates = _collect_for_tagging(sites, creative_images, documents)
    candidates = heuristic_filter(candidates, cap=20)
    if candidates and not should_cancel():
        try:
            tags = client.tag_images(candidates, on_log=on_log)
            for img, tag in zip(candidates, tags):
                img.tag = tag
            on_log("OK", f"Tagged {len(candidates)} candidates "
                          f"({sum(1 for c in candidates if c.tag == 'product')} product)")
        except Exception as e:
            on_log("WARN", f"Tagging failed: {e}")

    # 8. Save raw run for debug + return
    raw = {
        "timestamp": ts,
        "sources": {
            "urls": list(sources.urls),
            "creative_files": [str(p) for p in sources.creative_files],
            "document_files": [str(p) for p in sources.document_files],
        },
        "sites": [_site_to_dict(s) for s in sites],
        "documents": [_doc_to_dict(d) for d in documents],
        "creative_images": [_img_to_dict(i) for i in creative_images],
        "candidates": [_img_to_dict(c) for c in candidates],
        "dna_sections": dna_model.model_dump(),
    }
    (out_dir / "raw.json").write_text(json.dumps(raw, indent=2, default=str))

    return BrandDNAResult(
        dna_text=dna_md,
        candidates=candidates,
        sites=sites,
        documents=documents,
        creative_images=creative_images,
        output_dir=out_dir,
        raw_sections=dna_model.model_dump(),
    )


# ─── helpers ───────────────────────────────────────────────────────────────

def _abort(out_dir: Path) -> BrandDNAResult:
    return BrandDNAResult(dna_text="", candidates=[], output_dir=out_dir)


def _safe_slug(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "site").replace(".", "_")
    return host[:48]


def _pick_url_images(sites: list[ScrapedSite], cap: int) -> list[CollectedImage]:
    """Prefer one screenshot per page first (richer signal), then fill with <img>."""
    out: list[CollectedImage] = []
    for site in sites:
        for page in site.pages:
            if page.screenshot is not None:
                out.append(page.screenshot)
                if len(out) >= cap:
                    return out
    if len(out) >= cap:
        return out
    flat_imgs: list[CollectedImage] = []
    for site in sites:
        for page in site.pages:
            flat_imgs.extend(page.images)
    flat_imgs.sort(key=lambda i: (i.width or 0) * (i.height or 0), reverse=True)
    for img in flat_imgs:
        if len(out) >= cap:
            break
        out.append(img)
    return out[:cap]


def _pick_doc_images(documents: list[ParsedDocument], cap: int) -> list[CollectedImage]:
    flat: list[CollectedImage] = []
    for d in documents:
        flat.extend(d.images)
    return flat[:cap]


def _collect_for_tagging(sites, creatives, documents) -> list[CollectedImage]:
    out: list[CollectedImage] = []
    for site in sites:
        for page in site.pages:
            out.extend(page.images)
    out.extend(creatives)
    for d in documents:
        out.extend(d.images)
    return out


def _img_to_dict(img: CollectedImage) -> dict:
    return {
        "path": str(img.path), "origin": img.origin,
        "width": img.width, "height": img.height,
        "note": img.note, "tag": img.tag,
    }


def _site_to_dict(site: ScrapedSite) -> dict:
    return {
        "url": site.url,
        "error": site.error,
        "pages": [
            {
                "url": p.url, "title": p.title, "meta_description": p.meta_description,
                "text_chars": len(p.text),
                "image_count": len(p.images),
                "screenshot": str(p.screenshot.path) if p.screenshot else None,
            }
            for p in site.pages
        ],
    }


def _doc_to_dict(doc: ParsedDocument) -> dict:
    return {
        "path": str(doc.path),
        "error": doc.error,
        "text_chars": len(doc.text),
        "images": [_img_to_dict(i) for i in doc.images],
    }


__all__ = [
    "Sources",
    "BrandDNAResult",
    "CollectedImage",
    "generate",
]
