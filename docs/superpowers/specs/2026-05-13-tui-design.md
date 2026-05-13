# TUI Design — doc-cleaner Interactive Terminal UI

**Date:** 2026-05-13
**Status:** Approved

## Goal

Replace the long bash command workflow with an interactive Textual TUI. User opens a terminal in the folder they want sorted, runs `python -m doc_cleaner` with no arguments, and is guided through the full scan → review → apply pipeline without ever typing a flag.

## Entry Point

- `python -m doc_cleaner` (no args) → launches TUI
- `python -m doc_cleaner ui` → explicit alias
- All existing subcommands (`scan`, `apply`, `undo`, `doctor`) remain unchanged

`__main__.py` checks `sys.argv` — if no subcommand is given, it calls `tui.run()` instead of `app()`.

## Three-Screen Flow

### Screen 1 — Config

Shown on launch. Collects the three required inputs before scanning can begin.

| Field | Default | Notes |
|-------|---------|-------|
| Input folder | `Path.cwd()` | Editable — user can change if needed |
| Output root | _(empty)_ | Where sorted files will be placed |
| Model | `qwen3.5:9b` | Ollama model name |

- "Start Scan" button is disabled until output root is non-empty
- On start: validates paths exist, then switches to Scan screen
- Ollama auto-start runs as first step of the scan worker (same logic as CLI)

### Screen 2 — Scan

Runs the scan pipeline in a Textual background worker. UI updates are posted from the worker thread via `app.call_from_thread`.

Displays:
- Current file being processed (truncated path)
- Live counters: Scanned / Classified / Needs Review / Errors
- No progress bar (total file count is unknown upfront)

On completion: automatically switches to Review screen, passing the collected `PlanRow` list in memory (no intermediate CSV written at this stage).

### Screen 3 — Review

DataTable with one row per scanned file.

Columns: `✓ | Filename | Category | Suggested Name | Confidence | Status`

Keyboard controls:
- `↑` / `↓` — navigate rows
- `space` or `enter` — toggle approved on highlighted row
- `a` — approve all rows with status `planned`
- `n` — clear all approvals

Buttons:
- **Apply** — writes plan CSV to `plans/plan-<timestamp>.csv`, calls `apply_plan`, shows inline result summary (moved / skipped / errors / undo path)
- **Export CSV** — writes plan CSV without applying (for external review)

After apply: result summary replaces the button row. Undo manifest path is shown so the user knows where to find it.

## Architecture

### New file: `doc_cleaner/tui.py`

Contains:
- `ProgressUpdate` message (current file, counters)
- `ScanDone` message (list of PlanRow objects)
- `ConfigScreen(Screen)` — input widgets + Start button
- `ScanScreen(Screen)` — progress display + background worker
- `ReviewScreen(Screen)` — DataTable + Apply/Export buttons
- `DocCleanerApp(App)` — wires screens together
- `run()` — public entry point called from `__main__.py`

The scan worker reuses the same core modules as the CLI scan command: `scan_files`, `extract_text`, `OllamaClient`, `build_prompt`, `compute_target`, `PlanWriter` etc. No logic is duplicated — only the loop moves from `cli.py` into the worker.

### Modified files

| File | Change |
|------|--------|
| `doc_cleaner/__main__.py` | Launch TUI when `len(sys.argv) == 1` |
| `doc_cleaner/cli.py` | Add `ui` command that calls `tui.run()` |
| `pyproject.toml` | Add `textual>=0.50` to dependencies |

## Error Handling

- **Ollama not running:** worker tries auto-start (same as CLI), shows status in Scan screen. If it fails to start, shows error and returns to Config screen.
- **Invalid input path:** validated on Start button press, shown inline on Config screen.
- **File errors during scan:** counted as errors, shown in counters, do not abort scan.
- **Apply errors:** shown inline in result summary after apply.

## Out of Scope

- File browser widget for path selection (typed input is sufficient)
- Editing the suggested target path per-row in the TUI (use Export CSV + Numbers for that)
- Parallel scanning workers (sequential, same as CLI default)
