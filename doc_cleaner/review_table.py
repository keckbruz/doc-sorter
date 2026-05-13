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

    def run(self) -> None:
        pass
