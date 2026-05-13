from pathlib import Path
import csv
import pytest
from doc_cleaner.planner import PlanWriter, compute_target
from doc_cleaner.classifier.schema import PlanRow


def _row(**kwargs) -> PlanRow:
    defaults = dict(
        approved=False, status="planned",
        original_path="/tmp/a.pdf", target_path="/out/a.pdf",
        category="Finance", suggested_filename="a.pdf",
        confidence=90, needs_review=False, reason="test",
        file_size=1024, file_hash="abc", modified_time="2024-01-01T00:00:00",
        extractor="pdf", model="qwen3.5:9b",
    )
    defaults.update(kwargs)
    return PlanRow(**defaults)


def test_plan_writer_creates_csv(tmp_path):
    csv_path = tmp_path / "plan.csv"
    with PlanWriter(csv_path) as writer:
        writer.write(_row())

    assert csv_path.exists()
    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 1
    assert rows[0]["category"] == "Finance"


def test_plan_writer_creates_jsonl(tmp_path):
    csv_path = tmp_path / "plan.csv"
    jsonl_path = tmp_path / "plan.jsonl"
    with PlanWriter(csv_path, jsonl_path) as writer:
        writer.write(_row())

    lines = jsonl_path.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    data = json.loads(lines[0])
    assert data["category"] == "Finance"


def test_compute_target_basic(tmp_path):
    seen: set[Path] = set()
    result = compute_target(tmp_path, "Finance", "Banking", "2024-01-01 - Bank.pdf", seen)
    assert result == tmp_path / "Finance" / "Banking" / "2024-01-01 - Bank.pdf"
    assert result in seen


def test_compute_target_collision(tmp_path):
    existing = tmp_path / "Finance" / "Banking" / "file.pdf"
    existing.parent.mkdir(parents=True)
    existing.touch()

    seen: set[Path] = {existing}
    result = compute_target(tmp_path, "Finance", "Banking", "file.pdf", seen)
    assert result != existing
    assert "file (2)" in result.name or "-" in result.stem


def test_compute_target_no_subcategory(tmp_path):
    seen: set[Path] = set()
    result = compute_target(tmp_path, "Review", None, "unknown.pdf", seen)
    assert str(result) == str(tmp_path / "Review" / "unknown.pdf")


def test_compute_target_path_traversal_blocked(tmp_path):
    seen: set[Path] = set()
    with pytest.raises(ValueError, match="Path traversal"):
        compute_target(tmp_path, "../evil", None, "bad.pdf", seen)


def test_plan_writer_writes_multiple_rows(tmp_path):
    csv_path = tmp_path / "plan.csv"
    with PlanWriter(csv_path) as writer:
        writer.write(_row(category="Finance"))
        writer.write(_row(category="Legal"))

    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 2
    cats = [r["category"] for r in rows]
    assert "Finance" in cats
    assert "Legal" in cats
