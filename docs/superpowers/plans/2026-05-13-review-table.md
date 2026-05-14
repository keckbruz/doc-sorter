# Review Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the prompt-based interactive review workflow with a prompt_toolkit full-screen review table that supports arrow navigation, inline editing of proposed name and category, macOS Preview, and an iterative apply loop.

**Architecture:** `doc_cleaner/review_table.py` is a self-contained prompt_toolkit `Application` that owns all UI state and calls an `apply_callback` (provided by `interactive.py`) when the user triggers an apply action. `interactive.py` provides the callback, which marks CSV rows as approved and calls the existing `apply_plan`. The table stays open after "Apply confident" and closes only on "Apply all" or "Cancel".

**Tech Stack:** `prompt_toolkit>=3.0`, existing `typer`, `rich`, `doc_cleaner.applier.apply_plan`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `doc_cleaner/review_table.py` | Rewrite | ReviewRow dataclass, helpers, ReviewTableApp |
| `tests/test_review_table.py` | Create | Unit tests for data model and render |
| `doc_cleaner/interactive.py` | Modify | CSV→ReviewRows, apply callback, call ReviewTableApp |
| `pyproject.toml` | Modify | Add `prompt_toolkit>=3.0` dependency |
| `try_review.py` | Modify | Update for new ReviewRow signature |

---

## Task 1: ReviewRow dataclass + helper functions

**Files:**
- Rewrite: `doc_cleaner/review_table.py`
- Create: `tests/test_review_table.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_review_table.py
from pathlib import Path
from doc_cleaner.review_table import ReviewRow, _status_str, _is_confident, _is_applicable

def _row(**kw):
    defaults = dict(
        original_path=Path("/docs/a.pdf"),
        original_name="a.pdf",
        target_path=Path("/out/Finance/Invoices/2024-01-01 - X.pdf"),
        new_name="2024-01-01 - X.pdf",
        category="Finance/Invoices",
        confidence=95,
        needs_review=False,
    )
    return ReviewRow(**{**defaults, **kw})

def test_status_excluded():
    assert _status_str(_row(excluded=True)) == "skip"

def test_status_user_edited():
    assert _status_str(_row(user_edited=True)) == "✓ edited"

def test_status_needs_review():
    assert _status_str(_row(confidence=60, needs_review=True)) == "⚠ review"

def test_status_planned():
    assert _status_str(_row()) == "✓"

def test_is_confident_above():
    assert _is_confident(_row(confidence=95), threshold=90)

def test_is_confident_below():
    assert not _is_confident(_row(confidence=89), threshold=90)

def test_is_confident_excluded():
    assert not _is_confident(_row(excluded=True), threshold=90)

def test_is_applicable_normal():
    assert _is_applicable(_row())

def test_is_applicable_review_category():
    assert not _is_applicable(_row(category="Review"))

def test_is_applicable_excluded():
    assert not _is_applicable(_row(excluded=True))

def test_is_applicable_needs_review_but_has_category():
    # low confidence but still has a real classification — applicable for "Apply all"
    assert _is_applicable(_row(confidence=60, needs_review=True))
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `review_table` doesn't export these yet.

- [ ] **Step 3: Rewrite `doc_cleaner/review_table.py` with dataclass and helpers only**

Replace the entire file with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ACTION_APPLY_CONFIDENT = "apply_confident"
ACTION_APPLY_ALL = "apply_all"
ACTION_CANCEL = "cancel"

_COL_ORIG = 30
_COL_NAME = 38
_COL_CAT = 22


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


@dataclass
class ReviewRow:
    original_path: Path
    original_name: str
    target_path: Path
    new_name: str
    category: str
    confidence: int
    needs_review: bool
    excluded: bool = False
    user_edited: bool = False


def _status_str(row: ReviewRow) -> str:
    if row.excluded:
        return "skip"
    if row.user_edited:
        return "✓ edited"
    if row.needs_review:
        return "⚠ review"
    return "✓"


def _is_confident(row: ReviewRow, threshold: int) -> bool:
    return not row.excluded and row.confidence >= threshold


def _is_applicable(row: ReviewRow) -> bool:
    return (
        not row.excluded
        and bool(row.category)
        and row.category.split("/")[0] != "Review"
    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/review_table.py tests/test_review_table.py
git commit -m "feat: ReviewRow dataclass and helper functions"
```

---

## Task 2: ReviewTableApp skeleton + action label helpers

