# Unlocking Arabic Manuscripts - Cairo2026: Hands-on ATR Workshop

This workshop has two exercises. **Start with the review application:** compare
the source images with automatically generated transcriptions,
then correct them. No programming, installation or API key is needed.

The second, optional exercise is for participants who want to run recognisers
themselves and compare their results.

## Exercise 1: review transcription and layout

**Start with the [online review application](https://eis1600.github.io/unlocking-arabic-manuscripts-cairo2026/)**, the consensus review used in the main
exercise, with **two printed books and no metadata**. The website loads each
book only when selected. Use **Save HTML** to keep a complete offline copy.
No installation, dataset-folder connection or API key is needed.

1. Choose a printed book from the list. Use **Edit Text** to click a suggested
   word, compare the alternatives with the image, and select or type a correction.
2. Try correcting a few words or structural labels. You can also
   explore **Edit Layout**. There is no need to finish a whole document.
3. Click **Save HTML** before closing. Open the downloaded HTML file to continue
   later, and save again after further edits. It contains all the documents,
   images and current corrections for that review; no other files are required.

**There is no autosave.** Keep your latest saved HTML. **Export** downloads
metadata or transcriptions, not the resumable application. Saving does not mark
a document as reviewed or confirm pending suggestions.
The first save from the website also downloads the remaining books and images,
so it can take longer. Wait for the HTML download to finish before closing.

The following reviews are **optional**:

| Open | What to try |
|---|---|
| [printed-books.html](review/printed-books.html) | Compare the recognisers' alternatives and correct metadata, text and layout. |
| [printed-books-consensus.html](review/printed-books-consensus.html) | Extended consensus review: all four printed books, including metadata. |
| [experiment-manuscripts.html](review/experiment-manuscripts.html) | Try the experimental manuscript transcription and layout review. |
| [printed-books-luna.html](review/printed-books-luna.html) (optional) | Check suggestions made by Luna from the alternatives and surrounding text. |

The optional reviews contain **four printed books and two manuscripts**, with
20 pages each; the main exercise uses the first two printed books. Each optional
HTML is self-contained, so you can
download just the exercise you want. Images are included at reduced quality to
keep downloads manageable; no original PDFs are needed. Saved HTML files can
still be several tens of megabytes because they include those images.

Use **Edit Text** to choose between readings, type corrections or change structural
labels, and **Edit Layout** to adjust text regions and reading order. In the
consensus and Luna views, click a suggested word in Edit Text to see the alternatives.
Check suggestions against the image: Luna's colours show its reported confidence,
not verified correctness. Which view helps you work faster?

Each exercise keeps its own corrections; they are not shared automatically with
other HTML files. The production pipeline's folder autosave is unchanged—this
manual-save interface is only for the workshop.

## Exercise 2 (optional): run the recognisers

Small printed and manuscript images are provided for testing eight recognition
systems. Each has a standalone Python entry point in `recognisers/`. Tesseract,
Kraken and Chandra also provide their own command-line interfaces (CLIs), shown
first in their sections below. Hosted services may charge for requests; local
models may require substantial memory and a GPU.

Run all commands from the workshop directory (`data/cairo2026`). Each entry point runs **one system**
and prints its transcription.

### Images and sources

| Files in `input_examples/` | Source PDF | Physical PDF page |
|---|---|---:|
| `printed.{png,pdf}` — two lines below the heading | `../example_dataset_2/inbox/shda07_1-20.pdf` | 5 |
| `printed_line-1.png`, `printed_line-2.png` — individual lines | Same PDF | 5 |
| `manuscript.{png,pdf}` — Paris, BnF Arabe 5881 | `../example_dataset_1_mss/original/Paris Arabe 5881 ann. BG 15.4.25.pdf` | 9 |
| `printed_page.{png,pdf}` — complete printed page | `../example_dataset_2/inbox/shda07_1-20.pdf` | 5 |
| `manuscript_page.{png,pdf}` — complete manuscript page | `../example_dataset_1_mss/original/Paris Arabe 5881 ann. BG 15.4.25.pdf` | 9 |

### Python setup

Inside this directory, create a Python virtual environment and install the required packages:

```sh
python3 -m venv env
env/bin/python -m pip install -r requirements.txt
```

This creates `cairo2026/env`; no activation is needed for the commands below.
Keep this directory inside the repository: its requirements, shared OCR code
and model files use paths relative to that location.

Kraken needs a **separate Python 3.10–3.13 environment**, described below.
The Python OCR scripts support `--help` and `--dry-run`; dry runs do not load
models or call APIs, and do not verify credentials or hardware compatibility.

### Tesseract 5.5.3

Install the engine and Arabic language data:

```sh
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-ara
```

Check your installed version with `tesseract --version` and Arabic availability
with `tesseract --list-langs`. Package-manager versions may differ from 5.5.3.

```sh
tesseract input_examples/printed.png stdout \
  -l ara --oem 1 --psm 6
```

For the manuscript line:

```sh
tesseract input_examples/manuscript.png stdout \
  -l ara --oem 1 --psm 13
```

`--oem 1` selects the LSTM recognition engine. `stdout` prints the transcription
in the terminal. All four modes below produce a transcription; `--psm` tells
Tesseract what layout to expect and how much segmentation to perform.

| Option | Expected input | What Tesseract does |
|---|---|---|
| `--psm 3` | A complete page | Finds text blocks and lines automatically, then transcribes them. |
| `--psm 6` | One text block, possibly containing several lines (`input_examples/printed.png`) | Finds the lines within that block and transcribes them. |
| `--psm 7` | One cropped text line (`input_examples/printed_line-2.png`) | Treats the image as one line, applying its usual line analysis before recognition. |
| `--psm 13` | One cropped text line | Recognises the whole crop as one line, bypassing some of the usual line-analysis rules. |

Alternatively, use the prepared Python entry point, which calls the same CLI
and defaults to Arabic with the LSTM engine:

```sh
env/bin/python recognisers/ocr_tesseract.py \
  input_examples/printed.png --psm 6
env/bin/python recognisers/ocr_tesseract.py \
  input_examples/manuscript.png --psm 13
```

### Kraken 7.0.2

Install Kraken in a separate Python 3.10–3.13 environment:

```sh
# macOS
brew install python@3.13
python3.13 -m venv env-kraken

# Ubuntu/Debian: check that python3 is version 3.10–3.13
sudo apt install python3-venv
python3 --version
python3 -m venv env-kraken

# Both platforms
env-kraken/bin/python -m pip install -r requirements-kraken.txt
```

If Linux's default Python is outside the supported range, use a Python 3.10–3.13
interpreter explicitly when creating `env-kraken`.

On Apple Silicon with Python 3.13, if Kraken fails with a SciPy `__thread_bss`
loading error, install the compatible macOS wheel of the same SciPy version:

```sh
env-kraken/bin/python -m pip download \
  --no-deps --only-binary=:all: \
  --platform macosx_12_0_arm64 \
  --dest /tmp/cairo-scipy-wheel \
  scipy==1.15.3
env-kraken/bin/python -m pip install --force-reinstall --no-deps \
  /tmp/cairo-scipy-wheel/scipy-1.15.3-cp313-cp313-macosx_12_0_arm64.whl
```

Check the installation with `env-kraken/bin/kraken --version`.

The `-r` option means **raise on error**: Kraken reports the underlying exception
if processing fails, helping diagnose problems. It does not change recognition.

Select the processor with the **global** `-d` option, before `segment` or `ocr`:

- If omitted, Kraken 7.0.2 uses `auto`, selecting a device automatically according to the available hardware and software support. It does not necessarily use the CPU.
- `-d cpu`: CPU (used in the examples below).
- `-d cuda:0`: first NVIDIA GPU; requires a working NVIDIA driver and a CUDA-enabled PyTorch installation.
- `-d mps`: Apple Silicon GPU; requires MPS support in PyTorch. If a model uses unsupported operations, use `-d cpu`.

For example, to run a cropped line on an NVIDIA GPU, use the same command below
but start with `env-kraken/bin/kraken -r -d cuda:0` instead of
`env-kraken/bin/kraken -r -d cpu`. On Apple Silicon, use
`env-kraken/bin/kraken -r -d mps`. These device options also apply to full-page
segmentation and recognition. See the [Kraken device options](https://github.com/mittagessen/kraken/releases/tag/7.0).

Download the models into `recognisers/kraken_models/`:

- [OpenITI AOCP](https://github.com/OpenITI/AOCP_print_models): `layout-20210711_AQ.mlmodel` (printed-page segmentation) and `apt-20221130.mlmodel` (printed-text recognition).
- [Muharaf, Bors Uifalean (2024)](https://doi.org/10.5281/zenodo.14295489): `muharaf_rec_best.mlmodel` (Arabic manuscript recognition).

For an already cropped line, use only a recognition model; `ocr -s` skips
segmentation:

```sh
env-kraken/bin/kraken -r -d cpu \
  -i input_examples/printed_line-2.png output_kraken_printed_line-2.txt \
  ocr -s -m recognisers/kraken_models/apt-20221130.mlmodel \
  --num-line-workers 0 \
  --base-dir R
```

For the manuscript line:

```sh
env-kraken/bin/kraken -r -d cpu \
  -i input_examples/manuscript.png output_kraken_manuscript.txt \
  ocr -s -m recognisers/kraken_models/muharaf_rec_best.mlmodel \
  --num-line-workers 0 \
  --base-dir R
```

The first `-i` specifies the input image and output text file. After `ocr`,
`-s` skips segmentation and `-m` selects the recognition model.
`--base-dir R` sets the recognised text's base direction to right-to-left,
guiding character ordering when Arabic is mixed with numbers or Latin text.
It should match the text-direction convention used to train the recognition model.
`--num-line-workers 0` extracts line images within the main process instead of
starting separate workers (the default is two), avoiding process-startup overhead
for these small examples. It does not change the recognition model or select CPU/GPU.

For a complete page, chain **segmentation followed by recognition**:

```sh
env-kraken/bin/kraken -r -d cpu \
  -i input_examples/printed_page.png output_kraken_page.txt \
  segment -bl -i recognisers/kraken_models/layout-20210711_AQ.mlmodel -d horizontal-rl \
  ocr -m recognisers/kraken_models/apt-20221130.mlmodel \
  --num-line-workers 0 \
  --base-dir R
```

After `segment`, `-bl` enables baseline segmentation, `-i` selects its model,
and `-d horizontal-rl` sets the text direction. After `ocr`,
`-m` selects the recognition model to transcribe the detected lines.

In our tests, a segmenter fragmented the tight two-line crop. Using the full page
or recognising manually cropped lines avoided that segmentation problem.

Alternatively, the prepared Python entry point calls Kraken's CLI and prints
the transcription. It defaults to the public OpenITI models listed above and CPU:

```sh
env/bin/python recognisers/ocr_kraken.py \
  input_examples/printed_page.png --device cpu
env/bin/python recognisers/ocr_kraken.py \
  input_examples/printed_line-2.png --single-line
env/bin/python recognisers/ocr_kraken.py \
  input_examples/manuscript.png --single-line \
  --recognition-model recognisers/kraken_models/muharaf_rec_best.mlmodel
```

Use `--device cuda:0` or `--device mps` for a supported GPU. Override the models
with `--segmentation-model` and `--recognition-model`. For a PDF, add `--page 1`
(physical page number, starting at 1); `--dpi` controls rendering (default: 300).

### Chandra OCR 2

The project requirements install Chandra and its local inference dependencies.
Its own CLI can process an image or PDF and save the results in an output directory:

```sh
TORCH_DEVICE=cuda:0 env/bin/chandra \
  input_examples/printed.png output_chandra --method hf
TORCH_DEVICE=cuda:0 env/bin/chandra \
  input_examples/manuscript.png output_chandra --method hf
```

`--method hf` runs the model locally through Hugging Face; `TORCH_DEVICE=cuda:0`
selects the first NVIDIA GPU and requires a compatible driver and CUDA-enabled
PyTorch. On an Apple Silicon Mac, use `TORCH_DEVICE=mps` instead.
To process the PDF, replace `printed.png` with `printed.pdf`; no other option
needs changing. Chandra renders PDF pages into images automatically, so image
preparation and recognition results may differ from those of the PNG input.
The CLI saves Markdown, HTML and metadata under `output_chandra/printed/`.
Use `--no-html --no-images` to omit HTML and extracted images,
`--max-output-tokens` to limit generation per page, and `--help` for all options.

Alternatively, use the prepared Python entry point, which calls Chandra's Python
API and prints the Markdown transcription:

```sh
env/bin/python recognisers/ocr_chandra.py \
  input_examples/printed.png \
  --backend cuda
env/bin/python recognisers/ocr_chandra.py \
  input_examples/manuscript.png \
  --backend cuda
```

Loads `datalab-to/chandra-ocr-2` on the **host NVIDIA GPU** (`cuda:0`).
`--backend cuda` is the default and requires a compatible NVIDIA driver and
CUDA-enabled PyTorch. On an **Apple Silicon Mac**, use `--backend mps` instead.
The first run downloads roughly 10.6 GB of weights; loading and
inference need substantial memory. No external OCR API is used.
For a separately configured Linux GPU/vLLM server, use
`--backend vllm --api-base http://localhost:8000/v1`. This entry point does
not offer CPU inference.
The CLI and wrapper have different image-preparation defaults, so their outputs
need not match exactly, even with the same source image and model.

Alternatively, use [Datalab's hosted API](https://www.datalab.to/) with an API key,
without installing Chandra or downloading model weights locally. This is a paid
service, with a free usage allowance; see [Datalab's pricing](https://app.datalab.to/pricing).

### Google Cloud Vision

The Python client is included in the project requirements. Before running the example:

1. Create or select a Google Cloud project, enable billing and enable the Cloud Vision API.
2. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
3. Configure local authentication:

```sh
gcloud init
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Replace `YOUR_PROJECT_ID` with your project's ID. The Python client uses these
credentials automatically; no API key needs to be added to the script. See
[Google's setup guide](https://cloud.google.com/vision/docs/setup).

Then run:

```sh
env/bin/python recognisers/ocr_google_vision.py \
  input_examples/printed.png
env/bin/python recognisers/ocr_google_vision.py \
  input_examples/manuscript.png
```

The script sends the PNG to Google's `DOCUMENT_TEXT_DETECTION` service and prints
the transcription, without a prompt or local model. This entry point accepts PNG
images, not PDFs.
Requests are subject to [Google's API pricing](https://cloud.google.com/vision/pricing).

### Mistral OCR 4

The Python client is included in the requirements. Create an API key in
[Mistral Studio](https://console.mistral.ai/) and set `MISTRAL_API_KEY` in your
environment or private `~/.config/.env` file.

```sh
env/bin/python recognisers/ocr_mistral.py \
  input_examples/printed.png \
  --model mistral-ocr-4-0
env/bin/python recognisers/ocr_mistral.py \
  input_examples/manuscript.png \
  --model mistral-ocr-4-0
```

This sends a local image to the OCR API through Python's `mistralai` client and
prints its Markdown output. No transcription prompt or local model is needed.
PNG, JPEG and PDF inputs are supported; a PDF sends all its pages. To compare
the single printed line, use `input_examples/printed_line-2.png` instead.
Use `--dry-run` to validate the input without calling the API, or
`--record output_mistral.json` to save a new image-free response record.

The entry point uses direct requests. Standard OCR 4 pricing is **US$4 per
1,000 pages**, or **US$2 per 1,000 pages through the separate Batch API**
(checked 23 September 2026). Document AI annotations have separate pricing.
See [Mistral's OCR guide](https://docs.mistral.ai/studio/document-processing/basic_ocr)
and [OCR 4 pricing](https://mistral.ai/news/ocr-4/).

### Gemini

The client is included in the project requirements. Set `GEMINI_API_KEY`
in your environment or private `~/.config/.env` file.

```sh
env/bin/python recognisers/ocr_gemini.py \
  input_examples/printed.png \
  --model gemini-3.8-flash \
  --prompt prompts/arabic_block.txt \
  --stream
env/bin/python recognisers/ocr_gemini.py \
  input_examples/manuscript.png \
  --model gemini-3.8-flash \
  --prompt prompts/arabic_line.txt \
  --stream
```

`--prompt` is required: use `prompts/arabic_block.txt` for multiple lines or
`prompts/arabic_line.txt` for a single-line crop. Edit these UTF-8 text files or
pass your own file to change the instructions; the file is sent as written.
Both prompts require only the transcription, without explanations or alternative
readings, and use one `XXX` per unreadable word. These instructions cannot
guarantee compliance: always check the returned text. The script does not silently
remove commentary from a model's answer or print an incomplete Gemini response.
`--dry-run` displays the selected prompt without making an API request.
`--stream` explicitly enables a **direct, billable
request**, not discounted Batch processing. No local model is installed.

**Content filtering:** Gemini may reject a request with `content_blocked`,
without identifying the specific filter or what triggered it. We encountered
this with both Gemini 3.7 Flash and 3.8 Flash; it is not exclusive to 3.8.
The latest 3.8 Flash run returned a transcription for the manuscript crop, but
successful requests do not guarantee that other inputs will be accepted.
Some API responses provide safety feedback, but the rejections in our tests did
not explain the specific cause. See [Google's safety documentation](https://ai.google.dev/gemini-api/docs/safety-settings).

### Qwen

For **DeepInfra**, the client is included in the project requirements. Set `DEEPINFRA_API_KEY`
in your environment or private `~/.config/.env` file.

```sh
env/bin/python recognisers/ocr_qwen.py \
  input_examples/printed.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_block.txt
env/bin/python recognisers/ocr_qwen.py \
  input_examples/manuscript.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_line.txt
```

Uses the explicitly selected prompt file, shared with the Gemini examples,
through a billable DeepInfra request. Edit the file to try different instructions.
DeepInfra is the default backend; no local model installation is required.

For **local inference**, use `--backend hf` with an explicit device. The workshop
requirements include Transformers, PyTorch and Accelerate. No DeepInfra key is
needed; the first run downloads the model from Hugging Face.

On **Apple Silicon (MPS)**:

```sh
env/bin/python recognisers/ocr_qwen.py \
  input_examples/printed.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_block.txt \
  --backend hf --device mps
env/bin/python recognisers/ocr_qwen.py \
  input_examples/manuscript.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_line.txt \
  --backend hf --device mps
```

On **Linux with an NVIDIA GPU (CUDA)**:

```sh
env/bin/python recognisers/ocr_qwen.py \
  input_examples/printed.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_block.txt \
  --backend hf --device cuda:0
env/bin/python recognisers/ocr_qwen.py \
  input_examples/manuscript.png \
  --model Qwen/Qwen3.8-27B \
  --prompt prompts/arabic_line.txt \
  --backend hf --device cuda:0
```

`cuda:0` selects the first NVIDIA GPU. Install a compatible NVIDIA driver and
CUDA-enabled PyTorch using the [PyTorch installation guide](https://pytorch.org/get-started/locally/).
The local backend loads the full model onto the selected device, without
quantisation or CPU offloading. Its 27 billion parameters alone require roughly
54 GB at 16-bit precision, plus memory for inference and, on a Mac, the operating
system. This is not suitable for a 16–32 GB Mac or GPU. Allow substantial disk
space for the downloaded weights too.

These local paths have offline tests, but have not yet been validated with the
full model on either device. MPS operator compatibility and speed depend on the
installed PyTorch/Transformers versions. Unsupported operations or insufficient
memory produce an error; the script never silently switches to a paid API.
Use `--dry-run` to check arguments without downloading weights or running OCR.
See the [Qwen model card](https://huggingface.co/Qwen/Qwen3.8-27B) for local deployment.

### Jina OCR

[`jina-ocr-v1`](https://huggingface.co/jinaai/jina-ocr-v1) is a document
vision-language model based on DeepSeek-OCR. Create an API key at
[Jina AI](https://jina.ai/) and set `JINA_API_KEY` in your environment or
private `~/.config/.env` file. The workshop requirements include its API client.

```sh
env/bin/python recognisers/ocr_jina.py \
  input_examples/printed.png \
  --prompt prompts/arabic_block.txt
env/bin/python recognisers/ocr_jina.py \
  input_examples/manuscript.png \
  --prompt prompts/arabic_line.txt
```

This uses the hosted direct API and sends the image, not a public file URL.
The entry point also accepts PDFs, rendering each selected page as an image.
Use `--pages 0` for only the first PDF page, or `--dry-run` to inspect settings
without calling the service. `--prompt` sends the selected editable prompt file.
Dollar cost depends on the account's billing; API usage tokens are not themselves
a dollar price. Empty or truncated output is reported as a failure.
Both workshop crops returned text in our test, but the printed output lost line
breaks and many vowel marks, and the manuscript reading contained substantial errors.

For the single printed line:

```sh
env/bin/python recognisers/ocr_jina.py \
  input_examples/printed_line-2.png \
  --prompt prompts/arabic_line.txt
```

The downloadable weights use **CC BY-NC 4.0**, not an unrestricted commercial
licence. The model card provides local CPU/GPU instructions; the workshop entry
point uses the hosted API, not a local installation.

## Saving results

Chandra, Vision, Gemini, Qwen and Mistral accept `--record NEW_PATH.json` to save text,
settings, image checksum, elapsed time and available usage, without embedding
images or overwriting existing records. The Tesseract and Kraken Python entry
points print text to stdout. Kraken's CLI saves text to the output file specified
after `-i`; Chandra's CLI saves files in its output directory.
Gemini and Qwen records also retain the exact prompt, its path and a SHA-256
checksum so results remain traceable after editing a prompt file.

`recognisers/ocr_demo.py` remains the shared entry point for Chandra, Vision, Gemini and
Qwen, selected by its first argument. The separate scripts use the same code.

API reruns incur charges and may return different text.
