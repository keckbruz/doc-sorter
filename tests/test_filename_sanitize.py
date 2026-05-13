from pathlib import Path
import pytest
from doc_cleaner.utils import sanitize_filename, safe_target_path


def test_basic_format():
    result = sanitize_filename(
        date="2024-03-12",
        sender="Allianz",
        document_type="Beitragsrechnung",
        original_stem="old_name",
        extension=".pdf",
    )
    assert result == "2024-03-12 - Allianz - Beitragsrechnung.pdf"


def test_no_date_uses_undated():
    result = sanitize_filename(
        date=None,
        sender="Sparkasse",
        document_type="Kontoauszug",
        original_stem="stmt",
        extension=".pdf",
    )
    assert result.startswith("undated - Sparkasse")


def test_no_sender_skips_sender():
    result = sanitize_filename(
        date="2024-01-01",
        sender=None,
        document_type="Invoice",
        original_stem="inv",
        extension=".pdf",
    )
    assert "None" not in result
    assert "2024-01-01" in result
    assert "Invoice" in result


def test_forbidden_chars_removed():
    result = sanitize_filename(
        date="2024-01-01",
        sender="Bad:Name/Company",
        document_type="Doc*Type",
        original_stem="x",
        extension=".pdf",
    )
    for ch in r':/"*?<>|\\':
        assert ch not in result


def test_max_length():
    long_sender = "A" * 200
    result = sanitize_filename(
        date="2024-01-01",
        sender=long_sender,
        document_type="Type",
        original_stem="x",
        extension=".pdf",
    )
    assert len(result) <= 200


def test_whitespace_normalized():
    result = sanitize_filename(
        date="2024-01-01",
        sender="  Allianz  ",
        document_type="  Invoice  ",
        original_stem="x",
        extension=".pdf",
    )
    assert "  " not in result


def test_safe_target_path_inside_root(tmp_path):
    target = safe_target_path(tmp_path, "Finance", "Banking", "2024-01-01 - Bank - Statement.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Finance" in str(target)
    assert "Banking" in str(target)


def test_safe_target_path_no_subcategory(tmp_path):
    target = safe_target_path(tmp_path, "Review", None, "unknown.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Review" in str(target)


def test_safe_target_path_blocks_traversal(tmp_path):
    with pytest.raises(ValueError, match="Path traversal"):
        safe_target_path(tmp_path, "../evil", None, "bad.pdf")


def test_max_length_with_long_extension():
    long_sender = "A" * 200
    result = sanitize_filename(
        date="2024-01-01",
        sender=long_sender,
        document_type="Type",
        original_stem="x",
        extension=".docx",
    )
    assert len(result) <= 200