**Files:**
- Modify: `doc_cleaner/review_table.py` — add `ReviewTableApp` class
- Modify: `tests/test_review_table.py` — add app construction tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_review_table.py`:

```python
from doc_cleaner.review_table import ReviewTableApp

def _make_app(rows=None, threshold=90):
    if rows is None:
        rows = [_row()]
    return ReviewTableApp(rows, threshold=threshold)

def test_app_initial_state():
    app = _make_app()
    assert app.cursor == 0
    assert not app.edit_mode
    assert app.edit_field == "name"
    assert app.edit_buffer == ""

def test_total_includes_three_actions():
    app = _make_app([_row(), _row(confidence=60, needs_review=True)])
    assert app._total == 5  # 2 rows + 3 actions

def test_on_action_false_for_row():
    app = _make_app([_row()])
    app.cursor = 0
    assert not app._on_action

def test_on_action_true_for_action_item():
    app = _make_app([_row()])
    app.cursor = 1  # first action
    assert app._on_action
    assert app._action_index == 0

def test_action_labels_confident_count():
    rows = [
        _row(confidence=95),
        _row(confidence=60, needs_review=True),
    ]
    app = _make_app(rows, threshold=90)
    labels = app._action_labels()
    assert "1 files" in labels[0]   # only 1 confident
    assert "2 files" in labels[1]   # both have a real category → applicable

def test_action_labels_excludes_excluded():
    rows = [_row(confidence=95), _row(confidence=95, excluded=True)]
    app = _make_app(rows, threshold=90)
    labels = app._action_labels()
    assert "1 files" in labels[0]
    assert "1 files" in labels[1]
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_review_table.py::test_app_initial_state -v
```

Expected: `ImportError` — `ReviewTableApp` not defined yet.

- [ ] **Step 3: Add `ReviewTableApp` skeleton to `review_table.py`**

Append after the helper functions (before the end of file):

```python
class ReviewTableApp:
    def __init__(
        self,
        rows: list[ReviewRow],
        threshold: int = 90,
        apply_callback: Callable[[list[ReviewRow]], None] | None = None,
    ) -> None:
        self.rows = list(rows)
        self.threshold = threshold
        self.apply_callback = apply_callback or (lambda r: None)
        self.cursor: int = 0
        self.edit_mode: bool = False
        self.edit_field: str = "name"  # "name" | "category"
        self.edit_buffer: str = ""

    @property
    def _total(self) -> int:
        return len(self.rows) + 3

    @property
    def _on_action(self) -> bool:
        return self.cursor >= len(self.rows)

    @property
    def _action_index(self) -> int:
        return self.cursor - len(self.rows)

    def _action_labels(self) -> list[str]:
        n_conf = sum(1 for r in self.rows if _is_confident(r, self.threshold))
        n_all = sum(1 for r in self.rows if _is_applicable(r))
        return [
            f"Apply confident (≥{self.threshold}) — {n_conf} files",
            f"Apply all — {n_all} files",
            "Cancel",
        ]

    def _render(self) -> list[tuple[str, str]]:
        return [("", "Review table (stub)\n")]

    def run(self) -> None:
        pass
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: all pass (including Task 1 tests).

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/review_table.py tests/test_review_table.py
git commit -m "feat: ReviewTableApp skeleton with action label helpers"
```

---

## Task 3: `_render()` — full static table

**Files:**
- Modify: `doc_cleaner/review_table.py` — replace `_render()` stub

- [ ] **Step 1: Write render tests**

Append to `tests/test_review_table.py`:

```python
def _rendered_text(app):
    return "".join(t for _, t in app._render())

def test_render_shows_original_name():
    app = _make_app([_row(original_name="allianz.pdf")])
    assert "allianz.pdf" in _rendered_text(app)

def test_render_shows_proposed_name():
    app = _make_app([_row(new_name="2024-01-01 - Allianz.pdf")])
    assert "2024-01-01 - Allianz.pdf" in _rendered_text(app)

def test_render_shows_category():
    app = _make_app([_row(category="Finance/Invoices")])
    assert "Finance/Invoices" in _rendered_text(app)

def test_render_shows_confidence():
    app = _make_app([_row(confidence=95)])
    assert "95" in _rendered_text(app)

def test_render_shows_review_status():
    app = _make_app([_row(confidence=60, needs_review=True)])
    assert "⚠ review" in _rendered_text(app)

def test_render_shows_skip_status():
    app = _make_app([_row(excluded=True)])
    assert "skip" in _rendered_text(app)

