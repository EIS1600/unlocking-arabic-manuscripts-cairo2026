#!/usr/bin/env python3
"""Transcribe a local image or PDF using Jina OCR's hosted API.

Usage (inside data/cairo2026; JINA_API_KEY required):
  env/bin/python recognisers/ocr_jina.py input_examples/printed.png --prompt prompts/arabic_block.txt
  env/bin/python recognisers/ocr_jina.py input_examples/manuscript.png --prompt prompts/arabic_line.txt
  env/bin/python recognisers/ocr_jina.py input_examples/printed_line-2.png --prompt prompts/arabic_line.txt
  env/bin/python recognisers/ocr_jina.py input_examples/printed.pdf --pages 0 --dry-run
  env/bin/python recognisers/ocr_jina.py input_examples/printed.png --prompt prompts/arabic_block.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.providers.jina_ocr import main as jina_main


def main(argv=None):
    """Accept the workshop's positional input and use the shared Jina client."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and not arguments[0].startswith("-"):
        arguments.insert(0, "--input")
    return jina_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
