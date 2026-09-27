#!/usr/bin/env python3
"""Test Kraken recognition on manually separated printed lines.

Usage (inside data/cairo2026):
  env/bin/python scripts/kraken_manual_lines.py
  env/bin/python scripts/kraken_manual_lines.py --recognize

The manually chosen split is in the whitespace between the two printed lines.
No resizing, enhancement or transcription correction is applied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "2a39599b3e8936641af271b267ef9a9ed9628142b1ad9a7f79b568efa4f16bc7"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recognize", action="store_true")
    args = parser.parse_args()
    source = FOLDER / "input_examples/printed.png"
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("Source crop changed; inspect it before choosing new manual bounds")
    target = FOLDER / "input_examples"
    target.mkdir(exist_ok=True)
    record_path = FOLDER / "printed_page5-kraken-manual-lines.json"
    if args.recognize and record_path.exists():
        raise FileExistsError(f"Preserve existing recognition record: {record_path}")
    crops = []
    with Image.open(source) as image:
        if image.size != (1497, 235):
            raise ValueError("Unexpected source dimensions")
        for number, bounds in enumerate(((0, 0, 1497, 124), (0, 124, 1497, 235)), 1):
            path = target / f"printed_line-{number}.png"
            crop = image.crop(bounds)
            crop.save(path, dpi=image.info.get("dpi"), icc_profile=image.info.get("icc_profile"))
            with Image.open(path) as saved:
                assert saved.tobytes() == crop.tobytes()
            crops.append((path, bounds))
            print(f"{path.relative_to(ROOT)}: {crop.size}, bounds={bounds}")
    if not args.recognize:
        return
    executable = FOLDER / "env-kraken/bin/kraken"
    model = ROOT / "src/kraken/print_transcription_NEW.mlmodel"
    version = subprocess.check_output([
        str(FOLDER / "env-kraken/bin/python"), "-c",
        "import importlib.metadata; print(importlib.metadata.version('kraken'))",
    ], text=True).strip()
    lines = []
    with tempfile.TemporaryDirectory(prefix="cairo-kraken-lines-") as temporary:
        for number, (path, bounds) in enumerate(crops, 1):
            output = Path(temporary) / f"line_{number}.txt"
            command = [str(executable), "-d", "cpu", "-i", str(path), str(output),
                       "ocr", "-s", "--num-line-workers", "0", "--base-dir", "R",
                       "-m", str(model)]
            started = time.monotonic()
            subprocess.run(command, check=True, cwd=ROOT)
            elapsed = time.monotonic() - started
            raw = output.read_text(encoding="utf-8")
            lines.append({"line": number, "image": str(path.relative_to(ROOT)),
                          "image_sha256": sha256(path), "source_pixel_bounds": bounds,
                          "raw_output": raw, "elapsed_seconds": elapsed})
            print(f"Line {number}: {raw!r}", flush=True)
    record = {"provider": "kraken", "software_version": version,
              "recognition_model": str(model.relative_to(ROOT)), "model_sha256": sha256(model),
              "source_image": str(source.relative_to(ROOT)), "source_sha256": sha256(source),
              "segmentation": "manual two-line split; no segmentation model used",
              "recognition_options": ["-d", "cpu", "ocr", "-s", "--num-line-workers", "0", "--base-dir", "R"],
              "timing_scope": "separate CLI process and model loading for each line",
              "lines": lines, "text": "\n".join(line["raw_output"].rstrip("\n") for line in lines)}
    record_path.parent.mkdir(exist_ok=True)
    with record_path.open("x", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Saved {record_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
