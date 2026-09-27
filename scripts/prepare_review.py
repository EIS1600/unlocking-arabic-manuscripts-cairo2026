#!/usr/bin/env python3
"""Package portable workshop reviewers, without OCR or model calls.

Usage (from data/unlocking-arabic-manuscripts-cairo2026):
  env/bin/python scripts/prepare_review.py
  env/bin/python scripts/prepare_review.py --wait-manuscripts
  env/bin/python scripts/prepare_review.py --agent-only

Copies ordinary and consensus review HTML plus the saved workshop Luna proposals.
--agent-only adds the Luna view to an already packaged workshop without reprocessing images.
When all workshop documents are available, rebuilds the manual-save standalone
exercises and the root GitHub Pages index with build_portable_review.py.
It never copies drafts,
ground truth, API receipts, PDFs or raw OCR. Existing workshop drafts are retained.
Workshop images are reduced to JPEG quality 52, at most 1600 pixels per side;
the original reviewers and their evidence fingerprints remain authoritative.
"""
from __future__ import annotations

import argparse
import base64
from html.parser import HTMLParser
from html import escape
from io import BytesIO
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote, urlsplit

from PIL import Image

WORKSHOP = Path(__file__).resolve().parents[1]
REPO = WORKSHOP.parents[1]
sys.path.insert(0, str(REPO))
from src.core.ocr_resume import atomic_write_text
DATASETS = (("cairo2026_dataset", "google-document-ai", 4, "Printed books"),
            ("cairo2026_dataset_mss", "manuscript", 2, "Manuscripts"))
IMAGE_MAX_EDGE = 1600
IMAGE_QUALITY = 52
ENTRY_NAMES = {"cairo2026_dataset": "printed-books", "cairo2026_dataset_mss": "experiment-manuscripts"}
LUNA_RUN = "cairo-workshop-luna-waw-20260927"
REVIEW_TITLES = {
    "ordinary": "Cairo2026 · Printed books",
    "consensus": "Cairo2026 · Printed books — consensus review",
    "agent": "Cairo2026 · Printed books — Luna-assisted review",
    "manuscript": "Cairo2026 · Manuscripts — experimental review",
}
# Bound decoding independently of Pillow's warning threshold; never disable its
# decompression-bomb protection. Only known, static raster payloads are changed.
IMAGE_MAX_PIXELS = 80_000_000
IMAGE_MAX_BASE64 = 256_000_000
EMBEDDED_IMAGE = re.compile(
    r'(?P<uri>data:image/(?:png|jpeg|jpg|webp);base64,)'
    r'(?P<data>[A-Za-z0-9+/]+={0,2})'
    r'|(?P<field>"image"\s*:\s*")(?P<bare>[A-Za-z0-9+/]+={0,2})(?P<end>")'
)


def compress_images(text: str, stats: dict[str, int]) -> str:
    """Replace raster bytes only, retaining text, geometry and evidence metadata.

    Metadata viewers store bare base64 in `image` fields; OCR viewers embed full
    data URIs. Their two known metadata JS consumers must advertise JPEG too.
    Work one image at a time without retaining a cache of decoded page images.
    """
    def replace(match: re.Match) -> str:
        encoded = match.group("data") or match.group("bare")
        if len(encoded) > IMAGE_MAX_BASE64:
            raise ValueError("Workshop image exceeds encoded-size limit")
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError(f"Unsupported workshop raster: {source.format}")
            if not (0 < source.width * source.height <= IMAGE_MAX_PIXELS):
                raise ValueError("Workshop image exceeds pixel limit")
            source.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
            if source.mode in {"RGBA", "LA", "P"} or "transparency" in source.info:
                rgba = source.convert("RGBA")
                raster = Image.new("RGB", source.size, "white")
                raster.paste(rgba, mask=rgba.getchannel("A"))
            else:
                raster = source.convert("RGB")
            output = BytesIO()
            raster.save(output, format="JPEG", quality=IMAGE_QUALITY, optimize=True)
        compressed = output.getvalue()
        stats["images"] = stats.get("images", 0) + 1
        stats["original_image_bytes"] = stats.get("original_image_bytes", 0) + len(raw)
        stats["compressed_image_bytes"] = stats.get("compressed_image_bytes", 0) + len(compressed)
        payload = base64.b64encode(compressed).decode("ascii")
        if match.group("uri"):
            return "data:image/jpeg;base64," + payload
        return match.group("field") + payload + match.group("end")

    text = EMBEDDED_IMAGE.sub(replace, text)
    for expression in ("${page.image}", "${pages[position].image}"):
        text = text.replace("data:image/png;base64," + expression,
                            "data:image/jpeg;base64," + expression)
    return text


def isolate_storage(text: str) -> str:
    """Keep copied viewers from reusing production browser drafts or handles."""
    for method in ("getItem", "setItem", "removeItem"):
        text = text.replace(f"localStorage.{method}(",
                            f'localStorage.{method}("cairo2026-workshop:" + ')
    return text.replace('"openiti-html-review"', '"cairo2026-workshop-review"')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.links.append(value)


def validate_links(root: Path, paths: list[Path]) -> None:
    for path in paths:
        if path.suffix != ".html":
            continue
        parser = Links()
        parser.feed(path.read_text(encoding="utf-8"))
        for value in parser.links:
            url = urlsplit(value)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f"Missing or escaping workshop link: {path}: {value}")