def test_render_shows_edited_status():
    app = _make_app([_row(user_edited=True, confidence=100)])
    assert "✓ edited" in _rendered_text(app)

def test_render_shows_action_labels():
    text = _rendered_text(_make_app())
    assert "Apply confident" in text
    assert "Apply all" in text
    assert "Cancel" in text

def test_render_cursor_marker_on_current_row():
    app = _make_app([_row(), _row()])
    app.cursor = 1
    text = _rendered_text(app)
    lines = text.splitlines()
    # Find data lines (skip header/sep)
    data_lines = [l for l in lines if l.startswith("▶") or l.startswith("  ") and "✓" in l]
    assert any(l.startswith("▶") for l in data_lines)
```

- [ ] **Step 2: Run to verify render tests fail**

```bash
python3 -m pytest tests/test_review_table.py -k "render" -v
```

Expected: FAIL — stub returns only "Review table (stub)\n".

- [ ] **Step 3: Replace `_render()` with full implementation**

Replace the stub `_render` method in `ReviewTableApp` with:

```python
def _render(self) -> list[tuple[str, str]]:
    sep = "  " + "─" * (_COL_ORIG + _COL_NAME + _COL_CAT + 16) + "\n"
    lines: list[tuple[str, str]] = []

    header = (
        f"  {'ORIGINAL':<{_COL_ORIG}} {'PROPOSED NAME':<{_COL_NAME}}"
        f" {'CATEGORY':<{_COL_CAT}} CONF  STATUS\n"
    )
    lines.append(("class:header", header))
    lines.append(("class:sep", sep))

    for i, row in enumerate(self.rows):
        at_cursor = self.cursor == i
        editing = at_cursor and self.edit_mode
        prefix = "▶ " if at_cursor else "  "

        orig = _truncate(row.original_name, _COL_ORIG)
        conf = str(row.confidence)
        status = _status_str(row)

        if editing and self.edit_field == "name":
            name_text = _truncate(self.edit_buffer + "█", _COL_NAME)
            cat_text = _truncate(row.category, _COL_CAT)
            name_style, cat_style = "class:field-active", "class:field-inactive"
        elif editing and self.edit_field == "category":
            name_text = _truncate(row.new_name, _COL_NAME)
            cat_text = _truncate(self.edit_buffer + "█", _COL_CAT)
            name_style, cat_style = "class:field-inactive", "class:field-active"
        else:
            name_text = _truncate(row.new_name, _COL_NAME)
            cat_text = _truncate(row.category, _COL_CAT)
            name_style = cat_style = ""

        if row.excluded:
            base = "class:row-skip"
        elif row.user_edited:
            base = "class:row-edited"
        elif row.needs_review:
            base = "class:row-review"
        else:
            base = "class:row-ok"
        if at_cursor and not editing:
            base = "class:row-cursor"

        if editing:
            lines.append((base, f"{prefix}{orig:<{_COL_ORIG}} "))
            lines.append((name_style, f"{name_text:<{_COL_NAME}}"))
            lines.append((base, " "))
            lines.append((cat_style, f"{cat_text:<{_COL_CAT}}"))
            lines.append((base, f" {conf:>4}  {status}\n"))
        else:
            lines.append((base, (
                f"{prefix}{orig:<{_COL_ORIG}} {name_text:<{_COL_NAME}}"
                f" {cat_text:<{_COL_CAT}} {conf:>4}  {status}\n"
            )))

    lines.append(("class:sep", sep))

    for i, label in enumerate(self._action_labels()):
        idx = len(self.rows) + i
        at_cursor = self.cursor == idx
        prefix = "▶ " if at_cursor else "  "
        style = "class:action-cursor" if at_cursor else "class:action"
        lines.append((style, f"{prefix}{label}\n"))

    if self.edit_mode:
        hint = "\n  ←→ switch field   ↑↓ next row   enter confirm   esc discard\n"
    else:
        hint = "\n  ↑↓ navigate   enter edit   space preview   x exclude\n"
    lines.append(("class:hint", hint))

    return lines
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/review_table.py tests/test_review_table.py
git commit -m "feat: full _render() for review table"
```

---

## Task 4: Edit mode state helpers

**Files:**
- Modify: `doc_cleaner/review_table.py` — add `_start_edit`, `_confirm_edit`, `_switch_field`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_review_table.py`:

