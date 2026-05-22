# DocSorter — Agent Orientation

This file is for AI agents working on this codebase. Read it before touching anything.

## What this is

A native macOS app that sorts a folder of documents into a named taxonomy using a locally-running AI model (Ollama). The app is a SwiftUI frontend. All heavy lifting — OCR, classification, file moves — runs via a Python backend process.

No internet. No cloud. No data leaves the machine.

---

## Repository layout

```
doc_cleaner/          Python backend package (the brains)
  cli.py              Entry point for all CLI subcommands (Typer)
  scanner.py          Walks input folder, collects file metadata
  extractors/         Text extraction per file type
    __init__.py       Router: decides which extractor to call
    pdf.py            Text-based PDF (pypdf)
    pdf_ocr.py        Image-only PDF via Tesseract; 10-page cap, early stop
    image_ocr.py      JPEG/PNG/HEIC/TIFF; EXIF correction, rotation retry
    _rotation.py      ocr_with_rotation_retry() — shared by both OCR extractors
    docx.py           python-docx extraction
    text.py           Plain text / markdown / CSV
  classifier/         Ollama-based classification
    ollama.py         HTTP call to Ollama, JSON response
    prompts.py        System + user prompt templates
    schema.py         Pydantic models for AI response
  taxonomy.py         Load taxonomy.yaml, validate/normalize categories
  planner.py          Build CSV plan from classification results
  applier.py          Move files according to plan; write undo manifest
  undo.py             Restore files from undo manifest
  logging.py          Debug JSONL log helper
  config.py           Shared constants (e.g. supported extensions)

taxonomy.yaml         Default German-language taxonomy (categories + subcategories)
embed_ocr.py          Standalone script: embed searchable text into scanned PDFs

DocSorter/            Xcode project (SwiftUI app)
  project.yml         xcodegen spec — run `xcodegen generate` to regenerate .xcodeproj
  DocSorter/
    DocSorterApp.swift   App entry point, injects AppState + Settings as env objects
    ContentView.swift    NavigationSplitView: sidebar left, main pane right
    Bridge/
      PythonBridge.swift   Launches Python subprocesses; streams JSONL back to Swift
      ScanEvent.swift      Codable event types for all JSONL streams
    Model/
      AppState.swift       @MainActor ObservableObject; drives all UI state via AppPhase enum
      ReviewRow.swift      Per-file review data (editable)
      Settings.swift       @AppStorage-backed user preferences
    Sidebar/
      SidebarView.swift    Setup form + scan workflow orchestration
      SidebarViewModel.swift  File picker, validation, file-count helper
    MainPane/
      MainPaneView.swift   Switches on AppPhase to show the right view
      IdleView.swift       Empty state
      PreparingView.swift  COUNTED / EMBEDDING / PEEKING / CLASSIFYING progress rows
      ScanningView.swift   Live classification progress bar
      TaxonomySuggestionView.swift  Shows AI-suggested new categories, confirm/skip
      ReviewTableView.swift  Sortable table of proposed moves; keyboard nav
      DetailPanelView.swift  Inline editor for category/subcategory/filename
      DoneView.swift       Apply result summary + Undo button
      ErrorView.swift      Error display

tests/                Python tests (pytest)
pyproject.toml        Python package config; `pip install -e .` installs `doc-sorter` CLI
```

---

## How the pipeline works

1. **Count** — `SidebarViewModel.countFiles()` counts files instantly in Swift before starting the Python process.

2. **Embed-sparse** — `suggest-taxonomy --embed-sparse` pre-scans PDFs. Any PDF with fewer than a configurable minimum of non-whitespace chars gets `ocrmypdf` run on it in-place, permanently embedding a searchable text layer. Emits `{"event":"embed",...}` JSONL events for the EMBEDDING progress row.

3. **Peek** — The same `suggest-taxonomy` command reads a sample of document content (no OCR — just embedded text or filename), sends it to Ollama, and streams back `{"event":"taxonomy","additions":{...}}`. If new categories are suggested, the app shows `TaxonomySuggestionView`.

4. **Scan** — `scan` command walks the full input folder. Each file: extract text → classify via Ollama → write a row to the CSV plan and JSONL plan. Streams `{"event":"progress",...}` per file and `{"event":"done",...}` at the end.

5. **Review** — Swift reads the CSV plan into `ReviewRow` array. User can edit category, subcategory, suggested filename; toggle files in/out; Quick Look any file.

6. **Apply** — `apply` command reads the (possibly edited) CSV plan and moves files. Writes an undo manifest JSON.

7. **Undo** — `undo` command reads the manifest and moves files back.

---

## Subprocess bridge

`PythonBridge.swift` spawns Python subprocesses and reads their stdout line-by-line as JSONL.

