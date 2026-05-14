# Review Table Design
_Date: 2026-05-13_
_Status: Approved_

## Goal

Replace the current prompt-based interactive workflow with a prompt_toolkit interactive review table. The user reviews classified documents, edits proposed names and categories, previews files, and applies moves in an iterative loop — all without leaving the terminal.

## Entry Point

`python -m doc_cleaner` (no args) → runs scan → opens review table
`doc-sorter ui` → same

## Review Table

Built with `prompt_toolkit.Application` (full_screen=True). Renders a table of `ReviewRow` objects with live key bindings.

### Columns

```
ORIGINAL NAME   PROPOSED NAME   CATEGORY   CONF   STATUS
```

- ORIGINAL NAME: read-only, truncated
- PROPOSED NAME: editable (edit mode)
- CATEGORY: editable (edit mode)
- CONF: read-only integer; user-edited rows show 100
- STATUS: ✓ planned / ⚠ review / skip / ✓ edited

### Review Mode Controls

| Key | Action |
|-----|--------|
| ↑ / ↓ | Navigate rows and action items |
| enter | Enter edit mode (on a data row) / execute (on an action item) |
| space | Open file in macOS Preview (`open <path>`) |
| x | Toggle exclude (skip) |

### Edit Mode Controls

| Key | Action |
|-----|--------|
| ← / → | Switch between Proposed Name and Category fields |
| ↑ / ↓ | Confirm edit + move to prev/next row (stay in edit mode) |
| enter | Confirm edit + exit edit mode |
| esc | Discard edit + exit edit mode |
| type / backspace | Edit current field; cursor always at end |

After any edit, row confidence is set to 100 and status becomes "✓ edited".

### Action Items (bottom of table)

Live counts update as rows are edited or excluded.

| Action | Behaviour |
|--------|-----------|
| Apply confident (≥90) — N files | Calls apply callback, removes applied rows, table stays open |
| Apply all — N files | Applies all with a classification (not excluded), table closes |
| Cancel | Closes table, nothing more applied |

"Apply all" skips: excluded rows, and rows with no classification (complete failures).

## Architecture

### `doc_cleaner/review_table.py` (replace current prototype)

```
@dataclass ReviewRow
    original_path: Path
    original_name: str
    new_name: str
    category: str
    confidence: int
    needs_review: bool
    excluded: bool = False
    user_edited: bool = False

class ReviewTableApp
    __init__(rows, threshold=90, apply_callback)
    run() -> (rows, action)
```

- `apply_callback(rows_to_apply: list[ReviewRow]) -> None` — called when Apply confident is selected; caller handles actual file moves
- Two editable fields per row, tracked as `edit_field: Literal["name", "category"]`
- Edit buffer always appended/backspaced (no internal cursor movement)
- `full_screen=True` for clean alternate-screen rendering

### `doc_cleaner/interactive.py` (updated)

The apply loop lives here:
```
scan → collect PlanRows → build ReviewRows → open ReviewTableApp
  if ACTION_APPLY_CONFIDENT → apply_plan(confident_rows), re-enter loop with remainder
  if ACTION_APPLY_ALL → apply_plan(all_with_classification)
  if ACTION_CANCEL → exit
```

### `pyproject.toml`

Add `prompt_toolkit>=3.0` to dependencies.

## Out of Scope

- Scrolling within the table (acceptable for v1 — most scans are <50 files)
- Editing confidence value directly
- Multi-select (bulk edit multiple rows at once)