```python
def test_start_edit_sets_state():
    app = _make_app([_row(new_name="old.pdf")])
    app._start_edit()
    assert app.edit_mode
    assert app.edit_field == "name"
    assert app.edit_buffer == "old.pdf"

def test_confirm_edit_name_updates_row():
    app = _make_app([_row(new_name="old.pdf", target_path=Path("/out/Finance/Invoices/old.pdf"))])
    app._start_edit()
    app.edit_buffer = "new.pdf"
    app._confirm_edit()
    assert app.rows[0].new_name == "new.pdf"
    assert app.rows[0].target_path.name == "new.pdf"
    assert app.rows[0].user_edited
    assert app.rows[0].confidence == 100
    assert not app.rows[0].needs_review
    assert not app.edit_mode

def test_confirm_edit_category_updates_row():
    app = _make_app([_row(category="Finance/Invoices")])
    app._start_edit()
    app._switch_field(1)   # move to category field
    app.edit_buffer = "Legal/Contracts"
    app._confirm_edit()
    assert app.rows[0].category == "Legal/Contracts"
    assert app.rows[0].user_edited

def test_switch_field_right():
    app = _make_app([_row(new_name="n.pdf", category="Finance/Invoices")])
    app._start_edit()                  # edit_field == "name", buffer == "n.pdf"
    app._switch_field(1)               # switch to category
    assert app.edit_field == "category"
    assert app.edit_buffer == "Finance/Invoices"

def test_switch_field_wraps():
    app = _make_app([_row()])
    app._start_edit()
    app._switch_field(1)   # name → category
    app._switch_field(1)   # category → name (wraps)
    assert app.edit_field == "name"

def test_switch_field_saves_buffer():
    app = _make_app([_row(new_name="n.pdf", category="Finance/Invoices")])
    app._start_edit()
    app.edit_buffer = "edited.pdf"
    app._switch_field(1)               # save "edited.pdf" into row.new_name, switch to category
    assert app.rows[0].new_name == "edited.pdf"
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_review_table.py -k "edit" -v
```

Expected: FAIL — `_start_edit`, `_confirm_edit`, `_switch_field` not defined.

- [ ] **Step 3: Add helpers to `ReviewTableApp`**

Add these three methods to `ReviewTableApp` (before `run`):

```python
def _start_edit(self) -> None:
    row = self.rows[self.cursor]
    self.edit_mode = True
    self.edit_field = "name"
    self.edit_buffer = row.new_name

def _confirm_edit(self) -> None:
    row = self.rows[self.cursor]
    if self.edit_field == "name":
        row.new_name = self.edit_buffer
        row.target_path = row.target_path.parent / self.edit_buffer
    else:
        row.category = self.edit_buffer
    row.user_edited = True
    row.confidence = 100
    row.needs_review = False
    self.edit_mode = False
    self.edit_buffer = ""

def _switch_field(self, direction: int) -> None:
    row = self.rows[self.cursor]
    # Save current buffer before switching
    if self.edit_field == "name":
        row.new_name = self.edit_buffer
    else:
        row.category = self.edit_buffer
    fields = ["name", "category"]
    self.edit_field = fields[(fields.index(self.edit_field) + direction) % len(fields)]
    self.edit_buffer = row.new_name if self.edit_field == "name" else row.category
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/review_table.py tests/test_review_table.py
git commit -m "feat: edit mode helpers — start, confirm, switch field"
```

---

## Task 5: Apply confident helper

**Files:**
- Modify: `doc_cleaner/review_table.py` — add `_do_apply_confident`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_review_table.py`:

```python
def test_apply_confident_calls_callback():
    called_with = []
    rows = [
        _row(confidence=95),
        _row(original_path=Path("/b.pdf"), original_name="b.pdf",
             target_path=Path("/out/b.pdf"), confidence=60, needs_review=True),
    ]
    app = ReviewTableApp(rows, threshold=90, apply_callback=called_with.extend)
    
    class FakeEvent:
        class app:
            @staticmethod
            def exit(): pass
    
    app._do_apply_confident(FakeEvent())
    assert len(called_with) == 1
    assert called_with[0].original_name == "a.pdf"

def test_apply_confident_removes_applied_rows():
    rows = [
        _row(confidence=95),
        _row(original_path=Path("/b.pdf"), original_name="b.pdf",
             target_path=Path("/out/b.pdf"), confidence=60, needs_review=True),
    ]
    app = ReviewTableApp(rows, threshold=90, apply_callback=lambda r: None)

    class FakeEvent:
        class app:
            @staticmethod
            def exit(): pass

    app._do_apply_confident(FakeEvent())
    assert len(app.rows) == 1
    assert app.rows[0].original_name == "b.pdf"

