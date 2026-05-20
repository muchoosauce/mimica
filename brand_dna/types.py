"""Dataclasses for the Brand DNA generator pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


ImageTag = Literal["product", "lifestyle", "logo", "other"]


@dataclass
class Sources:
    urls: list[str] = field(default_factory=list)
    creative_files: list[Path] = field(default_factory=list)
    document_files: list[Path] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.urls or self.creative_files or self.document_files)


@dataclass
class CollectedImage:
    """An image candidate harvested from any source.

    Site-scraped images are kept in memory only (`data` set, `path` None) — we
    do not write site visuals to disk. Document-embedded images and user-staged
    creatives still live on disk (`path` set, `data` None).
    """
    path: Optional[Path] = None   # local file, when the image is persisted
    origin: str = ""              # "url:<url>", "creative", "document:<file>"
    width: int = 0
    height: int = 0
    note: str = ""                # optional descriptor (e.g. "screenshot", "embedded")
    tag: Optional[ImageTag] = None
    data: Optional[bytes] = None  # in-memory bytes (preferred over path when set)
    media_type: str = "image/jpeg"  # only meaningful when `data` is set


@dataclass
class ScrapedSite:
    url: str
    pages: list["ScrapedPage"] = field(default_factory=list)
    error: Optional[str] = None

    def all_text(self) -> str:
        return "\n\n".join(p.combined_text() for p in self.pages if p.text)


@dataclass
class ScrapedPage:
    url: str
    title: str = ""
    meta_description: str = ""
    text: str = ""
    images: list[CollectedImage] = field(default_factory=list)
    screenshot: Optional[CollectedImage] = None

    def combined_text(self) -> str:
        bits = [f"## {self.url}"]
        if self.title:
            bits.append(f"Title: {self.title}")
        if self.meta_description:
            bits.append(f"Meta: {self.meta_description}")
        if self.text:
            bits.append(self.text)
        return "\n".join(bits)


@dataclass
class ParsedDocument:
    path: Path
    text: str = ""
    images: list[CollectedImage] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class BrandDNAResult:
    dna_text: str                                      # markdown blob, ready for brands.json
    candidates: list[CollectedImage]                   # all collected images with tags
    sites: list[ScrapedSite] = field(default_factory=list)
    documents: list[ParsedDocument] = field(default_factory=list)
    creative_images: list[CollectedImage] = field(default_factory=list)
    output_dir: Optional[Path] = None                  # where the full run is saved
    raw_sections: dict = field(default_factory=dict)   # parsed Pydantic model as dict

    def product_candidates(self) -> list[CollectedImage]:
        return [c for c in self.candidates if c.tag == "product"]
