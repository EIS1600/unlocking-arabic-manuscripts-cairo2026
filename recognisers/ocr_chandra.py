#!/usr/bin/env python3
"""Transcribe a PNG with Chandra OCR 2; defaults to the host NVIDIA GPU (CUDA).

Usage (inside data/cairo2026):
  env/bin/python recognisers/ocr_chandra.py input_examples/printed.png
  env/bin/python recognisers/ocr_chandra.py input_examples/manuscript.png --backend cuda
  env/bin/python recognisers/ocr_chandra.py input_examples/printed.png --backend mps
  env/bin/python recognisers/ocr_chandra.py input_examples/printed.png --backend vllm --api-base http://localhost:8000/v1
"""
from ocr_demo import main

if __name__ == '__main__':
    main(provider='chandra')