def test_apply_confident_exits_when_no_rows_remain():
    exited = []
    rows = [_row(confidence=95)]
    app = ReviewTableApp(rows, threshold=90, apply_callback=lambda r: None)

    class FakeEvent:
        class app:
            @staticmethod
            def exit():
                exited.append(True)

    app._do_apply_confident(FakeEvent())
    assert exited

def test_apply_confident_stays_open_when_rows_remain():
    exited = []
    rows = [
        _row(confidence=95),
        _row(original_path=Path("/b.pdf"), original_name="b.pdf",
             target_path=Path("/out/b.pdf"), confidence=60, needs_review=True),
    ]
    app = ReviewTableApp(rows, threshold=90, apply_callback=lambda r: None)

    class FakeEvent:
        class app:
            @staticmethod
            def exit():
                exited.append(True)

    app._do_apply_confident(FakeEvent())
    assert not exited   # still open — review rows remain
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_review_table.py -k "apply_confident" -v
```

Expected: FAIL — `_do_apply_confident` not defined.

- [ ] **Step 3: Add `_do_apply_confident` to `ReviewTableApp`**

```python
def _do_apply_confident(self, event: object) -> None:
    to_apply = [r for r in self.rows if _is_confident(r, self.threshold)]
    if to_apply:
        self.apply_callback(to_apply)
        applied = {r.original_path for r in to_apply}
        self.rows = [r for r in self.rows if r.original_path not in applied]
        self.cursor = max(0, min(self.cursor, self._total - 1))
    if not self.rows:
        event.app.exit()  # type: ignore[attr-defined]
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/review_table.py tests/test_review_table.py
git commit -m "feat: _do_apply_confident removes applied rows, exits when empty"
```

---

## Task 6: Full `run()` with key bindings

**Files:**
- Modify: `doc_cleaner/review_table.py` — replace `run()` stub with full implementation
- Modify: `pyproject.toml` — add `prompt_toolkit>=3.0`

- [ ] **Step 1: Add `prompt_toolkit` to `pyproject.toml`**

In the `dependencies` list, add after `pyyaml`:

```toml
"prompt_toolkit>=3.0",
```

- [ ] **Step 2: Install**

```bash
pip3 install -e ".[dev]" -q
```

- [ ] **Step 3: Replace `run()` with full key-binding implementation**

Replace the stub `run` method in `ReviewTableApp`:

```python
def run(self) -> None:
    import subprocess
    from prompt_toolkit import Application
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    kb = KeyBindings()
    in_edit = Condition(lambda: self.edit_mode)
    not_edit = Condition(lambda: not self.edit_mode)

    @kb.add("up", filter=not_edit)
    def _up(event):
        self.cursor = max(0, self.cursor - 1)

    @kb.add("down", filter=not_edit)
    def _down(event):
        self.cursor = min(self._total - 1, self.cursor + 1)

    @kb.add("enter", filter=not_edit)
    def _enter(event):
        if self._on_action:
            idx = self._action_index
            if idx == 0:
                self._do_apply_confident(event)
            elif idx == 1:
                to_apply = [r for r in self.rows if _is_applicable(r)]
                self.apply_callback(to_apply)
                event.app.exit()
            else:
                event.app.exit()
        else:
            self._start_edit()

    @kb.add("space", filter=not_edit)
    def _preview(event):
        if not self._on_action:
            subprocess.Popen(["open", str(self.rows[self.cursor].original_path)])

    @kb.add("x", filter=not_edit)
    def _exclude(event):
        if not self._on_action:
            r = self.rows[self.cursor]
            r.excluded = not r.excluded

    @kb.add("left", filter=in_edit)
    def _field_left(event):
        self._switch_field(-1)

    @kb.add("right", filter=in_edit)
    def _field_right(event):
        self._switch_field(1)

    @kb.add("up", filter=in_edit)
    def _edit_up(event):
        self._confirm_edit()
        self.cursor = max(0, self.cursor - 1)
        if not self._on_action:
            self._start_edit()

    @kb.add("down", filter=in_edit)
    def _edit_down(event):
        self._confirm_edit()
        next_cur = min(len(self.rows) - 1, self.cursor + 1)
        self.cursor = next_cur
        if not self._on_action:
            self._start_edit()

    @kb.add("enter", filter=in_edit)
    def _edit_confirm(event):
        self._confirm_edit()

    @kb.add("escape", filter=in_edit)
    def _edit_discard(event):
        self.edit_mode = False
        self.edit_buffer = ""

    @kb.add("backspace", filter=in_edit)
    def _backspace(event):
        self.edit_buffer = self.edit_buffer[:-1]

    @kb.add("<any>", filter=in_edit)
    def _char(event):
        data = event.data
        if data and len(data) == 1 and ord(data) >= 32:
            self.edit_buffer += data

    style = Style.from_dict({
        "header": "bold",
        "sep": "ansibrightblack",
        "row-ok": "",
        "row-review": "ansiyellow",
        "row-skip": "ansibrightblack",
        "row-edited": "ansigreen",
        "row-cursor": "reverse",
        "field-active": "bg:ansiblue bold",
        "field-inactive": "ansibrightblack",
        "action": "",
        "action-cursor": "bold reverse",
        "hint": "ansibrightblack italic",
    })

    layout = Layout(Window(content=FormattedTextControl(self._render)))
    app = Application(
        layout=layout, key_bindings=kb, style=style, full_screen=True
    )
    app.run()
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python3 -m pytest tests/test_review_table.py -v
```

Expected: all pass (run() is not unit-tested directly — it requires a TTY).

- [ ] **Step 5: Smoke-test manually with try_review.py**

Update `try_review.py` to match the new `ReviewRow` signature (add `target_path`):

```python
"""Quick prototype test — run with: python3 try_review.py"""
from pathlib import Path
from doc_cleaner.review_table import ReviewRow, ReviewTableApp

