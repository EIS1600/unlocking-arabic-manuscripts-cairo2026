#!/usr/bin/env python3
"""Run one workshop crop through Chandra, Cloud Vision, Gemini, or Qwen.

Usage (inside data/cairo2026):
  env/bin/python recognisers/ocr_demo.py chandra input_examples/printed.png --backend cuda
  env/bin/python recognisers/ocr_demo.py chandra input_examples/printed.png --backend mps
  env/bin/python recognisers/ocr_demo.py chandra input_examples/printed.png --backend vllm --api-base http://localhost:8000/v1
  env/bin/python recognisers/ocr_demo.py vision input_examples/printed.png
  env/bin/python recognisers/ocr_demo.py vision input_examples/printed.png --record printed-vision.json
  env/bin/python recognisers/ocr_demo.py gemini input_examples/manuscript.png --prompt prompts/arabic_line.txt --stream
  env/bin/python recognisers/ocr_demo.py gemini input_examples/printed.png --prompt prompts/arabic_block.txt --stream --dry-run
  env/bin/python recognisers/ocr_demo.py qwen input_examples/printed.png --prompt prompts/arabic_block.txt --record printed-qwen.json
  env/bin/python recognisers/ocr_demo.py qwen input_examples/printed.png --prompt prompts/arabic_block.txt --backend hf --device mps

Chandra defaults to local NVIDIA CUDA inference; --backend mps selects Apple
Silicon instead. Qwen defaults to
DeepInfra; --backend hf loads its weights locally. Hosted providers use single
direct requests for live demonstrations, not production batches.
Cloud calls incur charges; stdout contains the uncorrected transcription. No
dataset outputs or ground truth are modified. Errors are not silently retried.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def transcribe_qwen_local(image_path: Path, prompt: str, model_id: str, device: str) -> str:
    """Run unquantised local inference; never silently fall back to a paid API."""
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    if device == 'mps':
        if not torch.backends.mps.is_available():
            raise RuntimeError('Apple MPS is unavailable. Use an Apple Silicon Mac with MPS-enabled PyTorch.')
    elif not torch.cuda.is_available() or int(device.split(':')[1]) >= torch.cuda.device_count():
        raise RuntimeError(f'{device} is unavailable. Check the NVIDIA driver and CUDA-enabled PyTorch installation.')
    dtype = torch.float16
    if device.startswith('cuda:'):
        with torch.cuda.device(device):
            if torch.cuda.is_bf16_supported():
                dtype = torch.bfloat16
    print(f'Loading {model_id} on {device}; weights may be downloaded on the first run.', file=sys.stderr)
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id, dtype=dtype, device_map={'': device}, attn_implementation='sdpa',
    ).eval()
    messages = [{'role': 'user', 'content': [
        {'type': 'image', 'url': str(image_path.resolve())},
        {'type': 'text', 'text': prompt},
    ]}]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors='pt', enable_thinking=False,
    ).to(device)
    # Keep IDs/grid dimensions integral, but match floating image tensors to weights.
    inputs = {key: value.to(dtype=dtype) if value.is_floating_point() else value
              for key, value in inputs.items()}
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
    generated = output[0, inputs['input_ids'].shape[-1]:]
    eos = model.generation_config.eos_token_id
    eos_ids = [eos] if isinstance(eos, int) else (eos or [])
    if not len(generated) or int(generated[-1]) not in eos_ids:
        raise RuntimeError('Incomplete local Qwen response: no end-of-sequence token; no transcription printed.')
    return processor.decode(generated, skip_special_tokens=True)


def main(argv: list[str] | None = None, *, provider: str | None = None) -> None:
    parser = argparse.ArgumentParser(description=(f'Run {provider} on a PNG image.' if provider else __doc__))
    if provider is None:
        parser.add_argument('provider', choices=('chandra', 'vision', 'gemini', 'qwen'))
    elif provider not in ('chandra', 'vision', 'gemini', 'qwen'):
        raise ValueError(f'Unknown provider: {provider}')
    else:
        parser.set_defaults(provider=provider)
    parser.add_argument('image', type=Path)
    parser.set_defaults(model=None, prompt=None, backend=None, api_base=None, stream=False, device=None)
    if provider in (None, 'gemini', 'qwen'):
        parser.add_argument('--model', help='Model ID (defaults: gemini-3.8-flash or Qwen/Qwen3.8-27B)')
        parser.add_argument('--prompt', type=Path, help='Required for Gemini/Qwen: UTF-8 prompt file sent as written')
    parser.add_argument('--record', type=Path, help='Save a compact response record, without image data')
    if provider in (None, 'chandra', 'qwen'):
        choices = ('cuda', 'mps', 'vllm') if provider == 'chandra' else ('deepinfra', 'hf') if provider == 'qwen' else ('cuda', 'mps', 'vllm', 'deepinfra', 'hf')
        parser.add_argument('--backend', choices=choices, help='Chandra: cuda (default, NVIDIA GPU 0), mps (Apple Silicon), or vllm; Qwen: deepinfra (default) or hf (local)')
    if provider in (None, 'qwen'):
        parser.add_argument('--device', help='Required for local Qwen: mps or cuda:N (for example cuda:0)')
    if provider in (None, 'chandra'):
        parser.add_argument('--api-base', help='Chandra vLLM URL; requires --backend vllm')
    if provider in (None, 'gemini'):
        parser.add_argument('--stream', action='store_true', help='Explicit opt-in to a direct Gemini demo request')
    parser.add_argument('--dry-run', action='store_true', help='Validate input without calling any service')
    args = parser.parse_args(argv)
    args.backend = args.backend or ('deepinfra' if args.provider == 'qwen' else 'cuda' if args.provider == 'chandra' else None)
    allowed_backends = {'qwen': ('deepinfra', 'hf'), 'chandra': ('cuda', 'mps', 'vllm')}
    if args.backend is not None and args.backend not in allowed_backends.get(args.provider, ()):
        parser.error('--backend does not apply to this provider.')
    if args.provider == 'qwen' and args.backend == 'hf':
        if args.device != 'mps' and not (args.device and args.device.startswith('cuda:') and args.device[5:].isdigit()):
            parser.error('--backend hf requires --device mps or cuda:N.')
    elif args.device is not None:
        parser.error('--device applies only to Qwen --backend hf.')
    prompt = None
    if args.provider in ('gemini', 'qwen'):
        if args.prompt is None:
            parser.error('--prompt is required for Gemini and Qwen; choose a file under prompts/ or supply your own.')
        try:
            prompt = args.prompt.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            parser.error(f'Cannot read UTF-8 prompt file {args.prompt}: {error}')
        if not prompt.strip():
            parser.error('The prompt file is empty.')
    elif args.prompt is not None:
        parser.error('--prompt applies only to Gemini and Qwen.')
    args.model = args.model or ('Qwen/Qwen3.8-27B' if args.provider == 'qwen' else 'gemini-3.8-flash')
    if args.record and args.record.exists():
        parser.error('The response record already exists; choose a new path to preserve the earlier result.')
    if args.provider == 'chandra':
        if args.backend == 'vllm' and not args.api_base:
            parser.error('--backend vllm requires --api-base.')
        if args.backend != 'vllm' and args.api_base:
            parser.error('--api-base applies only to --backend vllm.')
    if args.provider == 'gemini' and not args.stream:
        parser.error('The live Gemini demo requires --stream; production OCR uses Batch by default.')
    from PIL import Image
    with Image.open(args.image) as source:
        if source.format != 'PNG':
            parser.error('Use the saved PNG crop, not the PDF.')
        source.verify()
    if args.dry_run:
        print(f'Valid PNG: {args.image}; provider={args.provider}; no request made')
        if args.provider == 'chandra':
            target = args.api_base or ('host NVIDIA GPU (cuda:0)' if args.backend == 'cuda' else 'host Mac (Apple MPS)')
            print(f'Backend: {args.backend}; target: {target}')
        if args.provider in ('gemini', 'qwen'):
            print(f'Model: {args.model}\nPrompt file: {args.prompt}\nPrompt:\n{prompt}')
        if args.provider == 'qwen':
            print(f'Backend: {args.backend}; device: {args.device or "hosted"}; no model loaded')
        return
    from src.core.path_utils import load_env
    load_env()
    started = time.monotonic()
    if args.provider == 'vision':
        from google.cloud import vision_v1
        result = vision_v1.ImageAnnotatorClient().document_text_detection(
            image=vision_v1.Image(content=args.image.read_bytes()), timeout=90, retry=None)
        if result.error.message:
            raise RuntimeError(result.error.message)
        text = result.full_text_annotation.text
    elif args.provider == 'gemini':
        from src.providers.gemini_manuscript_ocr import _client
        client = _client()
        result = client.interactions.create(
            model=args.model,
            input=[{'type': 'text', 'text': prompt},
                   {'type': 'image', 'mime_type': 'image/png',
                    'data': base64.b64encode(args.image.read_bytes()).decode(),
                    'resolution': 'high'}],
            generation_config={'max_output_tokens': 2048, 'thinking_level': 'medium'},
            store=False,
        )
        if result.status != 'completed':
            raise RuntimeError(f'Gemini response is not complete (status={result.status}); no transcription printed.')
        # The SDK's output_text selects final model-output text, not thought steps.
        text = result.output_text
    elif args.provider == 'qwen' and args.backend == 'hf':
        result = None
        text = transcribe_qwen_local(args.image, prompt, args.model, args.device)
    elif args.provider == 'qwen':
        from src.providers.qwen_manuscript_ocr import _client
        image_bytes = args.image.read_bytes()
        started = time.monotonic()
        result = _client().with_options(timeout=90, max_retries=0).chat.completions.create(
            model=args.model,
            messages=[{'role': 'user', 'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {
                    'url': 'data:image/png;base64,' + base64.b64encode(image_bytes).decode()}}]}],
            temperature=0,
            reasoning_effort='none',
            max_tokens=2048,
        )
        elapsed = time.monotonic() - started
        choice = result.choices[0]
        text = choice.message.content
        if args.record:
            with Image.open(args.image) as source:
                dimensions = list(source.size)
            record = {
                'recorded_at': datetime.now(timezone.utc).isoformat(),
                'provider': 'deepinfra', 'requested_model': args.model,
                'returned_model': result.model, 'mode': 'direct',
                'image_path': str(args.image), 'image_pixels': dimensions,
                'image_sha256': hashlib.sha256(image_bytes).hexdigest(),
                'prompt': prompt, 'prompt_path': str(args.prompt),
                'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
                'temperature': 0, 'reasoning_effort': 'none',
                'max_tokens': 2048, 'elapsed_seconds': elapsed,
                'finish_reason': choice.finish_reason,
                'usage': result.usage.model_dump() if result.usage else None,
                'text': text,
            }
            args.record.parent.mkdir(parents=True, exist_ok=True)
            with args.record.open('x', encoding='utf-8') as handle:
                json.dump(record, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
        if choice.finish_reason != 'stop':
            raise RuntimeError(f'Incomplete Qwen response: {choice.finish_reason}')
    else:
        if args.backend == 'cuda':
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA is unavailable. Install an NVIDIA driver and CUDA-enabled PyTorch; on Apple Silicon, select --backend mps.')
        from chandra.model import InferenceManager
        from chandra.model.schema import BatchInputItem
        from chandra.settings import settings
        if args.backend in ('cuda', 'mps'):
            if args.backend == 'mps':
                from src.providers.chandra_ocr import validate_mps_available
                validate_mps_available()
            settings.TORCH_DEVICE = 'cuda:0' if args.backend == 'cuda' else 'mps'
            settings.MODEL_CHECKPOINT = 'datalab-to/chandra-ocr-2'
            manager = InferenceManager(method='hf')
            options = {}
        else:
            settings.VLLM_MODEL_NAME = 'chandra'
            manager = InferenceManager(method='vllm')
            options = dict(vllm_api_base=args.api_base, max_workers=1, max_retries=0)
        with Image.open(args.image) as source:
            image = source.convert('RGB')
        result = manager.generate(
            [BatchInputItem(image=image, prompt_type='ocr_layout')],
            max_output_tokens=2048, **options,
        )[0]
        if result.error:
            raise RuntimeError(str(result.error))
        text = result.markdown
    if not text or not text.strip():
        raise RuntimeError('The service returned no transcription.')
    if args.record and (args.provider != 'qwen' or args.backend == 'hf'):
        with Image.open(args.image) as source:
            dimensions = list(source.size)
        usage = getattr(result, 'usage', None)
        record = {
            'recorded_at': datetime.now(timezone.utc).isoformat(),
            'provider': args.provider,
            'requested_model': args.model if args.provider in ('gemini', 'qwen') else (
                'datalab-to/chandra-ocr-2' if args.provider == 'chandra' else 'DOCUMENT_TEXT_DETECTION'),
            'mode': args.backend if args.provider in ('chandra', 'qwen') else 'direct',
            'image_path': str(args.image), 'image_pixels': dimensions,
            'image_sha256': hashlib.sha256(args.image.read_bytes()).hexdigest(),
            'prompt': prompt,
            'prompt_path': str(args.prompt) if prompt is not None else None,
            'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest() if prompt is not None else None,
            'generation_config': {'max_output_tokens': 2048, 'thinking_level': 'medium',
                                  'image_resolution': 'high'} if args.provider == 'gemini' else (
                                      {'max_new_tokens': 2048, 'do_sample': False, 'enable_thinking': False}
                                      if args.provider == 'qwen' else None),
            'elapsed_seconds': time.monotonic() - started,
            'timing_scope': 'provider setup and request; includes model loading for local backends',
            'usage': usage.model_dump(mode='json') if hasattr(usage, 'model_dump') else None,
            'text': text,
        }
        if args.provider == 'qwen':
            record.update(device=args.device, external_api_cost_usd=0)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        with args.record.open('x', encoding='utf-8') as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    print(text.strip())


if __name__ == '__main__':
    main()
