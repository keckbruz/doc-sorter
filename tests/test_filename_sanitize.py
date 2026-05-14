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
    assert result == "2024-03_beitragsrechnung_allianz.pdf"


def test_year_month_only():
    result = sanitize_filename(
        date="2024-03-12",
        sender="Allianz",
        document_type="Rechnung",
        original_stem="x",
        extension=".pdf",
    )
    assert result.startswith("2024-03_")
    assert "12" not in result


def test_no_date_omits_date():
    result = sanitize_filename(
        date=None,
        sender="Sparkasse",
        document_type="Kontoauszug",
        original_stem="stmt",
        extension=".pdf",
    )
    assert "undated" not in result
    assert result == "kontoauszug_sparkasse.pdf"


def test_no_sender_skips_sender():
    result = sanitize_filename(
        date="2024-01-01",
        sender=None,
        document_type="Invoice",
        original_stem="inv",
        extension=".pdf",
    )
    assert "none" not in result.lower()
    assert result == "2024-01_invoice.pdf"


def test_no_date_no_sender():
    result = sanitize_filename(
        date=None,
        sender=None,
        document_type="Vertrag",
        original_stem="doc",
        extension=".pdf",
    )
    assert result == "vertrag.pdf"


def test_no_date_no_sender_no_type_uses_stem():
    result = sanitize_filename(
        date=None,
        sender=None,
        document_type=None,
        original_stem="my file",
        extension=".pdf",
    )
    assert result == "my-file.pdf"


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


def test_spaces_become_hyphens():
    result = sanitize_filename(
        date="2024-01-01",
        sender="Finanzamt München",
        document_type="Einkommensteuerbescheid",
        original_stem="x",
        extension=".txt",
    )
    assert " " not in result
    assert "finanzamt-m" in result


def test_lowercase():
    result = sanitize_filename(
        date="2024-01-01",
        sender="VODAFONE GMBH",
        document_type="RECHNUNG",
        original_stem="x",
        extension=".pdf",
    )
    assert result == result.lower()


def test_sender_truncated():
    long_sender = "Sehr Langer Firmenname GmbH Co KG"
    result = sanitize_filename(
        date="2024-01-01",
        sender=long_sender,
        document_type="Rechnung",
        original_stem="x",
        extension=".pdf",
    )
    parts = result.split("_")
    sender_part = parts[-1].replace(".pdf", "")
    assert len(sender_part) <= 25


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


def test_safe_target_path_inside_root(tmp_path):
    target = safe_target_path(tmp_path, "Finanzen", "Bankwesen", "2024-03_kontoauszug_sparkasse.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Finanzen" in str(target)
    assert "Bankwesen" in str(target)


def test_safe_target_path_no_subcategory(tmp_path):
    target = safe_target_path(tmp_path, "Review", None, "unknown.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Review" in str(target)


def test_safe_target_path_blocks_traversal(tmp_path):
    with pytest.raises(ValueError, match="Path traversal"):
        safe_target_path(tmp_path, "../evil", None, "bad.pdf")
