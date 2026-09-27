#!/usr/bin/env python3
"""Extract the Cairo OCR examples without resampling the source image pixels.

Usage (inside data/cairo2026):
  env/bin/python scripts/prepare_crops.py
  env/bin/python scripts/prepare_crops.py --only printed
  env/bin/python scripts/prepare_crops.py --only printed_line

Regenerates printed, printed_line and manuscript PNG/PDF pairs in cairo2026/input_examples/.
Requires one unrotated, unmasked, axis-aligned source image per selected page.
Crop edges expand to whole source pixels. No sharpening or upscaling is applied.
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parents[1] / 'input_examples'
SOURCES = (
    ('printed', 'data/example_dataset_2/inbox/shda07_1-20.pdf',
     4, (0.125, 0.320, 0.910, 0.405)),
    ('printed_line', 'data/example_dataset_2/inbox/shda07_1-20.pdf',
     4, (0.125, 0.365, 0.910, 0.405)),
    ('manuscript', 'data/example_dataset_1_mss/original/Paris Arabe 5881 ann. BG 15.4.25.pdf',
     8, (0.305, 0.149, 0.890, 0.190)),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=[source[0] for source in SOURCES])
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, source, page_index, bounds in SOURCES:
        if args.only and name != args.only:
            continue
        with fitz.open(ROOT / source) as document:
            page = document[page_index]
            images = page.get_image_info(xrefs=True)
            if page.rotation or len(images) != 1 or page.get_text().strip():
                raise ValueError(f'{source}: expected one unrotated scanned image, no text overlay')
            info = images[0]
            a, b, c, d, _, _ = info['transform']
            if b or c or a <= 0 or d <= 0:
                raise ValueError(f'{source}: rotated or mirrored image is unsupported')
            extracted = document.extract_image(info['xref'])
            if extracted.get('smask'):
                raise ValueError(f'{source}: image masks require explicit compositing')
            clip = fitz.Rect(*(value * (page.rect.width if i % 2 == 0 else page.rect.height)
                               for i, value in enumerate(bounds)))
            image_rect = fitz.Rect(info['bbox'])
            if not image_rect.contains(clip):
                raise ValueError(f'{source}: crop extends outside source image')
            # Use the PDF renderer's native JPEG decoder, avoiding differences
            # in chroma upsampling between Pillow and the source PDF renderer.
            native = fitz.Pixmap(document, info['xref'])
            if native.alpha or native.n not in (1, 3):
                raise ValueError(f'{source}: expected opaque grey or RGB image')
            with Image.frombytes('L' if native.n == 1 else 'RGB',
                                 (native.width, native.height), native.samples) as image:
                pixels = (
                    math.floor((clip.x0 - image_rect.x0) * image.width / image_rect.width),
                    math.floor((clip.y0 - image_rect.y0) * image.height / image_rect.height),
                    math.ceil((clip.x1 - image_rect.x0) * image.width / image_rect.width),
                    math.ceil((clip.y1 - image_rect.y0) * image.height / image_rect.height),
                )
                dpi = (image.width / image_rect.width * 72,
                       image.height / image_rect.height * 72)
                crop = image.crop(pixels)
                # The PDF's profile is authoritative; a JPEG can carry a
                # different embedded profile that the PDF viewer does not use.
                colour_space = document.xref_get_key(info['xref'], 'ColorSpace')[1]
                profile_ref = re.search(r'/ICCBased\s+(\d+)\s+0\s+R', colour_space)
                profile = document.xref_stream(int(profile_ref[1])) if profile_ref else None
                if not profile_ref and colour_space not in ('/DeviceRGB', '/DeviceGray'):
                    raise ValueError(f'{source}: unsupported colour space {colour_space}')
                png = OUTPUT / f'{name}.png'
                crop.save(png, dpi=dpi, icc_profile=profile)
                with Image.open(png) as saved:
                    assert saved.mode == crop.mode and saved.tobytes() == crop.tobytes()
                pdf = OUTPUT / f'{name}.pdf'
                with fitz.open() as result:
                    result_page = result.new_page(width=crop.width / dpi[0] * 72,
                                                  height=crop.height / dpi[1] * 72)
                    result_page.insert_image(result_page.rect, filename=str(png))
                    result.set_metadata({'title': name, 'subject': 'Native source pixels, no resampling; provenance in README.md'})
                    result.save(pdf, garbage=4, deflate=True)
                with fitz.open(pdf) as result:
                    xref = result[0].get_images()[0][0]
                    # extract_image() can colour-convert ICC-based images to
                    # RGB. Check raw image samples to verify lossless storage.
                    assert fitz.Pixmap(result, xref).samples == crop.tobytes()
                print(f'{name}: {crop.width} x {crop.height}; native DPI {dpi}; '
                      f'source pixel bounds {pixels}; PNG and PDF pixels verified')


if __name__ == '__main__':
    main()
