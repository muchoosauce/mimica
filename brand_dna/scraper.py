"""Shallow web scraper using Playwright (Chromium) + BeautifulSoup.

Scrapes the homepage and common secondary paths, captures full-page screenshots
for vision analysis, and downloads <img> assets for product candidate detection.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from .types import CollectedImage, ScrapedPage, ScrapedSite


_SECONDARY_PATHS = [
    "/about", "/about-us", "/our-story", "/story",
    "/shop", "/products", "/collections/all",
    "/faq", "/contact",
]
_PAGE_TIMEOUT_MS = 20_000
_MAX_PAGES = 6
_MAX_IMG_BYTES = 5 * 1024 * 1024
_MIN_IMG_DIM = 100
_TEXT_LIMIT_PER_PAGE = 8000  # chars
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)


def scrape_site(
    url: str,
    image_dir: Path,
    on_log=lambda lvl, msg: None,
) -> ScrapedSite:
    """Scrape one site shallowly. Returns ScrapedSite with .error on fatal failure."""
    site = ScrapedSite(url=url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        site.error = f"playwright not installed: {e}"
        return site

    paths = _candidate_paths(url)
    image_dir.mkdir(parents=True, exist_ok=True)
    on_log("INFO", f"Scraping {url} (up to {len(paths)} pages)")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
                pg = context.new_page()
                for i, path in enumerate(paths):
                    full = urljoin(url, path)
                    try:
                        page = _scrape_page(pg, full, image_dir, on_log, page_idx=i)
                        if page is not None:
                            site.pages.append(page)
                    except Exception as e:
                        on_log("WARN", f"  {full}: {e}")
                context.close()
            finally:
                browser.close()
    except Exception as e:
        site.error = f"playwright failure: {e}"
        on_log("ERR", f"  {url}: {e}")
        return site

    on_log("OK", f"Scraped {len(site.pages)} pages, "
                 f"{sum(len(p.images) for p in site.pages)} images, "
                 f"{sum(1 for p in site.pages if p.screenshot)} screenshots")
    return site


def _candidate_paths(url: str) -> list[str]:
    paths = ["/"]
    for p in _SECONDARY_PATHS:
        if p not in paths:
            paths.append(p)
    return paths[:_MAX_PAGES]


def _scrape_page(pw_page, full_url: str, image_dir: Path,
                 on_log, page_idx: int) -> Optional[ScrapedPage]:
    response = pw_page.goto(full_url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT_MS)
    if response is None:
        return None
    if response.status >= 400:
        return None

    try:
        pw_page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass

    html = pw_page.content()
    title = pw_page.title() or ""
    meta_desc = ""
    try:
        meta_desc = pw_page.evaluate(
            "document.querySelector('meta[name=description]')?.content || ''"
        ) or ""
    except Exception:
        pass

    text = _extract_text(html)
    text = text[:_TEXT_LIMIT_PER_PAGE]

    page = ScrapedPage(
        url=full_url,
        title=title,
        meta_description=meta_desc,
        text=text,
    )

    # Screenshot full page (heavy on long pages — clip to viewport-height-ish)
    try:
        shot_path = image_dir / f"screenshot_{page_idx:02d}.jpg"
        pw_page.screenshot(path=str(shot_path), full_page=True, type="jpeg", quality=80)
        page.screenshot = CollectedImage(
            path=shot_path,
            origin=f"url:{full_url}",
            note="screenshot",
        )
    except Exception as e:
        on_log("WARN", f"  screenshot failed for {full_url}: {e}")

    # <img> harvest
    try:
        img_urls = pw_page.evaluate("""
            () => Array.from(document.querySelectorAll('img'))
                .map(img => img.currentSrc || img.src)
                .filter(Boolean)
        """) or []
    except Exception:
        img_urls = []

    seen = set()
    for img_url in img_urls:
        absolute = urljoin(full_url, img_url)
        if absolute in seen:
            continue
        seen.add(absolute)
        ci = _download_image(absolute, image_dir, page_idx)
        if ci is not None:
            page.images.append(ci)
        if len(page.images) >= 25:  # cap per page
            break

    on_log("INFO", f"  {full_url} → {len(page.images)} images")
    return page


def _download_image(img_url: str, image_dir: Path, page_idx: int) -> Optional[CollectedImage]:
    if not img_url.startswith(("http://", "https://")):
        return None
    if img_url.endswith(".svg") or "data:image/svg" in img_url:
        return None
    try:
        r = requests.get(img_url, headers={"User-Agent": _USER_AGENT}, timeout=20, stream=True)
    except Exception:
        return None
    if r.status_code >= 400:
        return None

    content_type = (r.headers.get("Content-Type") or "").lower()
    if not content_type.startswith("image/"):
        return None
    ext = content_type.split("/")[-1].split(";")[0] or "jpg"
    if ext == "jpeg":
        ext = "jpg"
    if ext not in ("jpg", "png", "webp", "gif"):
        return None

    name = re.sub(r"[^A-Za-z0-9_.-]", "_", urlparse(img_url).path.split("/")[-1] or "img")
    out = image_dir / f"img_p{page_idx:02d}_{abs(hash(img_url)) % 10**8}_{name}"
    if not out.suffix:
        out = out.with_suffix(f".{ext}")
    try:
        size = 0
        with open(out, "wb") as f:
            for chunk in r.iter_content(8192):
                if not chunk:
                    continue
                size += len(chunk)
                if size > _MAX_IMG_BYTES:
                    f.close()
                    out.unlink(missing_ok=True)
                    return None
                f.write(chunk)
    except Exception:
        return None

    w, h = _image_dims(out)
    if max(w, h) < _MIN_IMG_DIM:
        out.unlink(missing_ok=True)
        return None
    return CollectedImage(path=out, origin=f"url:{img_url}", width=w, height=h)


def _image_dims(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _extract_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html[:_TEXT_LIMIT_PER_PAGE]

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header nav", "footer"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
