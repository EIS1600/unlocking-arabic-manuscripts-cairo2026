#!/usr/bin/env python3
"""Run local Kraken on a page image, one PDF page, or an already cropped line.

Usage (inside data/cairo2026):
  env/bin/python recognisers/ocr_kraken.py input_examples/printed_page.png --device cpu
  env/bin/python recognisers/ocr_kraken.py input_examples/printed_page.pdf --page 1
  env/bin/python recognisers/ocr_kraken.py input_examples/printed_line-2.png --single-line
  env/bin/python recognisers/ocr_kraken.py input_examples/manuscript.png --single-line --recognition-model recognisers/kraken_models/muharaf_rec_best.mlmodel --dry-run

PDF page numbers are 1-based. Temporary rendered images and OCR output are
removed after execution; stdout contains text. Original inputs are unchanged.
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
MODELS = FOLDER / 'recognisers/kraken_models'


def build_command(args, image: Path, output: Path) -> list[str]:
    command = [args.executable, '-r', '-d', args.device, '-i', str(image), str(output)]
    if not args.single_line:
        command += ['segment', '-bl', '-i', str(args.segmentation_model), '-d', 'horizontal-rl']
    command += ['ocr']
    if args.single_line:
        command += ['-s']
    return command + ['--num-line-workers', '0', '--base-dir', 'R', '-m', str(args.recognition_model)]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--page', type=int, help='Required for PDF input, starting at 1')
    parser.add_argument('--dpi', type=int, default=300, help='PDF rendering resolution')
    parser.add_argument('--single-line', action='store_true', help='Skip segmentation for an already cropped line')
    parser.add_argument('--recognition-model', type=Path, default=MODELS / 'apt-20221130.mlmodel')
    parser.add_argument('--segmentation-model', type=Path, default=MODELS / 'layout-20210711_AQ.mlmodel')
    parser.add_argument('--executable', default=str(FOLDER / 'env-kraken/bin/kraken'))
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    args.input = args.input.resolve()
    if not args.input.is_file():
        parser.error('Input does not exist.')
    args.executable = shutil.which(args.executable)
    if not args.executable:
        parser.error('Kraken executable not found; install requirements-kraken.txt in env-kraken.')
    models = [args.recognition_model] + ([] if args.single_line else [args.segmentation_model])
    if any(not model.is_file() for model in models):
        parser.error('A required model file is missing; see the project model references.')
    is_pdf = args.input.suffix.lower() == '.pdf'
    if args.dpi <= 0:
        parser.error('--dpi must be positive.')
    if is_pdf:
        import fitz
        with fitz.open(args.input) as document:
            if args.page is None or not 1 <= args.page <= len(document):
                parser.error(f'PDF input requires --page between 1 and {len(document)}.')
    else:
        if args.page is not None:
            parser.error('--page applies only to PDF input.')
        from PIL import Image
        with Image.open(args.input) as image:
            image.verify()
    if args.dry_run:
        print('Validated input, executable and model paths; no rendering or OCR run.')
        print('Command:', build_command(args, Path('page.png') if is_pdf else args.input, Path('output.txt')))
        return
    with tempfile.TemporaryDirectory(prefix='cairo-kraken-') as folder:
        image_path = args.input
        if is_pdf:
            image_path = Path(folder) / 'page.png'
            with fitz.open(args.input) as document:
                document[args.page - 1].get_pixmap(dpi=args.dpi, alpha=False).save(image_path)
        output = Path(folder) / 'output.txt'
        subprocess.run(build_command(args, image_path, output), check=True)
        text = output.read_text(encoding='utf-8').strip()
        if not text:
            raise RuntimeError('Kraken returned no text. Check segmentation or use --single-line for a cropped line.')
        print(text)


if __name__ == '__main__':
    main()
