#!/usr/bin/env python3
"""Transcribe a PNG with a prompted Gemini model (paid direct demo request).

Usage (inside data/cairo2026; GEMINI_API_KEY required):
  env/bin/python recognisers/ocr_gemini.py input_examples/printed.png --model gemini-3.8-flash --prompt prompts/arabic_block.txt --stream
  env/bin/python recognisers/ocr_gemini.py input_examples/manuscript.png --model gemini-3.8-flash --prompt prompts/arabic_line.txt --stream --dry-run
"""
from ocr_demo import main

if __name__ == '__main__':
    main(provider='gemini')
