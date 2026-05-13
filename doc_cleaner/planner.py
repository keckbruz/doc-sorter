from __future__ import annotations
import csv
import hashlib
from pathlib import Path
from typing import Optional
from doc_cleaner.classifier.schema import PlanRow
from doc_cleaner.utils import safe_target_path

CSV_COLUMNS = [
    "approved", "status", "original_path", "target_path", "category",
    "subcategory", "document_date", "sender", "document_type",
    "suggested_filename", "confidence", "needs_review", "reason",
    "file_size", "file_hash", "modified_time", "extractor", "model", "error",
]


class PlanWriter:
    def __init__(self, csv_path: Path, jsonl_path: Optional[Path] = None):
        self.csv_path = csv_path
        self.jsonl_path = jsonl_path
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        self._writer.writeheader()
        if jsonl_path:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._jsonl_file = open(jsonl_path, "w", encoding="utf-8")
        else:
            self._jsonl_file = None

    def write(self, row: PlanRow) -> None:
        d = row.model_dump()
        # Booleans as lowercase strings in CSV
        d["approved"] = str(d["approved"]).lower()
        d["needs_review"] = str(d["needs_review"]).lower()
        # None → empty string
        for k, v in d.items():
            if v is None:
                d[k] = ""
        self._writer.writerow(d)
        self._csv_file.flush()
        if self._jsonl_file:
            self._jsonl_file.write(row.model_dump_json() + "\n")
            self._jsonl_file.flush()

    def close(self) -> None:
        self._csv_file.close()
        if self._jsonl_file:
            self._jsonl_file.close()

    def __enter__(self) -> "PlanWriter":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def compute_target(
    output_root: Path,
    category: str,
    subcategory: Optional[str],
    suggested_filename: str,
    existing_paths: set[Path],
) -> Path:
    # Raises ValueError on path traversal
    base = safe_target_path(output_root, category, subcategory, suggested_filename)

    if base not in existing_paths:
        existing_paths.add(base)
        return base

    # Collision resolution
    stem = base.stem
    suffix = base.suffix
    parent = base.parent
    for i in range(2, 100):
        candidate = parent / f"{stem} ({i}){suffix}"
        if candidate not in existing_paths:
            existing_paths.add(candidate)
            return candidate

    # Last resort hash suffix
    h = hashlib.md5(suggested_filename.encode()).hexdigest()[:6]
    fallback = parent / f"{stem}-{h}{suffix}"
    existing_paths.add(fallback)
    return fallback
