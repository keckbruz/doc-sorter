from pathlib import Path
import csv
import json
import pytest
from doc_cleaner.applier import apply_plan
from doc_cleaner.classifier.schema import UndoManifest


def _write_plan(path: Path, rows: list[dict]) -> None:
    columns = [
        "approved", "status", "original_path", "target_path", "category",
        "subcategory", "document_date", "sender", "document_type",
        "suggested_filename", "confidence", "needs_review", "reason",
        "file_size", "file_hash", "modified_time", "extractor", "model", "error",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            full = {c: row.get(c, "") for c in columns}
            writer.writerow(full)


def test_apply_moves_approved_file(tmp_path):
    src = tmp_path / "src" / "invoice.pdf"
    src.parent.mkdir(parents=True)
    src.write_text("Invoice content")
    dst = tmp_path / "out" / "Finance" / "invoice.pdf"

    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()

    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": h,
        "file_size": "15",
    }])

    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 1
    assert result.skipped == 0
    assert dst.exists()
    assert not src.exists()


def test_apply_skips_unapproved(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "false",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": "abc",
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 0
    assert src.exists()


def test_apply_does_not_overwrite(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    dst.parent.mkdir(parents=True)
    dst.write_text("existing!")  # target already exists

    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": h,
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    # File should be moved to a collision-safe path, not overwriting dst
    assert dst.read_text() == "existing!"
    assert result.moved == 1


def test_apply_writes_undo_manifest(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true", "status": "planned",
        "original_path": str(src), "target_path": str(dst),
        "file_hash": h, "file_size": "7",
    }])
    apply_plan(plan, undo, yes=True)
    assert undo.exists()
    manifest = UndoManifest.model_validate_json(undo.read_text())
    assert len(manifest.entries) == 1
    assert manifest.entries[0].original_path == str(src)


def test_apply_skips_hash_mismatch(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true", "status": "planned",
        "original_path": str(src), "target_path": str(dst),
        "file_hash": "wronghash000",
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 0
    assert result.skipped == 1
    assert src.exists()
