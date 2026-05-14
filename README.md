# doc-sorter

A local-first, privacy-preserving tool for classifying and organizing messy document folders on macOS.

**All processing is local. No cloud APIs. No telemetry. No account required.**

Two interfaces:
- **CLI** (`doc-sorter`) — terminal workflow, scriptable, full control
- **DocSorter.app** — native macOS SwiftUI app with folder pickers, live progress, and review table (requires Xcode to build)

---

## What it does

1. Scans a folder recursively and extracts text from PDFs, DOCX, images, and text files
2. Suggests taxonomy additions by peeking at your documents before the full scan
3. Classifies each file using a local Ollama model (e.g. `qwen3.5:9b`)
4. Generates a human-reviewable plan with suggested moves and renames
5. Applies approved moves when you're ready — with full undo support

## Privacy model

- The only network call is to `http://127.0.0.1:11434` (your local Ollama instance)
- Document text never leaves your machine
- No API keys, no accounts, no analytics, no logs uploaded anywhere
- Fully usable offline after Ollama and models are installed

---

## Installation

```bash
git clone <repo>
cd doc-sorter
pip install -e .
```

## Ollama setup

```bash
# Install Ollama: https://ollama.com
ollama serve
ollama pull qwen3.5:9b

# Verify
doc-sorter doctor
```

## OCR setup (optional)

```bash
brew install tesseract tesseract-lang
pip install pytesseract
doc-sorter doctor   # should show Tesseract OK
```

---

## CLI usage

### Quick interactive flow

```bash
doc-sorter
```

Opens a numbered terminal menu: scan, apply, undo, doctor. Writes plans to `plans/` and never opens a full-screen UI.

### Scan (dry-run — no files moved)

```bash
doc-sorter scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --model qwen3.5:9b \
  --plan ./plans/downloads-plan.csv
```

Output:
```
Scan complete (142.3s)
  Scanned:       428
  Classified:    391
  Needs review:   52
  Errors:          7
  Plan written to: plans/downloads-plan.csv
```

### Apply approved moves

```bash
doc-sorter apply \
  --plan ./plans/downloads-plan.csv
```

Shows a summary before moving anything. Writes an undo manifest automatically.

### Undo

```bash
doc-sorter undo \
  --undo-manifest ./plans/undo-2026-05-13.json
```

### Non-interactive pipeline (scan + apply in one step)

```bash
doc-sorter run \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --confidence-threshold 90 \
  --yes
```

### Taxonomy suggestion (used by the SwiftUI app, also useful standalone)

Before scanning, peek at document contents and suggest new taxonomy categories:

```bash
doc-sorter suggest-taxonomy \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --model qwen3.5:9b
```

Prints JSON to stdout, e.g. `{"Persönliches": ["Sportvereine"]}`. Returns `{}` if existing taxonomy already covers the documents.

### Machine-readable progress (for integrations)

```bash
doc-sorter scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --output-format jsonl
```

Emits one JSON line per file to stdout while Rich progress goes to stderr:

```json
{"event": "progress", "file": "steuerbescheid.pdf", "status": "classified", "classified": 12, "review": 3, "errors": 0, "total": null}
{"event": "done", "plan": "/path/to/plan.csv", "undo": null, "classified": 19, "review": 5, "errors": 0}
```

---

## Filename convention

Classified files are renamed to: `YYYY-MM_documenttype_sender.ext`

Examples:
- `2024-03_rechnung_vodafone.pdf`
- `2023-11_steuerbescheid_finanzamt-muenchen.pdf`
- `gehaltsabrechnung_firma-gmbh.pdf` (date unknown)

Rules: lowercase, underscores between segments, hyphens within a segment, no date if unknown, sender truncated to 25 chars.

---

## Taxonomy

The default German taxonomy covers:

