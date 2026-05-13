from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from doc_cleaner.classifier.schema import UndoManifest


@dataclass
class UndoResult:
    restored: int = 0
    skipped: int = 0
    conflicts: list[str] = field(default_factory=list)


def undo_moves(manifest_path: Path) -> UndoResult:
    manifest = UndoManifest.model_validate_json(manifest_path.read_text())
    result = UndoResult()

    for entry in manifest.entries:
        src = Path(entry.applied_path)
        dst = Path(entry.original_path)

        if not src.exists():
            result.conflicts.append(f"Applied path no longer exists: {src}")
            result.skipped += 1
            continue

        if dst.exists():
            result.conflicts.append(
                f"Original path is occupied, cannot restore: {dst}. "
                f"Applied file remains at: {src}"
            )
            result.skipped += 1
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            result.restored += 1
        except Exception as e:
            result.conflicts.append(f"Error restoring {src} → {dst}: {e}")
            result.skipped += 1

    return result
