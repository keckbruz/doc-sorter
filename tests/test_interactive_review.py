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

    mock_apply.assert_called_once_with(
        plan, undo,
        yes=True,
        apply_all_above_threshold=False,
        confidence_threshold=0,
    )
    # Verify approved=true was written to CSV
    with open(plan) as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["approved"] == "true"
