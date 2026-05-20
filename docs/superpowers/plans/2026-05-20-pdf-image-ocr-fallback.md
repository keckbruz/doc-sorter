# PDF Image OCR Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make doc-sorter extract text from scanned/image-based PDFs via OCR fallback, add HEIC image support, and fix a bug where the `suggest-taxonomy` command ignores `--ocr`.

**Architecture:** A new `pdf_ocr.py` extractor (mirrors existing `image_ocr.py` pattern) renders PDF pages to PIL images via pymupdf, then runs pytesseract. The router in `__init__.py` calls it automatically when pypdf returns sparse text (< 50 non-whitespace chars/page). HEIC support is added to `image_ocr.py` via soft-dep `pillow-heif`. All new deps go into the existing `[ocr]` optional extra.

**Tech Stack:** Python 3.11+, pypdf, pymupdf (fitz), pytesseract, pillow, pillow-heif, pytest, fpdf2 (tests)

---

## File Map

| Action | File | What changes |
|---|---|---|
| Modify | `pyproject.toml` | Add `pymupdf>=1.23`, `pillow-heif>=0.13` to `[ocr]` extra |
| Modify | `doc_cleaner/extractors/pdf.py` | Return 3-tuple `(text, error, page_count)` |
| Modify | `doc_cleaner/extractors/image_ocr.py` | Add HEIC support via pillow-heif |
| Modify | `doc_cleaner/extractors/__init__.py` | Unpack 3-tuple, add HEIC extensions, add PDF OCR fallback routing |
| Create | `doc_cleaner/extractors/pdf_ocr.py` | New extractor: pymupdf → PIL → pytesseract |
| Modify | `doc_cleaner/cli.py` | Add `--ocr`/`--ocr-language` to `suggest-taxonomy`, fix line 522 |
| Modify | `tests/test_extractors.py` | Tests for pdf 3-tuple, HEIC, pdf_ocr fallback |
| Modify | `tests/test_cli_suggest_taxonomy.py` | Test `--ocr` flag forwarding |

---

## Task 1: Add new dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update the `[ocr]` optional extra**

Open `pyproject.toml` and replace:
```toml
[project.optional-dependencies]
ocr = ["pytesseract"]
```
with:
```toml
[project.optional-dependencies]
ocr = ["pytesseract", "pymupdf>=1.23", "pillow-heif>=0.13"]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pymupdf and pillow-heif to [ocr] optional deps"
```

---

## Task 2: Update `extract_pdf_text` to return page count

`__init__.py` currently unpacks `text, err = extract_pdf_text(...)`. We extend the return to a 3-tuple and fix the unpacking atomically.

**Files:**
- Modify: `doc_cleaner/extractors/pdf.py`
- Modify: `doc_cleaner/extractors/__init__.py:32-35`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py::test_extract_pdf_text_returns_page_count -v
```
Expected: `FAILED` — `cannot unpack non-iterable` or `too many values to unpack` depending on Python's error.

- [ ] **Step 3: Update `pdf.py` to return 3-tuple**

Replace the entire contents of `doc_cleaner/extractors/pdf.py` with:
```python
from __future__ import annotations
from pathlib import Path


def extract_pdf_text(path: Path, max_chars: int = 0) -> tuple[str, str | None, int]:
    """Returns (text, error_or_none, page_count)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            parts.append(page_text)
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None, page_count
    except ImportError:
        return "", "pypdf not installed", 0
    except Exception as e:
        return "", str(e), 0
```

- [ ] **Step 4: Fix the unpacking in `__init__.py`**

In `doc_cleaner/extractors/__init__.py`, replace:
```python
    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err = extract_pdf_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="pdf", error=err)
```
with:
```python
    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err, page_count = extract_pdf_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="pdf", error=err)
```
(The `page_count` variable is unused for now — it will be used in Task 5.)

- [ ] **Step 5: Run all tests to verify nothing is broken**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py -v
```
Expected: all tests pass including the new one.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/extractors/pdf.py doc_cleaner/extractors/__init__.py tests/test_extractors.py
git commit -m "feat: extract_pdf_text returns page_count as 3-tuple"
```

---

## Task 3: Add HEIC support to image_ocr.py and IMAGE_EXTENSIONS

**Files:**
- Modify: `doc_cleaner/extractors/image_ocr.py`
- Modify: `doc_cleaner/extractors/__init__.py:9`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_extractors.py`:
```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py::test_heic_ocr_returns_heic_unavailable_when_pillow_heif_missing tests/test_extractors.py::test_heic_extension_in_image_extensions -v
```
Expected: both `FAILED`.

- [ ] **Step 3: Update `image_ocr.py`**

Replace the entire contents of `doc_cleaner/extractors/image_ocr.py` with:
```python
from __future__ import annotations
from pathlib import Path

_HEIC_EXTENSIONS = {".heic", ".heif"}


def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
    """OCR via pytesseract. Soft dependency — returns graceful error if not installed."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "ocr_unavailable"

    if path.suffix.lower() in _HEIC_EXTENSIONS:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            return "", "heic_unavailable"

    try:
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img, lang=language)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 4: Add `.heic` and `.heif` to `IMAGE_EXTENSIONS` in `__init__.py`**

In `doc_cleaner/extractors/__init__.py`, replace:
```python
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
```
with:
```python
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".heic", ".heif"}
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/extractors/image_ocr.py doc_cleaner/extractors/__init__.py tests/test_extractors.py
git commit -m "feat: add HEIC/HEIF support to image OCR extractor"
```