rows = [
    ReviewRow(Path("test_input/Finance/allianz_beitragsrechnung.pdf"),
              "allianz_beitragsrechnung.pdf",
              Path("/tmp/out/Finance/Invoices/2024-03-12 - Allianz SE - Beitragsrechnung.pdf"),
              "2024-03-12 - Allianz SE - Beitragsrechnung.pdf", "Finance/Invoices", 95, False),
    ReviewRow(Path("test_input/Finance/amazon_quittung.txt"),
              "amazon_quittung.txt",
              Path("/tmp/out/Finance/Receipts/2024-02-15 - Amazon.de - Receipt.txt"),
              "2024-02-15 - Amazon.de - Receipt.txt", "Finance/Receipts", 95, False),
    ReviewRow(Path("test_input/Finance/finanzamt_steuerbescheid.pdf"),
              "finanzamt_steuerbescheid.pdf",
              Path("/tmp/out/Finance/Taxes/2024-01-20 - Finanzamt - Steuerbescheid.pdf"),
              "2024-01-20 - Finanzamt - Steuerbescheid.pdf", "Finance/Taxes", 95, False),
    ReviewRow(Path("test_input/Finance/sparkasse_kontoauszug.pdf"),
              "sparkasse_kontoauszug.pdf",
              Path("/tmp/out/Finance/Banking/2024-01-01 - Sparkasse - Kontoauszug.pdf"),
              "2024-01-01 - Sparkasse - Kontoauszug.pdf", "Finance/Banking", 95, False),
    ReviewRow(Path("test_docs/generated/edge_cases/deep_document.txt"),
              "deep_document.txt",
              Path("/tmp/out/Finance/Invoices/2024-01-01 - Unknown - Invoice.txt"),
              "2024-01-01 - Unknown - Invoice.txt", "Finance/Invoices", 60, True),
    ReviewRow(Path("test_docs/generated/edge_cases/ambiguous_letter.txt"),
              "ambiguous_letter.txt",
              Path("/tmp/out/Personal/Other/[no date] - Unknown - Other.txt"),
              "[no date] - Unknown - Other.txt", "Personal/Other", 60, True),
]

ReviewTableApp(rows, threshold=90, apply_callback=lambda r: print(f"\nWould apply: {[x.original_name for x in r]}")).run()
```

Run it:

```bash
python3 try_review.py
```

Verify: table renders, navigation works, `→` enters edit mode with active field highlighted, `space` opens a PDF in Preview, `x` marks row as skip, action items respond to `enter`.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/review_table.py pyproject.toml try_review.py
git commit -m "feat: full ReviewTableApp with key bindings and prompt_toolkit"
```

---

## Task 7: Update `interactive.py` — CSV → ReviewRows + apply callback

