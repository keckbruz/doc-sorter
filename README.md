# doc-cleaner

A local-first, privacy-preserving CLI for classifying and organizing messy document folders on macOS.

**All processing is local. No cloud APIs. No telemetry. No account required.**

## What it does

1. Scans a folder recursively and extracts text from PDFs, DOCX, and text files
2. Classifies each file using a local Ollama model (e.g. qwen3.5:9b)
3. Generates a human-reviewable CSV/JSONL plan with suggested moves and renames
4. Applies approved moves when you're ready — with full undo support

## Privacy model

- The only network call is to `http://127.0.0.1:11434` (your local Ollama instance)
- Document text never leaves your machine
- No API keys, no accounts, no analytics, no logs uploaded anywhere
- Fully usable offline after Ollama and models are installed

## Installation

```bash
git clone <repo>
cd doc-cleaner
pip install -e .
```

## Ollama setup

```bash
# Install Ollama: https://ollama.com
ollama serve
ollama pull qwen3.5:9b

# Verify
python -m doc_cleaner doctor
```

## OCR setup (optional)

```bash
brew install tesseract tesseract-lang
pip install pytesseract
python -m doc_cleaner doctor   # should show Tesseract OK
```

## Usage

### 1. Scan (dry-run, no files moved)

```bash
python -m doc_cleaner scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --model qwen3.5:9b \
  --plan ./plans/downloads-plan.csv \
  --jsonl ./plans/downloads-plan.jsonl
```

Output:
```
Scan complete (142.3s)
  Scanned:       428
  Classified:    391
  Needs review:  52
  Errors:        7
  Cached:        0
  Plan written to: plans/downloads-plan.csv

No files were moved. Review the plan, then run apply.
```

### 2. Review the plan

Open `plans/downloads-plan.csv` in Numbers, Excel, or a text editor. For each row:
- Set `approved=true` to approve the move
- Set `approved=false` to skip (default)
- Edit `target_path` if you want a different destination

### 3. Apply approved moves

```bash
python -m doc_cleaner apply \
  --plan ./plans/downloads-plan.csv \
  --undo ./plans/undo-2026-05-13.json
```

You'll see a summary and a confirmation prompt before any files are moved.

### 4. Undo

```bash
python -m doc_cleaner undo \
  --undo-manifest ./plans/undo-2026-05-13.json
```

Or run the generated shell script:
```bash
bash ./plans/undo-2026-05-13.sh
```

### 5. Classify only first 50 files (for testing)

```bash
python -m doc_cleaner scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --limit 50
```

## Recommended workflow

1. **Start with a test copy** — copy 20–30 files to a temp folder first
2. **Dry-run first** — `scan` never moves anything
3. **Review the CSV** — check categories and filenames before approving
4. **Apply in small batches** — approve 10–20 rows at a time initially
5. **Keep backups** — Time Machine or a manual copy before applying to important folders

## Limitations

- Scanned PDFs (image-only) need OCR to extract text; without OCR, classification is based on filename only
- Model quality varies — always review before applying
- Very large files are truncated before sending to the model (see `--max-text-chars`)
- Sequential by default — classifying thousands of files takes time on a 16 GB Mac
