#!/usr/bin/env python3
"""Render Mimica.icns from the Caveat font + a violet→pink gradient.

Run from the repo root:  python3 wrapper/build_icon.py

Pillow does the rasterisation (white rounded square + gradient-filled
"Mimica" text). `iconutil` (built into macOS) packs the .iconset into
.icns. The output goes to wrapper/AppIcon.icns where build_dmg.command
picks it up automatically.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. From the repo root:", file=sys.stderr)
    print("  python3 -m pip install pillow", file=sys.stderr)
    sys.exit(1)


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FONT_PATH = REPO / "gui" / "fonts" / "Caveat-Medium.ttf"
ICONSET_DIR = HERE / "AppIcon.iconset"
ICNS_PATH = HERE / "AppIcon.icns"

ACCENT_VIOLET = (124, 92, 255)   # #7C5CFF
ACCENT_PINK   = (236, 72, 153)   # #EC4899


def make_gradient(width: int, height: int) -> Image.Image:
    """Horizontal violet → pink gradient."""
    grad = Image.new("RGB", (width, height), 0)
    pixels = grad.load()
    for x in range(width):
        t = x / max(width - 1, 1)
        r = int(ACCENT_VIOLET[0] * (1 - t) + ACCENT_PINK[0] * t)
        g = int(ACCENT_VIOLET[1] * (1 - t) + ACCENT_PINK[1] * t)
        b = int(ACCENT_VIOLET[2] * (1 - t) + ACCENT_PINK[2] * t)
        for y in range(height):
            pixels[x, y] = (r, g, b)
    return grad


def render_icon(size: int) -> Image.Image:
    """Render a single square Mimica icon at the given pixel size."""
    # Apple icons are typically drawn on a square canvas; macOS handles
    # the squircle masking when displaying. We add our own rounded-rect
    # so the icon also looks right when used outside macOS contexts.
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    radius = int(size * 0.225)  # ~22.5% — close to Apple's squircle
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill="white")

    # Render "Mimica" as a mask, then paste a gradient through that mask.
    target_text_height = int(size * 0.55)
    font = ImageFont.truetype(str(FONT_PATH), target_text_height)

    # Measure once with the actual font; some glyphs have descenders
    # that overshoot the bbox, so use textbbox for accuracy.
    text = "Mimica"
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # If the chosen size overshoots the canvas, scale the font down.
    max_w = int(size * 0.86)
    if text_w > max_w:
        target_text_height = int(target_text_height * max_w / text_w)
        font = ImageFont.truetype(str(FONT_PATH), target_text_height)
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

    # Mask = white text on transparent at canvas size.
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    text_x = (size - text_w) // 2 - bbox[0]
    text_y = (size - text_h) // 2 - bbox[1]
    mask_draw.text((text_x, text_y), text, font=font, fill=255)

    # Paste a gradient through the mask onto the white canvas.
    grad = make_gradient(size, size).convert("RGBA")
    canvas.paste(grad, (0, 0), mask)
    return canvas


def main() -> int:
    if not FONT_PATH.exists():
        print(f"Caveat font not found at {FONT_PATH}", file=sys.stderr)
        return 1

    # macOS .icns expects this exact set of (filename, size) pairs.
    iconset = [
        ("icon_16x16.png",       16),
        ("icon_16x16@2x.png",    32),
        ("icon_32x32.png",       32),
        ("icon_32x32@2x.png",    64),
        ("icon_128x128.png",    128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png",    256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png",    512),
        ("icon_512x512@2x.png", 1024),
    ]

    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    ICONSET_DIR.mkdir(parents=True)

    for filename, size in iconset:
        img = render_icon(size)
        img.save(ICONSET_DIR / filename, "PNG")
        print(f"  wrote {filename} ({size}×{size})")

    # Build the .icns. iconutil ships with macOS Command Line Tools.
    if ICNS_PATH.exists():
        ICNS_PATH.unlink()
    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)],
        check=True,
    )
    print(f"\nDone: {ICNS_PATH}")

    # Clean up the staging dir.
    shutil.rmtree(ICONSET_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
