#!/usr/bin/env python3
"""Transcribe a local image or PDF with Mistral's hosted OCR endpoint.

Usage (inside data/cairo2026; MISTRAL_API_KEY required):
  env/bin/python recognisers/ocr_mistral.py input_examples/printed.png
  env/bin/python recognisers/ocr_mistral.py input_examples/manuscript.png
  env/bin/python recognisers/ocr_mistral.py input_examples/printed_line-2.png --record output_mistral_line.json
  env/bin/python recognisers/ocr_mistral.py input_examples/printed.pdf --dry-run

Uses one direct, billable request without a transcription prompt. Stdout contains
the returned Markdown, unchanged. Optional records contain no embedded images.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
DEFAULT_MODEL = "mistral-ocr-4-0"


def read_document(path: Path) -> tuple[bytes, str, int]:
    """Validate the local input before issuing any billable request."""
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass or not document.page_count:
                raise ValueError("Use a nonempty, unencrypted PDF.")
            return data, "application/pdf", document.page_count
    from PIL import Image
    with Image.open(path) as image:
        mime = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(image.format)
        if not mime:
            raise ValueError("Use a PNG, JPEG or PDF file.")
        image.verify()
    return data, mime, 1


def transcribe(client, data: bytes, mime: str, model: str) -> dict:
    field = "document_url" if mime == "application/pdf" else "image_url"
    response = client.ocr.process(
        model=model,
        document={"type": field, field: f"data:{mime};base64," + base64.b64encode(data).decode("ascii")},
        include_image_base64=False,
        retries=None,
        timeout_ms=120000,
    )
    payload = response.model_dump(mode="json", exclude_none=True)
    pages = payload.get("pages") or []
    if not pages or not all(isinstance(page.get("markdown"), str) for page in pages):
        raise ValueError("Mistral did not return page transcriptions.")
    if not any(page["markdown"].strip() for page in pages):
        raise ValueError("Mistral returned no text; no transcription printed.")
    return {
        "returned_model": payload.get("model"),
        "usage": payload.get("usage_info"),
        "pages": [{"index": page.get("index"), "markdown": page["markdown"]} for page in pages],
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--record", type=Path, help="Save a new compact image-free response record")
    parser.add_argument("--dry-run", action="store_true", help="Check input without calling the API")
    args = parser.parse_args(argv)
    if args.record and (args.record.exists() or not args.record.parent.is_dir()):
        parser.error("Choose a new record filename in an existing directory.")
    try:
        data, mime, page_count = read_document(args.input)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.dry_run:
        print(f"Valid input: {args.input}; {page_count} page(s); model={args.model}; direct API; no request made")
        return
    from src.core.path_utils import load_env
    load_env()
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        parser.error("Set MISTRAL_API_KEY in your environment or private ~/.config/.env file.")
    from mistralai.client import Mistral
    started = time.monotonic()
    with Mistral(api_key=key) as client:
        result = transcribe(client, data, mime, args.model)
    record = {
        "provider": "mistral", "model": args.model, "mode": "direct",
        "input": str(args.input), "source_sha256": hashlib.sha256(data).hexdigest(),
        "input_page_count": page_count, "created_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started, **result,
    }
    if args.record:
        with args.record.open("x", encoding="utf-8") as destination:
            json.dump(record, destination, ensure_ascii=False, separators=(",", ":"))
            destination.write("\n")
    print("\n\n".join(page["markdown"] for page in result["pages"]))


if __name__ == "__main__":
    main()
