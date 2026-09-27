#!/usr/bin/env python3
"""Extract complete source pages as single-page PDFs and native-pixel PNGs.

Usage (inside data/cairo2026):
  env/bin/python scripts/prepare_pages.py

Writes printed_page.{pdf,png} and manuscript_page.{pdf,png} in input_examples/.
Existing outputs are not overwritten. PDF page objects are copied, not rasterised.
PNG extraction preserves native image samples and the PDF colour profile, clipping
only outside the visible page. Pixel bounds round outwards by at most one pixel.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parents[1] / "input_examples"
SOURCES = (
    ("printed_page", "data/example_dataset_2/inbox/shda07_1-20.pdf", 4),
    ("manuscript_page", "data/example_dataset_1_mss/original/Paris Arabe 5881 ann. BG 15.4.25.pdf", 8),
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, _, _ in SOURCES:
        for suffix in ("pdf", "png"):
            target = OUTPUT / f"{name}.{suffix}"
            if target.exists():
                raise FileExistsError(f"Preserve existing example: {target}")
    for name, source, index in SOURCES:
        with fitz.open(ROOT / source) as document:
            page = document[index]
            images = page.get_image_info(xrefs=True)
            if page.rotation or len(images) != 1 or page.get_text().strip() or list(page.annots()):
                raise ValueError("Expected an unrotated scanned page without text or annotations")
            info = images[0]
            a, b, c, d, _, _ = info["transform"]
            if b or c or a <= 0 or d <= 0 or info.get("has-mask"):
                raise ValueError("Unsupported image transform or mask")
            rect = fitz.Rect(info["bbox"])
            if not rect.contains(page.rect):
                raise ValueError("Source image must cover the complete visible page")
            pix = fitz.Pixmap(document, info["xref"])
            if pix.alpha or pix.n not in (1, 3):
                raise ValueError("Expected opaque grayscale or RGB image")
            bounds = (
                math.floor((page.rect.x0 - rect.x0) * pix.width / rect.width),
                math.floor((page.rect.y0 - rect.y0) * pix.height / rect.height),
                math.ceil((page.rect.x1 - rect.x0) * pix.width / rect.width),
                math.ceil((page.rect.y1 - rect.y0) * pix.height / rect.height),
            )
            colour_space = document.xref_get_key(info["xref"], "ColorSpace")[1]
            profile_ref = re.search(r"/ICCBased\s+(\d+)\s+0\s+R", colour_space)
            if not profile_ref and colour_space not in ("/DeviceRGB", "/DeviceGray"):
                raise ValueError(f"Unsupported colour space: {colour_space}")
            profile = document.xref_stream(int(profile_ref[1])) if profile_ref else None
            png = OUTPUT / f"{name}.png"
            with Image.frombytes("L" if pix.n == 1 else "RGB", (pix.width, pix.height), pix.samples) as image:
                crop = image.crop(bounds)
                crop.save(png, icc_profile=profile,
                          dpi=(pix.width / rect.width * 72, pix.height / rect.height * 72))
                with Image.open(png) as saved:
                    assert saved.tobytes() == crop.tobytes()
                    assert saved.info.get("icc_profile") == profile
            pdf = OUTPUT / f"{name}.pdf"
            with fitz.open() as single:
                single.insert_pdf(document, from_page=index, to_page=index)
                single.save(pdf, garbage=4, deflate=True)
            with fitz.open(pdf) as saved:
                assert len(saved) == 1 and saved[0].rect == page.rect
                assert saved[0].get_pixmap(dpi=100).samples == page.get_pixmap(dpi=100).samples
                copied_xref = saved[0].get_image_info(xrefs=True)[0]["xref"]
                assert saved.xref_stream_raw(copied_xref) == document.xref_stream_raw(info["xref"])
            print(f"{name}: source page {index + 1}; PNG {crop.width} x {crop.height}; PDF and pixels verified")


if __name__ == "__main__":
    main()
