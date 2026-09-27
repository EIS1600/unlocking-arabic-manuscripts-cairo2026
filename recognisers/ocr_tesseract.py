#!/usr/bin/env python3
"""Run the installed Tesseract CLI on an image and print its transcription.

Usage (inside data/cairo2026):
  env/bin/python recognisers/ocr_tesseract.py input_examples/printed.png --psm 6
  env/bin/python recognisers/ocr_tesseract.py input_examples/manuscript.png --psm 13
  env/bin/python recognisers/ocr_tesseract.py input_examples/printed_page.png --psm 3 --dry-run

Install Tesseract and Arabic language data separately; see README.md.
"""
import argparse
import shlex
import shutil
import subprocess
from pathlib import Path


def build_command(args) -> list[str]:
    return [args.executable, str(args.image), 'stdout', '-l', args.lang,
            '--oem', str(args.oem), '--psm', str(args.psm)]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--lang', default='ara', help='Tesseract language code (default: ara)')
    parser.add_argument('--oem', type=int, choices=range(4), default=1,
                        help='Recognition engine (default: 1, LSTM)')
    parser.add_argument('--psm', type=int, choices=range(14), default=6,
                        help='Page segmentation mode (default: 6, one text block)')
    parser.add_argument('--executable', default='tesseract', help='Tesseract executable name or path')
    parser.add_argument('--dry-run', action='store_true', help='Validate input and show command without OCR')
    args = parser.parse_args(argv)
    args.image = args.image.resolve()
    if not args.image.is_file():
        parser.error('Input image does not exist.')
    from PIL import Image
    try:
        with Image.open(args.image) as image:
            image.verify()
    except (OSError, ValueError) as error:
        parser.error(f'Cannot read input as an image: {error}')
    args.executable = shutil.which(args.executable)
    if not args.executable:
        parser.error('Tesseract executable not found; see the installation instructions in README.md.')
    command = build_command(args)
    if args.dry_run:
        print('Validated input and executable; no OCR run. Language data is not checked.')
        print(shlex.join(command))
        return
    # Inherit stdout/stderr so the text and any engine diagnostics remain unchanged.
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
