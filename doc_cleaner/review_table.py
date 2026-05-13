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
        return [("", "Review table (stub)\n")]

    def run(self) -> None:
        pass