def label_review(text: str, dataset: str, relative: Path) -> str:
    """Change index display labels only; retain paths and persistence identities."""
    heading = f"<h1>{escape(dataset)} HTML review</h1>"
    if heading not in text:
        return text
    mode = "manuscript" if dataset.endswith("_mss") else (
        relative.parts[0] if relative.parts[0] in {"agent", "consensus"} else "ordinary"
    )
    title = escape(REVIEW_TITLES[mode])
    text = text.replace(heading, f"<h1>{title}</h1>")
    return text.replace(f"<title>{escape(dataset)} review</title>", f"<title>{title}</title>")


def entry_file(destination: Path, filename: str, target: str, title: str) -> Path:
    """Readable entry point; shared image-bearing documents remain in place."""
    path = destination / filename
    url = escape(target, quote=True)
    atomic_write_text(path, f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                      f'<title>{escape(title)}</title><meta http-equiv="refresh" content="0;url={url}">'
                      f'</head><body><a href="{url}">{escape(title)}</a></body></html>')
    return path


def package_luna(destination: Path) -> list[Path]:
    """Add saved, image-free suggestions; reuse the ordinary workshop viewers."""
    source = REPO / "data/cairo2026_dataset/_html_review"
    run = source / "agent" / LUNA_RUN
    if not (run / "index.html").is_file():
        raise ValueError(f"Saved Luna review missing: {run}")
    copied = []
    for original in sorted(run.rglob("*")):
        if not original.is_file() or original.suffix not in (".html", ".js"):
            continue
        text = original.read_text(encoding="utf-8")
        if EMBEDDED_IMAGE.search(text):
            raise ValueError(f"Agent wrapper unexpectedly contains images: {original}")
        if original.suffix == ".html":
            text = isolate_storage(text)
            text = label_review(text, "cairo2026_dataset", original.relative_to(source))
        target = destination / "cairo2026_dataset/_html_review" / original.relative_to(source)
        atomic_write_text(target, text)
        copied.append(target)
    copied.append(entry_file(
        destination, "printed-books-luna.html",
        f"cairo2026_dataset/_html_review/agent/{LUNA_RUN}/index.html",
        REVIEW_TITLES["agent"],
    ))
    validate_links(destination, copied)
    return copied


def package() -> bool:
    destination = WORKSHOP / "review"
    destination.mkdir(exist_ok=True)
    copied = []
    stats = {"source_bytes": 0, "packaged_bytes": 0, "images": 0,
             "original_image_bytes": 0, "compressed_image_bytes": 0}
    manuscript_ready = False
    for name, profile, count, title in DATASETS:
        root = REPO / "data" / name
        source = root / "_html_review"
        index = source / f"{name}_{profile}.html"
        viewers = list((source / f"ocr_{profile}").rglob("*.html"))
        # The pipeline writes the dataset index only after all viewers are ready.
        if not index.is_file() or len(viewers) != count:
            print(f"{title}: waiting for {count} complete review documents", flush=True)
            continue
        if profile == "manuscript":
            manuscript_ready = True
        for original in source.rglob("*"):
            if not original.is_file() or original.suffix not in (".html", ".js"):
                continue
            relative = original.relative_to(source)
            if relative.parts[0] == "agent":
                continue
            target = destination / name / "_html_review" / relative
            text = original.read_text(encoding="utf-8")
            stats["source_bytes"] += original.stat().st_size
            text = compress_images(text, stats)
            if original.suffix == ".html":
                text = isolate_storage(text)
                text = label_review(text, name, relative)
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                atomic_write_text(target, text)
            stats["packaged_bytes"] += target.stat().st_size
            copied.append(target)
        href = f"{name}/_html_review/{index.name}"
        stem = ENTRY_NAMES[name]
        review_title = REVIEW_TITLES["manuscript" if profile == "manuscript" else "ordinary"]
        ordinary = entry_file(destination, f"{stem}.html", href, review_title)
        copied.append(ordinary)
        if profile != "manuscript":
            consensus_indexes = list((source / "consensus").glob("*/index.html"))
            if len(consensus_indexes) > 1:
                raise ValueError("Select one consensus branch for the workshop")
            if consensus_indexes:
                href = f"{name}/_html_review/{consensus_indexes[0].relative_to(source).as_posix()}"
                launcher = entry_file(destination, f"{stem}-consensus.html", href, REVIEW_TITLES["consensus"])
                copied.append(launcher)
            copied.extend(package_luna(destination))
    validate_links(destination, copied)
    print(f"Packaged {len(copied)} HTML/JS files; manuscripts ready: {manuscript_ready}", flush=True)
    mib = 1024 * 1024
    reduction = 100 * (1 - stats["packaged_bytes"] / max(stats["source_bytes"], 1))
    print(f"Workshop compression: {stats['images']} images; HTML/JS "
          f"{stats['source_bytes'] / mib:.1f} → {stats['packaged_bytes'] / mib:.1f} MiB "
          f"({reduction:.1f}% smaller); raster bytes "
          f"{stats['original_image_bytes'] / mib:.1f} → "
          f"{stats['compressed_image_bytes'] / mib:.1f} MiB", flush=True)
    return manuscript_ready


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-manuscripts", action="store_true")
    parser.add_argument("--agent-only", action="store_true", help="Add saved Luna wrappers to existing workshop reviewers only")
    args = parser.parse_args()
    if args.agent_only:
        if args.wait_manuscripts:
            parser.error("--agent-only cannot be combined with --wait-manuscripts")
        copied = package_luna(WORKSHOP / "review")
        from build_portable_review import build
        build(WORKSHOP)
        print(f"Packaged {len(copied)} Luna HTML/JS files; existing images unchanged")
        return 0
    while True:
        ready = package()
        if ready:
            from build_portable_review import build
            build(WORKSHOP)
        if ready or not args.wait_manuscripts:
            return 0
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