| Category | Subcategories |
|----------|--------------|
| Finanzen | Bankwesen, Steuern, Versicherung, Geldanlage, Rechnungen, Quittungen |
| Verträge | Arbeitsvertrag, Mietvertrag, Dienstleistungsvertrag, Sonstiges |
| Behörden | Ausweise, Meldewesen, Bescheide, Sonstiges |
| Gesundheit | Arztberichte, Rechnungen, Versicherung, Rezepte |
| Arbeit | Gehaltsabrechnungen, Verträge, Zeugnisse, Bewerbungen |
| Bildung | Zertifikate, Hochschule, Kurse, Sonstiges |
| Wohnen | Miete, Nebenkosten, Internet, Anleitungen |
| Fahrzeuge | Versicherung, Wartung, Zulassung, Sonstiges |
| Persönliches | Briefe, Reise, Ausweise, Sonstiges |
| Medien | Fotos, Screenshots, Videos |
| Software | Lizenzen, Anleitungen |
| Archiv | — |
| Review | — (low-confidence files land here) |
| Duplikate | — |

The taxonomy is automatically extended based on your existing output folder structure and LLM suggestions for your specific document set.

---

## SwiftUI app (DocSorter.app)

A native macOS app that wraps the CLI with a clean interface — no terminal required.

**Requires:** Xcode 15+, macOS 14+

### Build

```bash
cd DocSorter
xcodegen generate   # regenerates DocSorter.xcodeproj from project.yml
open DocSorter.xcodeproj
# Cmd+R to build and run
```

### Features

- **Native folder pickers** — input and output folders selected via macOS file dialog, output folder persisted across restarts with security-scoped bookmarks
- **Preparing phase** — counts files instantly (local I/O), then runs taxonomy suggestion while showing an indeterminate progress bar
- **Taxonomy suggestion** — shows proposed additions (`+ Persönliches / Sportvereine`) with Add / Skip buttons
- **Live scan progress** — determinate progress bar, current filename, three live counters (classified / needs review / errors) color-coded green / amber / red
- **Review table** — full-width table with keyboard navigation:
  - `↑` / `↓` — navigate rows
  - `Enter` — expand/collapse detail panel for selected row
  - `Space` — open file in default app
  - `X` — exclude row (uncheck)
- **Detail panel** — expands inline: AI reasoning text, editable category / subcategory / filename, Approve button
- **Apply & undo** — "Apply selected (N)" button moves files; Done screen shows moved/skipped/errors with Undo button

### Architecture

Swift frontend + Python backend connected via subprocess. The app launches `python3 -m doc_cleaner` subcommands and reads stdout as JSONL for real-time progress. No Python bundled — requires Python 3 and Ollama installed on the machine.

```
DocSorter/
├── project.yml                     # xcodegen spec — source of truth for project config
├── DocSorter/
│   ├── DocSorterApp.swift
│   ├── ContentView.swift           # root NavigationSplitView
│   ├── Model/
│   │   ├── AppState.swift          # ObservableObject state machine
│   │   ├── ReviewRow.swift         # single file in the review table
│   │   └── Settings.swift          # UserDefaults + security-scoped bookmark
│   ├── Bridge/
│   │   ├── PythonBridge.swift      # subprocess launcher, JSONL stream
│   │   └── ScanEvent.swift         # Codable event structs
│   ├── Sidebar/
│   │   ├── SidebarView.swift       # folder pickers, scan trigger, full workflow
│   │   └── SidebarViewModel.swift  # NSOpenPanel, validation, file counting
│   └── MainPane/
│       ├── MainPaneView.swift      # state router
│       ├── IdleView.swift
│       ├── PreparingView.swift
│       ├── TaxonomySuggestionView.swift
│       ├── ScanningView.swift
│       ├── ReviewTableView.swift   # table + keyboard handling
│       ├── DetailPanelView.swift   # inline edit panel
│       ├── DoneView.swift
│       └── ErrorView.swift
```

---

## Recommended workflow

1. **Start with a small test folder** — copy 20–30 files to a temp folder first
2. **Scan is always dry-run** — no files are moved until you explicitly apply
3. **Review before applying** — check categories and filenames, especially amber rows
4. **Keep backups** — Time Machine or a manual copy before applying to important folders

## Limitations

- Scanned PDFs (image-only) need OCR; without it, classification is based on filename only
- Model quality varies — always review before applying
- Very large files are truncated before sending to the model (see `--max-text-chars`)
- Sequential by default — classifying thousands of files takes time on a 16 GB Mac
- SwiftUI app requires Xcode to build; no pre-built binary is distributed
