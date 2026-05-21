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


def test_extract_pdf_ocr_text_returns_text(tmp_path, mocker):
    import sys
    from PIL import Image as PILImage

    # Build a fake fitz page that returns a tiny pixmap
    fake_pix = mocker.MagicMock()
    fake_pix.width = 10
    fake_pix.height = 10
    fake_pix.samples = b'\xff' * (10 * 10 * 3)

    fake_page = mocker.MagicMock()
    fake_page.get_pixmap.return_value = fake_pix

    fake_doc = mocker.MagicMock()
    fake_doc.__enter__ = mocker.MagicMock(return_value=[fake_page])
    fake_doc.__exit__ = mocker.MagicMock(return_value=False)

    fake_fitz = mocker.MagicMock()
    fake_fitz.open.return_value = fake_doc
    fake_tesseract = mocker.MagicMock()
    fake_tesseract.image_to_string.return_value = "Scanned text here"
    mocker.patch.dict(sys.modules, {"fitz": fake_fitz, "pytesseract": fake_tesseract})

    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF fake")

    from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
    text, err = extract_pdf_ocr_text(p, language="deu+eng")
    assert err is None
    assert "Scanned text here" in text


def test_extract_pdf_ocr_text_returns_pymupdf_unavailable(tmp_path, mocker):
    import sys
    mocker.patch.dict(sys.modules, {"fitz": None})
    from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF fake")
    text, err = extract_pdf_ocr_text(p)
    assert text == ""
    assert err == "pymupdf_unavailable"


def test_extract_pdf_ocr_text_returns_ocr_unavailable_when_no_tesseract(tmp_path, mocker):
    import sys
    mocker.patch.dict(sys.modules, {"fitz": mocker.MagicMock(), "pytesseract": None})
    from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF fake")
    text, err = extract_pdf_ocr_text(p)
    assert text == ""
    assert err == "ocr_unavailable"


def test_extract_pdf_ocr_text_respects_max_chars(tmp_path, mocker):
    import sys

    fake_pix = mocker.MagicMock()
    fake_pix.width = 10
    fake_pix.height = 10
    fake_pix.samples = b'\xff' * (10 * 10 * 3)
    fake_page = mocker.MagicMock()
    fake_page.get_pixmap.return_value = fake_pix

    fake_doc = mocker.MagicMock()
    fake_doc.__enter__ = mocker.MagicMock(return_value=[fake_page])
    fake_doc.__exit__ = mocker.MagicMock(return_value=False)

    fake_fitz = mocker.MagicMock()
    fake_fitz.open.return_value = fake_doc
    fake_tesseract = mocker.MagicMock()
    fake_tesseract.image_to_string.return_value = "A" * 200
    mocker.patch.dict(sys.modules, {"fitz": fake_fitz, "pytesseract": fake_tesseract})

    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF fake")

    from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
    text, err = extract_pdf_ocr_text(p, max_chars=50)
    assert err is None
    assert len(text) == 50


def test_sparse_pdf_triggers_ocr_fallback(tmp_path, mocker):
    """A PDF where pypdf returns < 50 non-ws chars/page should trigger pdf_ocr fallback."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()  # 1 page, no text → sparse
    p = tmp_path / "sparse.pdf"
    pdf.output(str(p))

    mock_ocr = mocker.patch(
        "doc_cleaner.extractors.pdf_ocr.extract_pdf_ocr_text",
        return_value=("OCR extracted text", None),
    )

    from doc_cleaner.scanner import FileMetadata
    meta = FileMetadata(
        original_path=p, relative_path=Path(p.name), filename=p.name,
        extension=".pdf", file_size=p.stat().st_size, created_time=None,
        modified_time=p.stat().st_mtime, mime_type="application/pdf", file_hash="x",
    )
    from doc_cleaner.extractors import extract_text
    result = extract_text(meta)
    assert result.extractor == "pdf_ocr"
    assert result.text == "OCR extracted text"
    mock_ocr.assert_called_once()


def test_dense_pdf_skips_ocr_fallback(tmp_path, mocker):
    """A PDF with >= 50 non-ws chars/page must NOT trigger the OCR fallback."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "This is a fully text-based PDF with plenty of words in it, more than fifty characters.")
    p = tmp_path / "dense.pdf"
    pdf.output(str(p))

    mock_ocr = mocker.patch("doc_cleaner.extractors.pdf_ocr.extract_pdf_ocr_text")

    from doc_cleaner.scanner import FileMetadata
    meta = FileMetadata(
        original_path=p, relative_path=Path(p.name), filename=p.name,
        extension=".pdf", file_size=p.stat().st_size, created_time=None,
        modified_time=p.stat().st_mtime, mime_type="application/pdf", file_hash="x",
    )
    from doc_cleaner.extractors import extract_text
    result = extract_text(meta)
    assert result.extractor == "pdf"
    mock_ocr.assert_not_called()


