import pytest
from pydantic import ValidationError
from doc_cleaner.classifier.schema import ClassificationResult, PlanRow, UndoEntry, UndoManifest


def test_valid_classification():
    r = ClassificationResult(
        category="Finance",
        subcategory="Insurance",
        document_date="2024-03-12",
        sender="Allianz",
        document_type="Beitragsrechnung",
        suggested_filename="2024-03-12 - Allianz - Beitragsrechnung.pdf",
        confidence=92,
        reason="Contains Allianz and invoice date.",
        needs_review=False,
    )
    assert r.confidence == 92
    assert r.needs_review is False


def test_confidence_clamped_above_100():
    r = ClassificationResult(
        category="Review", suggested_filename="x.pdf",
        confidence=150, reason="test", needs_review=True,
    )
    assert r.confidence == 100


def test_confidence_clamped_below_0():
    r = ClassificationResult(
        category="Review", suggested_filename="x.pdf",
        confidence=-5, reason="test", needs_review=True,
    )
    assert r.confidence == 0


def test_null_fields_allowed():
    r = ClassificationResult(
        category="Review",
        document_date=None,
        sender=None,
        document_type=None,
        suggested_filename="unknown.pdf",
        confidence=10,
        reason="Cannot determine",
        needs_review=True,
    )
    assert r.sender is None
    assert r.document_date is None


def test_invalid_json_raises_validation_error():
    with pytest.raises((ValidationError, TypeError)):
        ClassificationResult.model_validate({"confidence": "not-a-number"})


def test_plan_row_defaults():
    row = PlanRow(
        status="planned",
        original_path="/tmp/a.pdf",
        target_path="/out/Finance/Banking/a.pdf",
        category="Finance",
        suggested_filename="a.pdf",
        confidence=90,
        needs_review=False,
        reason="test",
        file_size=1024,
        file_hash="abc",
        modified_time="2024-01-01T00:00:00",
        extractor="pdf",
        model="qwen3.5:9b",
    )
    assert row.approved is False
    assert row.error == ""


def test_undo_manifest_roundtrip():
    entry = UndoEntry(
        original_path="/tmp/a.pdf",
        applied_path="/out/Finance/a.pdf",
        file_hash="abc123",
        moved_at="2026-05-13T10:00:00",
    )
    manifest = UndoManifest(created_at="2026-05-13T10:00:00", entries=[entry])
    json_str = manifest.model_dump_json()
    restored = UndoManifest.model_validate_json(json_str)
    assert restored.entries[0].original_path == "/tmp/a.pdf"