**Files:**
- Modify: `doc_cleaner/interactive.py` — add helpers, update `scan_folder()`

- [ ] **Step 1: Write failing tests**

Create `tests/test_interactive_review.py`:

```python
import csv
from pathlib import Path
from doc_cleaner.interactive import _read_plan_as_review_rows, _make_apply_callback

def _write_plan(tmp_path, rows):
    plan = tmp_path / "plan.csv"
    fieldnames = [
        "approved", "status", "original_path", "target_path",
        "category", "subcategory", "suggested_filename",
        "confidence", "needs_review", "document_date", "sender",
        "document_type", "reason", "file_size", "file_hash",
        "modified_time", "extractor", "model", "error",
    ]
    with open(plan, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = {k: "" for k in fieldnames}
            row.update(r)
            w.writerow(row)
    return plan


def test_read_plan_builds_review_rows(tmp_path):
    plan = _write_plan(tmp_path, [{
        "original_path": str(tmp_path / "a.pdf"),
        "target_path": str(tmp_path / "out/Finance/Invoices/a.pdf"),
        "category": "Finance",
        "subcategory": "Invoices",
        "suggested_filename": "2024-01-01 - X.pdf",
        "confidence": "95",
        "needs_review": "false",
    }])
    rows = _read_plan_as_review_rows(plan)
    assert len(rows) == 1
    assert rows[0].category == "Finance/Invoices"
    assert rows[0].new_name == "2024-01-01 - X.pdf"
    assert rows[0].confidence == 95
    assert not rows[0].needs_review


def test_read_plan_no_subcategory(tmp_path):
    plan = _write_plan(tmp_path, [{
        "original_path": str(tmp_path / "a.pdf"),
        "target_path": str(tmp_path / "out/Review/a.pdf"),
        "category": "Review",
        "subcategory": "",
        "suggested_filename": "a.pdf",
        "confidence": "0",
        "needs_review": "true",
    }])
    rows = _read_plan_as_review_rows(plan)
    assert rows[0].category == "Review"


def test_apply_callback_marks_approved_and_calls_apply_plan(tmp_path, mocker):
    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF fake")
    dst = tmp_path / "out" / "Finance" / "Invoices" / "a.pdf"

    plan = _write_plan(tmp_path, [{
        "original_path": str(src),
        "target_path": str(dst),
        "category": "Finance",
        "subcategory": "Invoices",
        "suggested_filename": "a.pdf",
        "confidence": "95",
        "needs_review": "false",
        "file_hash": "",
    }])
    undo = tmp_path / "undo.json"

    mock_apply = mocker.patch("doc_cleaner.applier.apply_plan")

    from doc_cleaner.review_table import ReviewRow
    callback = _make_apply_callback(plan, undo)
    row = ReviewRow(src, "a.pdf", dst, "a.pdf", "Finance/Invoices", 95, False)
    callback([row])

    mock_apply.assert_called_once()
    # Verify approved=true was written to CSV
    with open(plan) as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["approved"] == "true"
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_interactive_review.py -v
```

Expected: FAIL — `_read_plan_as_review_rows` and `_make_apply_callback` not in `interactive.py`.

- [ ] **Step 3: Add helpers to `interactive.py`**

Add these two functions after the existing imports in `doc_cleaner/interactive.py`:

```python
def _read_plan_as_review_rows(plan_csv: Path) -> list:
    import csv as _csv
    from doc_cleaner.review_table import ReviewRow
    rows = []
    with open(plan_csv, newline="", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            cat = row["category"]
            if row.get("subcategory"):
                cat = f"{cat}/{row['subcategory']}"
            rows.append(ReviewRow(
                original_path=Path(row["original_path"]),
                original_name=Path(row["original_path"]).name,
                target_path=Path(row["target_path"]),
                new_name=row["suggested_filename"],
                category=cat,
                confidence=int(row["confidence"] or 0),
                needs_review=row["needs_review"].lower() == "true",
            ))
    return rows


def _make_apply_callback(plan_csv: Path, undo_path: Path):
    import csv as _csv
    from doc_cleaner.applier import apply_plan

    def apply(rows: list) -> None:
        from doc_cleaner.applier import apply_plan  # import here so tests can patch doc_cleaner.applier.apply_plan

        approved = {str(r.original_path): r for r in rows}

        rows_data = []
        with open(plan_csv, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            for row_data in reader:
                path = row_data["original_path"]
                if path in approved:
                    row_data["approved"] = "true"
                    review_row = approved[path]
                    if review_row.user_edited:
                        row_data["target_path"] = str(review_row.target_path)
                        row_data["suggested_filename"] = review_row.new_name
                rows_data.append(row_data)

        with open(plan_csv, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_data)

        apply_plan(
            plan_csv, undo_path,
            yes=True,
            apply_all_above_threshold=False,
            confidence_threshold=0,
        )

    return apply
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python3 -m pytest tests/test_interactive_review.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/interactive.py tests/test_interactive_review.py
git commit -m "feat: CSV→ReviewRows and apply callback for interactive review"
```