# ── _rotation.py helper ────────────────────────────────────────────────────

def test_rotation_retry_returns_early_when_text_above_threshold(mocker):
    from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
    fake_pt = mocker.MagicMock()
    fake_pt.image_to_string.return_value = "A" * 25  # 25 non-ws >= threshold of 20
    img = mocker.MagicMock()

    result = ocr_with_rotation_retry(img, fake_pt, "deu+eng", sparse_threshold=20)

    assert result == "A" * 25
    fake_pt.image_to_osd.assert_not_called()


def test_rotation_retry_rotates_and_returns_better_text(mocker):
    from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
    fake_pt = mocker.MagicMock()
    fake_pt.image_to_string.side_effect = ["ab", "Much better text after rotation"]
    fake_pt.image_to_osd.return_value = {"rotate": 90}
    img = mocker.MagicMock()
    rotated = mocker.MagicMock()
    img.rotate.return_value = rotated

    result = ocr_with_rotation_retry(img, fake_pt, "deu+eng", sparse_threshold=20)

    img.rotate.assert_called_once_with(-90, expand=True)
    assert result == "Much better text after rotation"


def test_rotation_retry_returns_original_when_osd_raises(mocker):
    from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
    fake_pt = mocker.MagicMock()
    fake_pt.image_to_string.return_value = "ab"
    fake_pt.image_to_osd.side_effect = Exception("OSD failed")
    img = mocker.MagicMock()

    result = ocr_with_rotation_retry(img, fake_pt, "deu+eng", sparse_threshold=20)

    assert result == "ab"
    img.rotate.assert_not_called()


def test_rotation_retry_skips_rotate_when_angle_is_zero(mocker):
    from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
    fake_pt = mocker.MagicMock()
    fake_pt.image_to_string.return_value = "ab"
    fake_pt.image_to_osd.return_value = {"rotate": 0}
    img = mocker.MagicMock()

    result = ocr_with_rotation_retry(img, fake_pt, "deu+eng", sparse_threshold=20)

    assert result == "ab"
    img.rotate.assert_not_called()


def test_rotation_retry_keeps_original_when_retry_is_worse(mocker):
    from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
    fake_pt = mocker.MagicMock()
    # original: 4 non-ws chars (sparse), retry: 1 non-ws char (worse)
    fake_pt.image_to_string.side_effect = ["ab cd", "x"]
    fake_pt.image_to_osd.return_value = {"rotate": 90}
    img = mocker.MagicMock()
    img.rotate.return_value = mocker.MagicMock()

    result = ocr_with_rotation_retry(img, fake_pt, "deu+eng", sparse_threshold=20)

    assert result == "ab cd"


def test_image_ocr_applies_exif_transpose(tmp_path, mocker):
    import sys
    from PIL import Image as RealImage

    img_path = tmp_path / "photo.png"
    RealImage.new("RGB", (1, 1)).save(str(img_path))

    fake_pytesseract = mocker.MagicMock()
    # Return enough text to skip OSD retry (>= 20 non-ws chars)
    fake_pytesseract.image_to_string.return_value = "Enough text to skip OSD retry here"
    mocker.patch.dict(sys.modules, {"pytesseract": fake_pytesseract})

    exif_spy = mocker.patch("PIL.ImageOps.exif_transpose", wraps=lambda img: img)

    from doc_cleaner.extractors.image_ocr import extract_ocr_text
    extract_ocr_text(img_path)

    exif_spy.assert_called_once()


def test_extract_pdf_ocr_sparse_page_triggers_osd_retry(tmp_path, mocker):
    import sys

    fake_pix = mocker.MagicMock()
    fake_pix.width = 10
    fake_pix.height = 10
    fake_pix.samples = b'\xff' * (10 * 10 * 3)
    fake_page = mocker.MagicMock()
    fake_page.get_pixmap.return_value = fake_pix

    fake_doc = mocker.MagicMock()
    fake_doc.__enter__ = mocker.MagicMock(return_value=[fake_page])
    fake_doc.__exit__ = mocker.MagicMock(return_value=False)

    fake_fitz = mocker.MagicMock()
    fake_fitz.open.return_value = fake_doc

    fake_tesseract = mocker.MagicMock()
    # First image_to_string call returns sparse text; retry returns real text
    fake_tesseract.image_to_string.side_effect = ["ab", "Real text found after rotation"]
    fake_tesseract.image_to_osd.return_value = {"rotate": 90}

    mocker.patch.dict(sys.modules, {"fitz": fake_fitz, "pytesseract": fake_tesseract})

    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF fake")

    from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
    text, err = extract_pdf_ocr_text(p, language="deu+eng")

    assert err is None
    assert "Real text found after rotation" in text
    fake_tesseract.image_to_osd.assert_called_once()
