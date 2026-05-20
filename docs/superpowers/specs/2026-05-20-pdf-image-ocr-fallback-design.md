# PDF Image OCR Fallback — Design Spec

**Date:** 2026-05-20

## Problem

`pypdf` extracts embedded text from PDFs. Scanned or photographed PDFs have no text layer, so `pypdf` returns an empty string and the classifier has nothing to work with. Additionally, HEIC images (common on Apple devices) are not in the recognised image set, so they are silently skipped even with `--ocr`.

A secondary bug: the `suggest_taxonomy` CLI command hardcodes `ocr=False`, making image OCR dead in that code path regardless of user intent.

---

## Design

### 1. New module: `doc_cleaner/extractors/pdf_ocr.py`

A new extractor following the same soft-dependency pattern as `image_ocr.py`.

```
extract_pdf_ocr_text(path, language, max_chars) -> tuple[str, str | None]
```

- Opens the PDF with `pymupdf` (fitz), renders each page to a PIL `Image` at 150 DPI.
- Runs `pytesseract.image_to_string` on each page image.
- Returns joined text and `None` on success, or `("", "<error_code>")` on failure.
- Error codes: `"pymupdf_unavailable"`, `"ocr_unavailable"`, or the exception message.
- Both `pymupdf` and `pytesseract` are imported inside the function — `ImportError` is caught and returned gracefully.

### 2. Routing change: `doc_cleaner/extractors/__init__.py`

**Sparseness check:** `extract_pdf_text` is updated to return a 3-tuple `(text, error, page_count)` so the router has page count without re-opening the file. Then:

```python
non_ws = len("".join(text.split()))
sparse = non_ws < 50 * max(1, page_count)
```

If sparse, call `extract_pdf_ocr_text` and return `ExtractionResult(extractor="pdf_ocr")`.

**HEIC support:** add `.heic` and `.heif` to `IMAGE_EXTENSIONS`. These are routed to `image_ocr.py` when `ocr=True`.

**Trigger:** the PDF OCR fallback runs automatically (no `--ocr` flag required) — consistent with user expectation that a PDF is always readable if possible. Image OCR (including HEIC) continues to require `--ocr`.

### 3. HEIC support in `doc_cleaner/extractors/image_ocr.py`

Before `Image.open()`, attempt:

```python
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    if path.suffix.lower() in {".heic", ".heif"}:
        return "", "heic_unavailable"
```

This is a no-op for non-HEIC files when `pillow-heif` is not installed.

### 4. Dependency changes: `pyproject.toml`

Extend the `[ocr]` optional extra:

```toml
[project.optional-dependencies]
ocr = ["pytesseract", "pymupdf>=1.23", "pillow-heif>=0.13"]
```

### 5. Bug fix: `doc_cleaner/cli.py` line 522

The `suggest_taxonomy` command hardcodes `ocr=False`. Fix:

- Add `ocr: bool = typer.Option(False, "--ocr/--no-ocr")` and `ocr_language: str = typer.Option("deu+eng", "--ocr-language")` parameters to the command.
- Pass `ocr=ocr, ocr_language=ocr_language` to `extract_text()` at line 522.

---

## Extractor labels

| Scenario | `extractor` value |
|---|---|
| pypdf found text | `"pdf"` |
| pypdf empty → OCR succeeded | `"pdf_ocr"` |
| pypdf empty → pymupdf missing | `"pdf"` (empty text, error set) |
| pypdf empty → pytesseract missing | `"pdf"` (empty text, error set) |
| image file + OCR | `"image_ocr"` |
| HEIC + OCR + pillow-heif missing | `"image_ocr"` with error `"heic_unavailable"` |

---

## Error handling

All soft dependencies follow the existing pattern: `ImportError` is caught inside the extractor function and returned as a string error code. Callers already handle `result.error != None` gracefully — no changes needed upstream.

---

## Tests

All tests use mocks — no real OCR libraries required in the dev environment.

| Test | File | What it checks |
|---|---|---|
| Sparse PDF triggers OCR fallback | `test_extractors.py` | `extract_text` calls `extract_pdf_ocr_text` when page text is below threshold |
| Dense PDF skips OCR fallback | `test_extractors.py` | `extract_pdf_ocr_text` not called when pypdf returns real text |
| PDF OCR missing pymupdf | `test_extractors.py` | Returns empty text with `"pymupdf_unavailable"` error |
| HEIC OCR with pillow-heif | `test_extractors.py` | Image opened and OCR'd successfully |
| HEIC OCR missing pillow-heif | `test_extractors.py` | Returns `"heic_unavailable"` error |
| suggest_taxonomy passes ocr flag | `test_cli_suggest_taxonomy.py` | `--ocr` flag is forwarded to `extract_text` |

---

## Out of scope

- **Swift app:** does not expose `--ocr` to the user. Wiring the OCR flag through the SwiftUI layer is a follow-up task.
- **PDF DPI tuning:** 150 DPI is a reasonable default. Configurable DPI is not included.
- **Mixed PDFs:** PDFs with some text pages and some image pages are handled page-by-page inside `pdf_ocr.py` naturally, but the sparseness check is document-level. Edge case accepted.
