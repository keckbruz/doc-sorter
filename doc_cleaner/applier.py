from __future__ import annotations
import csv
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from doc_cleaner.classifier.schema import UndoEntry, UndoManifest
from doc_cleaner.utils import safe_move


@dataclass
class ApplyResult:
    moved: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def apply_plan(
    plan_path: Path,
    undo_path: Path,
    yes: bool = False,
    apply_all_above_threshold: bool = False,
    confidence_threshold: int = 90,
) -> ApplyResult:
    rows = _read_rows(plan_path, apply_all_above_threshold, confidence_threshold)

    if not yes:
        import typer
        from rich.console import Console
        console = Console()
        console.print(f"\n[bold]About to move {len(rows)} files.[/bold]")
        confirmed = typer.confirm("Proceed?", default=False)
        if not confirmed:
            console.print("Aborted.")
            raise typer.Exit()

    entries: list[UndoEntry] = []
    result = ApplyResult()

    for row in rows:
        src = Path(row["original_path"])
        dst = Path(row["target_path"])

        if not src.exists():
            result.errors.append(f"Source not found: {src}")
            continue

        current_hash = _sha256(src)
        expected_hash = row.get("file_hash", "")
        if expected_hash and current_hash != expected_hash:
            result.skipped += 1
            result.errors.append(f"Hash mismatch (file changed since scan): {src}")
            continue

        try:
            actual_dst = safe_move(src, dst)
            entries.append(UndoEntry(
                original_path=str(src),
                applied_path=str(actual_dst),
                file_hash=current_hash,
                moved_at=datetime.now().isoformat(),
            ))
            result.moved += 1
        except Exception as e:
            result.errors.append(f"Error moving {src}: {e}")

    manifest = UndoManifest(
        created_at=datetime.now().isoformat(),
        entries=entries,
    )
    undo_path.parent.mkdir(parents=True, exist_ok=True)
    undo_path.write_text(manifest.model_dump_json(indent=2))

    _write_undo_script(undo_path.with_suffix(".sh"), entries)

    return result


def _read_rows(
    plan_path: Path,
    apply_all_above_threshold: bool,
    confidence_threshold: int,
) -> list[dict]:
    with open(plan_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    approved = []
    for row in rows:
        is_approved = row.get("approved", "").lower() == "true"
        confidence = int(row.get("confidence", 0) or 0)
        if is_approved or (apply_all_above_threshold and confidence >= confidence_threshold):
            approved.append(row)
    return approved


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_undo_script(sh_path: Path, entries: list[UndoEntry]) -> None:
    lines = ["#!/bin/bash", "# Undo script — moves files back to original locations", "set -e", ""]
    for entry in entries:
        lines.append(f'mv "{entry.applied_path}" "{entry.original_path}"')
    sh_path.write_text("\n".join(lines) + "\n")
    sh_path.chmod(0o755)
