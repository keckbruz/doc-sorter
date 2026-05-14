# Doc Sorter — macOS SwiftUI App Design

## Goal

A native macOS app that wraps the existing Python doc-sorter CLI with a clean SwiftUI interface — native folder pickers, real-time scan progress, keyboard-driven review table, no terminal required.

## Architecture

Swift frontend + Python backend connected via subprocess. Swift launches `python3 -m doc_cleaner` subcommands and reads stdout as JSONL for real-time updates. File counting and folder picking are handled natively in Swift. The Python codebase requires minimal additions to support structured output.

This approach keeps the Python core unchanged except for two new entry points. The subprocess boundary is an explicit isolation layer — bundling Python for distribution can be added later without touching the UI code.

**Assumption (v1):** Python 3 and Ollama are installed on the user's machine. The app does not bundle either.

## Layout

Single window, split pane:

- **Left sidebar** (~220pt, fixed width): input folder picker, output folder picker, model text field (with autocomplete from `ollama list`), confidence threshold stepper (integer, 0–100), Scan button. Always visible. Shows current scan state summary after a scan completes (rescan button, apply button).
- **Right pane** (flexible): transitions through workflow states (see below).

Window minimum size: 900 × 600pt.

## Visual Style

- **Background:** dark (`#0d0d0d` / `#111` surfaces)
- **Font:** `SF Mono` throughout — both UI labels and file content
- **Color coding — purposeful only:**
  - Green (`#3fb950`) — confident classification, success
  - Amber (`#e3a02b`) — needs attention, low confidence, review required
  - Red (`#f85149`) — errors
  - Blue (`#3a8fff`) — interactive elements, selection, active state
  - Grey (`#555`) — secondary labels, hints
- No decorative color. Color only appears where it signals something actionable.

## Right Pane — Workflow States

### 1. Idle
Empty state. Brief instruction: "Pick an input folder and press Scan."

### 2. Preparing
Triggered immediately when Scan is pressed. Two sequential steps:

1. **File count** — Swift walks the input directory using the same logic as `scan_files()`. Shows: `Found 24 documents in ~/Downloads`. Progress bar fills instantly (this is fast I/O, no LLM).
2. **Taxonomy peek** — calls `suggest-taxonomy` subcommand. Progress bar animates indeterminately while the LLM call runs.

### 3. Taxonomy Suggestion
Displayed after `suggest-taxonomy` returns. Shows suggested additions as a flat list:

```
Suggested additions to taxonomy:
  + Persönliches / Reise
  + Technik / Gerätehandbücher
  + Vereine / Mitgliedschaften
```

Two buttons: **Add to taxonomy** / **Skip**. If the suggestion returns empty, this state is skipped silently and scan proceeds immediately.

### 4. Scanning
Progress bar (determinate): `15 / 24` with percentage fill. Current filename shown below bar (truncated with ellipsis if long). Three live counters update as each file completes:

```
12  classified     3  needs review     0  errors
```

Counters are color-coded: green / amber / red.

### 5. Review Table
Full-width table. Columns: checkbox, filename, category/subcategory, confidence %.

**Color coding per row:**
- Green tint + blue checkbox: confident, selected for apply
- Amber left border: needs review, unchecked by default

**Keyboard controls (same as terminal version):**
- `↑` / `↓` — navigate rows
- `Space` — Quick Look preview (native `QLPreviewController`)
- `Enter` — expand detail panel for selected row; confirm edits when panel is open
- `X` — exclude row (uncheck, remove amber border)

**Detail panel** expands inline below the selected row on `Enter` or click. Contains:
- AI reasoning text (italic, grey)
- Category dropdown (all taxonomy categories/subcategories)
- Filename text field (editable)
- **Approve** button — checks the row and collapses the panel

**Toolbar above table:**
- "Select all confident" checkbox
- File count summary: `19 confident · 5 need review`
- **Apply selected** button (right-aligned)

### 6. Done
Shows apply result:
```
✓ Applied
Moved:   19 files
Skipped:  5 files
Errors:   0
```
**Undo** button calls `python3 -m doc_cleaner undo --undo-manifest <path>`. Scan again button resets to Idle.

## Settings Persistence

