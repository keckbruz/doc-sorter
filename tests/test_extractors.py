from pathlib import Path
import pytest
from doc_cleaner.scanner import FileMetadata
from doc_cleaner.extractors import extract_text, ExtractionResult


def _make_meta(path: Path, ext: str, mime: str) -> FileMetadata:
    return FileMetadata(
        original_path=path,
        relative_path=Path(path.name),
        filename=path.name,
        extension=ext,
        file_size=path.stat().st_size,
        created_time=None,
        modified_time=path.stat().st_mtime,
        mime_type=mime,
        file_hash="abc123",
    )


def test_extract_plain_text(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Hello world from a text file.")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert isinstance(result, ExtractionResult)
    assert "Hello world" in result.text
    assert result.extractor == "text"
    assert result.error is None


def test_extract_markdown(tmp_path):
    p = tmp_path / "readme.md"
    p.write_text("# Title\n\nSome content here.")
    meta = _make_meta(p, ".md", "text/markdown")
    result = extract_text(meta)
    assert "Title" in result.text
    assert result.extractor == "text"


def test_extract_unsupported_returns_empty(tmp_path):
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x00\x01\x02")
    meta = _make_meta(p, ".bin", "application/octet-stream")
    result = extract_text(meta)
    assert result.text == ""
    assert result.extractor == "none"


def test_extract_empty_file_returns_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert result.text == ""
    assert result.error is None


def test_extraction_result_dataclass():
    r = ExtractionResult(text="hello", extractor="text")
    assert r.error is None


def test_extract_pdf_text_returns_page_count(tmp_path):
    from fpdf import FPDF
    from doc_cleaner.extractors.pdf import extract_pdf_text
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Hello PDF page one")
    pdf.add_page()
    pdf.cell(0, 10, "Hello PDF page two")
    p = tmp_path / "two_page.pdf"
    pdf.output(str(p))

    text, err, page_count = extract_pdf_text(p)
    assert err is None
    assert page_count == 2
    assert "Hello PDF" in text


def test_heic_ocr_returns_heic_unavailable_when_pillow_heif_missing(tmp_path, mocker):
    import sys
    # pillow_heif absent; pytesseract mocked so we reach the HEIC check
    mocker.patch.dict(sys.modules, {
        "pytesseract": mocker.MagicMock(),
        "pillow_heif": None,
    })
    p = tmp_path / "card.heic"
    p.write_bytes(b"\x00fake heic bytes")
    from doc_cleaner.extractors.image_ocr import extract_ocr_text
    text, err = extract_ocr_text(p)
    assert text == ""
    assert err == "heic_unavailable"


def test_heic_extension_in_image_extensions():
    from doc_cleaner.extractors import IMAGE_EXTENSIONS
    assert ".heic" in IMAGE_EXTENSIONS
    assert ".heif" in IMAGE_EXTENSIONS