---

## Task 8: Wire ReviewTableApp into `scan_folder()`

**Files:**
- Modify: `doc_cleaner/interactive.py` — replace old select() apply flow in `scan_folder()`

- [ ] **Step 1: Replace the `scan_folder()` function body in `interactive.py`**

Replace the entire `scan_folder` function with:

```python
def scan_folder(console: Console) -> None:
    from doc_cleaner.cli import scan
    from doc_cleaner.review_table import ReviewTableApp

    input_dir = Path(typer.prompt("Folder to scan", default=str(Path.cwd()))).expanduser()
    while not input_dir.is_dir():
        console.print(f"[red]Folder not found:[/red] {input_dir}")
        input_dir = Path(typer.prompt("Folder to scan", default=str(Path.cwd()))).expanduser()

    output_root = Path(typer.prompt("Sorted output folder")).expanduser()
    model = typer.prompt("Ollama model", default="qwen3.5:9b")
    threshold = typer.prompt("Confidence threshold", default=90, type=int)

    plan_path, jsonl_path, undo_path = default_plan_paths()
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    console.print()
    scan(
        input=input_dir,
        output_root=output_root,
        model=model,
        ollama_host="http://127.0.0.1:11434",
        allow_remote_ollama=False,
        plan=plan_path,
        jsonl=jsonl_path,
        dry_run=True,
        confidence_threshold=threshold,
        max_files=None,
        max_depth=None,
        include_hidden=False,
        follow_symlinks=False,
        ocr=False,
        ocr_language="deu+eng",
        workers=1,
        max_text_chars=4000,
        cache_dir=None,
        taxonomy=None,
        limit=None,
        verbose=False,
        quiet=False,
    )

    rows = _read_plan_as_review_rows(plan_path)
    if not rows:
        console.print("[yellow]No files to review.[/yellow]")
        return

    apply_cb = _make_apply_callback(plan_path, undo_path)
    ReviewTableApp(rows, threshold=threshold, apply_callback=apply_cb).run()

    console.print(f"\n[green]Done.[/green] Undo manifest: {undo_path}")
```

- [ ] **Step 2: Remove now-unused imports from `interactive.py`**

The old `scan_folder` used `apply_plan` and `select`. Check the rest of the file still uses them (they're used in `apply_existing_plan` and `run`). If `apply_plan` is only in the helpers now (imported inside `_make_apply_callback`), remove the top-level import if present.

Run:

```bash
python3 -c "from doc_cleaner.interactive import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: End-to-end smoke test**

```bash
python3 -m doc_cleaner ui
```

Walk through: enter a folder path (e.g., `test_input`), output root (`/tmp/review-test`), default model, default threshold. Verify scan runs, review table opens, navigation and edit mode work. Press Cancel to exit without moving files.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/interactive.py
git commit -m "feat: wire ReviewTableApp into scan_folder interactive flow"
```

---

## Task 9: Final cleanup + full test run

**Files:**
- Modify: `pyproject.toml` — verify `prompt_toolkit>=3.0` is present
- Modify: `try_review.py` — already updated in Task 6

- [ ] **Step 1: Verify pyproject.toml has prompt_toolkit**

```bash
grep prompt_toolkit pyproject.toml
```

Expected: `"prompt_toolkit>=3.0",`

If missing, add it to the `dependencies` list.

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass (no regressions).

- [ ] **Step 3: Commit pyproject.toml if changed**

```bash
git add pyproject.toml
git commit -m "chore: add prompt_toolkit>=3.0 dependency"
```

- [ ] **Step 4: Clean up old prototype artifacts**

The prototype `try_review.py` at the project root is a dev tool, not part of the package. Leave it in place — it's useful for future iteration. No action needed.

- [ ] **Step 5: Final commit tag**

```bash
git log --oneline -5
```

Verify the feature is complete with clean commits.