Stored in `UserDefaults`:
- Output folder — persisted as a security-scoped bookmark so it survives app restarts
- Model name — string, default `qwen3.5:9b`
- Confidence threshold — integer 0–100, default 90
- Last input folder path — used only to pre-navigate the `NSOpenPanel`, not pre-filled

## Python CLI Additions

Two additions to the Python backend. No existing commands change behaviour.

### 1. `scan --output-format jsonl`

When `--output-format jsonl` is passed, the scan command emits one JSON line to stdout per file processed, in addition to writing the plan CSV:

```json
{"event": "progress", "file": "steuerbescheid.pdf", "status": "classified", "classified": 12, "review": 3, "errors": 0, "total": 24}
```

On completion:
```json
{"event": "done", "plan": "/path/to/plan.csv", "undo": "/path/to/undo.json", "classified": 19, "review": 5, "errors": 0}
```

On error (Ollama unreachable, etc.):
```json
{"event": "error", "message": "Ollama is not running at http://127.0.0.1:11434"}
```

### 2. `suggest-taxonomy` subcommand

```
python3 -m doc_cleaner suggest-taxonomy \
  --input <dir> \
  --output <dir> \
  --model <model>
```

Runs the existing `_suggest_taxonomy()` logic (peek read + LLM call) with the output folder as existing taxonomy context. Returns JSON to stdout:

```json
{"Persönliches": ["Reise"], "Technik": ["Gerätehandbücher"]}
```

Returns `{}` if no additions are needed. Exits with code 0 in all non-error cases.

## Swift Project Structure

```
DocSorter/
├── DocSorterApp.swift          # App entry point, window setup
├── ContentView.swift           # Root split pane layout
├── Sidebar/
│   ├── SidebarView.swift       # Folder pickers, model, threshold, scan button
│   └── SidebarViewModel.swift  # Settings persistence via UserDefaults
├── MainPane/
│   ├── MainPaneView.swift      # State router → correct child view
│   ├── IdleView.swift
│   ├── PreparingView.swift     # File count + taxonomy peek progress
│   ├── TaxonomySuggestionView.swift
│   ├── ScanningView.swift      # Progress bar + live counters
│   ├── ReviewTableView.swift   # Table + keyboard handling + detail panel
│   └── DoneView.swift
├── Bridge/
│   ├── PythonBridge.swift      # Subprocess launch + stdout JSONL parsing
│   ├── ScanEvent.swift         # Codable JSONL event structs
│   └── TaxonomySuggestion.swift
└── Model/
    ├── AppState.swift          # ObservableObject driving the UI state machine
    ├── ReviewRow.swift         # Single file in the review table
    └── Settings.swift          # UserDefaults-backed settings
```

## Data Flow

```
User clicks Scan
  → SidebarViewModel validates folders
  → AppState transitions to .preparing
  → PythonBridge.suggestTaxonomy() launches subprocess, parses JSON response
  → AppState transitions to .taxonomySuggestion (or .scanning if empty)
User confirms taxonomy
  → AppState transitions to .scanning
  → PythonBridge.scan() launches subprocess, reads JSONL line by line
  → Each progress event → AppState.update(event) → ScanningView re-renders
  → "done" event → AppState transitions to .review, loads plan CSV
User reviews and clicks Apply
  → PythonBridge.apply() launches subprocess
  → AppState transitions to .done with result
User clicks Undo
  → PythonBridge.undo() launches subprocess
```

## Error Handling

- **Ollama not running** — `suggest-taxonomy` and `scan` emit `{"event": "error", ...}`. App shows inline error in right pane with a "Start Ollama" button that runs `open -a Ollama`.
- **Python not found** — `PythonBridge` checks for `python3` on launch. If missing, shows a one-time setup prompt with install instructions.
- **Folder access denied** — `NSOpenPanel` handles permissions. Security-scoped bookmarks used for persisted output folder.
- **Subprocess exits non-zero** — treat as error, show stderr in right pane.

## Not in Scope (v1)

- Bundled Python or Ollama
- App Store / notarization / code signing for distribution
- Multiple simultaneous scans
- Light mode
- Drag-and-drop folder input
- Preferences window (settings live in sidebar)
