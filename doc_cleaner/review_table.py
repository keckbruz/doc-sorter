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