---

## Task 4: Create `pdf_ocr.py` extractor

**Files:**
- Create: `doc_cleaner/extractors/pdf_ocr.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_extractors.py`:
```python
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

    fake_doc = [fake_page]

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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py::test_extract_pdf_ocr_text_returns_text tests/test_extractors.py::test_extract_pdf_ocr_text_returns_pymupdf_unavailable tests/test_extractors.py::test_extract_pdf_ocr_text_returns_ocr_unavailable_when_no_tesseract -v
```
Expected: all `FAILED` with `ModuleNotFoundError` or import errors.

- [ ] **Step 3: Create `doc_cleaner/extractors/pdf_ocr.py`**

```python
from __future__ import annotations
from pathlib import Path


def extract_pdf_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
    """OCR fallback for image-based PDFs. Soft dependencies: pymupdf (fitz), pytesseract."""
    try:
        import fitz
    except ImportError:
        return "", "pymupdf_unavailable"
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "ocr_unavailable"
    try:
        doc = fitz.open(str(path))
        parts: list[str] = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            parts.append(pytesseract.image_to_string(img, lang=language))
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/extractors/pdf_ocr.py tests/test_extractors.py
git commit -m "feat: add pdf_ocr extractor for image-based PDFs via pymupdf+pytesseract"
```

---

## Task 5: Wire PDF OCR fallback into the extractor router

**Files:**
- Modify: `doc_cleaner/extractors/__init__.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_extractors.py`:
```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_extractors.py::test_sparse_pdf_triggers_ocr_fallback tests/test_extractors.py::test_dense_pdf_skips_ocr_fallback -v
```
Expected: both `FAILED` — fallback never called / always falls through to `"pdf"`.

- [ ] **Step 3: Update the PDF routing block in `__init__.py`**

Replace:
```python
    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err, page_count = extract_pdf_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="pdf", error=err)
```
with:
```python
    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err, page_count = extract_pdf_text(meta.original_path, max_chars)
        if not err:
            non_ws = len("".join(text.split()))
            if non_ws < 50 * max(1, page_count):
                from doc_cleaner.extractors.pdf_ocr import extract_pdf_ocr_text
                ocr_text, ocr_err = extract_pdf_ocr_text(
                    meta.original_path, ocr_language, max_chars
                )
                if ocr_text:
                    return ExtractionResult(text=ocr_text, extractor="pdf_ocr", error=ocr_err)
        return ExtractionResult(text=text, extractor="pdf", error=err)
```

- [ ] **Step 4: Run all tests**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/extractors/__init__.py tests/test_extractors.py
git commit -m "feat: auto OCR fallback for image-based PDFs when text is sparse"
```

---

## Task 6: Fix `suggest-taxonomy` hardcoded `ocr=False` bug

**Files:**
- Modify: `doc_cleaner/cli.py`
- Test: `tests/test_cli_suggest_taxonomy.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli_suggest_taxonomy.py`:
```python
def test_suggest_taxonomy_passes_ocr_flag_to_extract_text(tmp_path, mocker):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "scan.jpg").write_bytes(b"\xff\xd8fake jpeg")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    captured_calls = []

    def fake_extract_text(meta, max_chars=0, ocr=False, ocr_language="deu+eng"):
        captured_calls.append({"ocr": ocr, "ocr_language": ocr_language})
        from doc_cleaner.extractors import ExtractionResult
        return ExtractionResult(text="", extractor="none")

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.cli.extract_text", side_effect=fake_extract_text), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_cls:
        mock_cls.return_value.suggest_taxonomy.return_value = {}
        runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
            "--ocr",
            "--ocr-language", "eng",
        ])

    assert len(captured_calls) == 1
    assert captured_calls[0]["ocr"] is True
    assert captured_calls[0]["ocr_language"] == "eng"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/test_cli_suggest_taxonomy.py::test_suggest_taxonomy_passes_ocr_flag_to_extract_text -v
```
Expected: `FAILED` — `--ocr` is not a recognised option (or ocr is always False).

- [ ] **Step 3: Add `--ocr` and `--ocr-language` to `suggest_taxonomy_cmd`**

In `doc_cleaner/cli.py`, find the `suggest_taxonomy_cmd` function signature (around line 485) and add two parameters after `output_format`:

```python
@app.command("suggest-taxonomy")
def suggest_taxonomy_cmd(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Output folder (used as existing taxonomy context)"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    max_text_chars: int = typer.Option(300, "--max-text-chars"),
    output_format: str = typer.Option("text", "--output-format", help="Output format: text or jsonl"),
    ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
    ocr_language: str = typer.Option("deu+eng", "--ocr-language"),
) -> None:
```

- [ ] **Step 4: Fix line 522 to pass `ocr` and `ocr_language`**

Replace:
```python
            result = extract_text(meta, max_chars=max_text_chars, ocr=False)
```
with:
```python
            result = extract_text(meta, max_chars=max_text_chars, ocr=ocr, ocr_language=ocr_language)
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/cli.py tests/test_cli_suggest_taxonomy.py
git commit -m "fix: suggest-taxonomy command now respects --ocr and --ocr-language flags"
```

---

## Final verification

- [ ] **Run the full test suite one last time**

```bash
cd /Users/nicolairainprechter/Dev/doc-sorter && python -m pytest tests/ -v
```
Expected: all tests pass, zero failures.
