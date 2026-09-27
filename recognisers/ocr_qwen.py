#!/usr/bin/env python3
"""Transcribe a PNG with Qwen through DeepInfra or local Hugging Face inference.

Usage (inside data/cairo2026; DEEPINFRA_API_KEY required only for the default backend):
  env/bin/python recognisers/ocr_qwen.py input_examples/printed.png --model Qwen/Qwen3.8-27B --prompt prompts/arabic_block.txt
  env/bin/python recognisers/ocr_qwen.py input_examples/manuscript.png --model Qwen/Qwen3.8-27B --prompt prompts/arabic_line.txt --dry-run
  env/bin/python recognisers/ocr_qwen.py input_examples/printed.png --model Qwen/Qwen3.8-27B --prompt prompts/arabic_block.txt --backend hf --device mps
  env/bin/python recognisers/ocr_qwen.py input_examples/manuscript.png --model Qwen/Qwen3.8-27B --prompt prompts/arabic_line.txt --backend hf --device cuda:0
"""
from ocr_demo import main

if __name__ == '__main__':
    main(provider='qwen')
