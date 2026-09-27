#!/usr/bin/env python3
"""Transcribe a PNG with Google Cloud Vision DOCUMENT_TEXT_DETECTION.

Usage (inside data/cairo2026; configured Google credentials required):
  env/bin/python recognisers/ocr_google_vision.py input_examples/printed.png
  env/bin/python recognisers/ocr_google_vision.py input_examples/printed_line-2.png --dry-run
"""
from ocr_demo import main

if __name__ == '__main__':
    main(provider='vision')