**Critical:** Always call `process.environment = self.enrichedEnvironment()` on every `Process` before `.run()`. The enriched env injects `/opt/homebrew/bin:/usr/local/bin` into PATH so Tesseract, Ollama, etc. are found when the app is launched from Finder/Dock (which strips the user's shell PATH).

The Python process is invoked as:
```
python3 -u -m doc_cleaner <subcommand> [flags]
```

`-u` disables output buffering so JSONL lines arrive in real time.

JSONL event types (defined in `ScanEvent.swift`):
- `EmbedEvent` — `{event, file, status, done, total}` — one per PDF during embed-sparse
- `PeekEvent` — `{event, done, total}` — progress during peeking
- `TaxonomyResultEvent` — `{event, additions}` — final result from suggest-taxonomy
- `ProgressEvent` — `{event, file, classified, review, errors, total?}` — per-file during scan
- `DoneEvent` — `{event, plan, undo}` — scan complete
- `ErrorEvent` — `{event, message}` — error during scan

---

## OCR pipeline

Text extraction is routed in `doc_cleaner/extractors/__init__.py`:

| File type | Path |
|-----------|------|
| Text-based PDF | `pdf.py` via pypdf |
| Image-only PDF | `pdf_ocr.py` — PyMuPDF renders pages, Tesseract OCRs each; 10-page cap |
| JPG/PNG/HEIC/TIFF | `image_ocr.py` — PIL + Tesseract; EXIF orientation corrected via `ImageOps.exif_transpose` |
| DOCX | `docx.py` |
| TXT/MD/CSV | `text.py` |

**Rotation retry** (`_rotation.py`): After initial OCR, if non-whitespace char count < `sparse_threshold` (200 for images, 50 for PDF pages), Tesseract OSD is used to detect rotation angle. Image is rotated by `+angle` (NOT `-angle` — Tesseract's `rotate` field and PIL both use counter-clockwise degrees). Whichever pass produced more text wins.

**Timeout**: All `pytesseract` calls have `timeout=30`. On timeout, `RuntimeError` is raised and caught, returning `""` so the scan continues.

**ocrmypdf**: Used for the embed-sparse step only. Called with `skip_text=True` so already-processed pages are not re-encoded. Run `doc-sorter embed-ocr --input <folder>` or `python3 embed_ocr.py <folder>` to run it manually.

---

## AppState and AppPhase

`AppState` (`Model/AppState.swift`) is the single source of truth. It's injected as `@EnvironmentObject` everywhere.

`AppPhase` enum drives which view is shown:
```
.idle               → IdleView
.preparing(...)     → PreparingView
.taxonomySuggestion → TaxonomySuggestionView
.scanning(...)      → ScanningView
.review             → ReviewTableView + DetailPanelView
.done(...)          → DoneView
.error(...)         → ErrorView
```

State transitions happen on `@MainActor`. Background work (subprocess I/O) runs on `DispatchQueue` then calls `await MainActor.run { ... }`.

---

## Settings

`Settings` (`Model/Settings.swift`) uses `@AppStorage` to persist across launches:
- `lastInputPath` — last selected input folder path (String)
- `outputURL` — output folder (URL, stored as bookmark data)
- `modelName` — Ollama model name, defaults to `"qwen3:8b"`
- `confidenceThreshold` — 0–100 int, files below this go to Review category

---

## Taxonomy

`taxonomy.yaml` at repo root defines the default German-language taxonomy. Categories are top-level keys; subcategories are list values. The `Review` category is special — low-confidence files land there automatically.

Before each scan, `suggest-taxonomy` reads a sample of documents and asks Ollama if any new categories should be added. Additions are merged with the base taxonomy for that scan only (not persisted to `taxonomy.yaml`).

---

## Building the app

```bash
cd DocSorter
brew install xcodegen
xcodegen generate          # regenerates DocSorter.xcodeproj from project.yml
open DocSorter.xcodeproj   # then Cmd+R in Xcode
```

After any change to `project.yml` (adding/removing Swift files, changing settings), re-run `xcodegen generate`.

---

## Running the Python backend

```bash
pip install -e .                      # installs `doc-sorter` CLI + all deps
pip install -e ".[ocr]"               # include OCR extras (pytesseract, pymupdf, pillow-heif)
doc-sorter scan --input ~/Downloads --output-root ~/Sorted --ocr
doc-sorter doctor                     # checks all deps are installed
```

---

## Testing

```bash
pytest                    # runs all tests in tests/
pytest -k test_extractors # run a specific test module
```

Tests use fixtures in `tests/conftest.py`. OCR tests require Tesseract to be installed. Tests that hit Ollama are skipped if Ollama is not running.

---

## Key invariants

- **No `self.` → compiler error in closures**: Swift captures require explicit `self.` inside `DispatchQueue.async` blocks.
- **`process.environment` must be set on every Process**: Missing this means Tesseract/Ollama are not found → 0% confidence on all files.
- **`suggest-taxonomy` does NOT pass `--ocr`**: Peeking reads already-embedded text only; adding `--ocr` would cause Tesseract hangs during peeking.
- **`scan` passes `--ocr`**: Full classification does run OCR.
- **Rotation angle sign**: `img.rotate(angle)` not `img.rotate(-angle)`. Both Tesseract OSD and PIL use counter-clockwise convention.
- **`.onAppear` already runs on main thread** — no `DispatchQueue.main.async` wrapper needed.
- **`p.suffix.lower() == ".pdf"`** not `rglob("*.pdf")` — rglob is case-sensitive; `.PDF` files are common in scanned document archives.
