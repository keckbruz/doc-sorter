# EXIF Auto-Rotate, Adaptive OSD Retry & Swift Always-On OCR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix OCR failures on rotated images and image-based PDFs, and wire OCR always-on into the Swift app.

**Architecture:** A new shared `_rotation.py` helper encapsulates the adaptive OSD retry logic. Both `image_ocr.py` (standalone images) and `pdf_ocr.py` (PDF pages) call it after their primary OCR pass. If the result is sparse, the helper runs Tesseract OSD to detect rotation, rotates the image, and re-runs OCR — returning whichever pass gave more text. The Swift bridge is updated to always pass `--ocr` without any UI toggle.

**Tech Stack:** Python — `pytesseract` (`image_to_string`, `image_to_osd`), `Pillow` (`ImageOps.exif_transpose`, `Image.rotate`), `pymupdf` (fitz). Swift — `Process.arguments`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `doc_cleaner/extractors/_rotation.py` | Create | Shared `ocr_with_rotation_retry` helper |
| `doc_cleaner/extractors/image_ocr.py` | Modify | Add EXIF transpose; delegate OCR to helper |
| `doc_cleaner/extractors/pdf_ocr.py` | Modify | Delegate per-page OCR to helper |
| `tests/test_extractors.py` | Modify | Tests for helper, EXIF transpose, per-page OSD |
| `DocSorter/DocSorter/Bridge/PythonBridge.swift` | Modify | Add `--ocr --ocr-language deu+eng` to scan + suggestTaxonomy |

---

### Task 1: Create `_rotation.py` — OSD retry helper

**Files:**
- Create: `doc_cleaner/extractors/_rotation.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_extractors.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_extractors.py -k "rotation_retry" -v
```

Expected: 5 failures — `ModuleNotFoundError: No module named 'doc_cleaner.extractors._rotation'`

- [ ] **Step 3: Create `doc_cleaner/extractors/_rotation.py`**

```python
from __future__ import annotations
from typing import Any


def ocr_with_rotation_retry(
    img: Any,
    pytesseract: Any,
    language: str,
    sparse_threshold: int,
) -> str:
    """Run OCR; if result is sparse, use OSD to detect rotation, rotate, and retry.

    Returns whichever pass produced more non-whitespace text.
    Falls back to the first-pass result if OSD raises or returns 0°.
    """
    text = pytesseract.image_to_string(img, lang=language)
    non_ws = len("".join(text.split()))
    if non_ws >= sparse_threshold:
        return text
    try:
        osd = pytesseract.image_to_osd(
            img, lang=language, output_type=pytesseract.Output.DICT
        )
        angle = osd.get("rotate", 0)
    except Exception:
        return text
    if angle == 0:
        return text
    rotated = img.rotate(-angle, expand=True)
    retry = pytesseract.image_to_string(rotated, lang=language)
    return retry if len("".join(retry.split())) > non_ws else text
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_extractors.py -k "rotation_retry" -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/extractors/_rotation.py tests/test_extractors.py
git commit -m "feat: adaptive OSD rotation-retry helper"
```

---

### Task 2: Update `image_ocr.py` — EXIF transpose + OSD retry

**Files:**
- Modify: `doc_cleaner/extractors/image_ocr.py`
- Test: `tests/test_extractors.py`

Current `image_ocr.py` (for reference):
```python
from __future__ import annotations
from pathlib import Path

_HEIC_EXTENSIONS = {".heic", ".heif"}

def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
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
        if img.format == "HEIF":
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang=language)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_extractors.py::test_image_ocr_applies_exif_transpose -v
```

Expected: FAIL — `AssertionError: Expected 'exif_transpose' to have been called once`

- [ ] **Step 3: Update `image_ocr.py`**

Replace the entire file with:

```python
from __future__ import annotations
from pathlib import Path

_HEIC_EXTENSIONS = {".heic", ".heif"}


def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
    """OCR via pytesseract. Soft dependency — returns graceful error if not installed."""
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError:
        return "", "ocr_unavailable"

    if path.suffix.lower() in _HEIC_EXTENSIONS:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            return "", "heic_unavailable"

    try:
        from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
        img = Image.open(str(path))
        img = ImageOps.exif_transpose(img)
        if img.format == "HEIF":
            img = img.convert("RGB")
        text = ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=20)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 4: Run the full extractor test suite**

```
pytest tests/test_extractors.py -v
```

Expected: all tests PASSED (including the existing HEIC and image tests)

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/extractors/image_ocr.py tests/test_extractors.py
git commit -m "feat: EXIF transpose and adaptive OSD retry for image OCR"
```

---

### Task 3: Update `pdf_ocr.py` — OSD retry per page

**Files:**
- Modify: `doc_cleaner/extractors/pdf_ocr.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_extractors.py::test_extract_pdf_ocr_sparse_page_triggers_osd_retry -v
```

Expected: FAIL — `AssertionError: assert 'ab' contains 'Real text found after rotation'`

- [ ] **Step 3: Update `pdf_ocr.py`**

Replace the entire file with:

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
        from doc_cleaner.extractors._rotation import ocr_with_rotation_retry
        with fitz.open(str(path)) as doc:
            parts: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                parts.append(
                    ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=50)
                )
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 4: Run the full extractor test suite**

```
pytest tests/test_extractors.py -v
```

Expected: all tests PASSED (existing pdf_ocr tests must still pass)

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/extractors/pdf_ocr.py tests/test_extractors.py
git commit -m "feat: adaptive OSD rotation retry per page in PDF OCR"
```

---

### Task 4: Wire always-on OCR into `PythonBridge.swift`

**Files:**
- Modify: `DocSorter/DocSorter/Bridge/PythonBridge.swift:74-81` (suggestTaxonomy arguments)
- Modify: `DocSorter/DocSorter/Bridge/PythonBridge.swift:136-146` (scan arguments)

No tests — verified by code review.

- [ ] **Step 1: Update `suggestTaxonomy` process.arguments (line 74)**

Current (lines 74–81):
```swift
process.arguments = [
    "-u", "-m", "doc_cleaner",
    "suggest-taxonomy",
    "--input", inputPath,
    "--output-root", outputPath,
    "--model", model,
    "--output-format", "jsonl",
]
```

Replace with:
```swift
process.arguments = [
    "-u", "-m", "doc_cleaner",
    "suggest-taxonomy",
    "--input", inputPath,
    "--output-root", outputPath,
    "--model", model,
    "--output-format", "jsonl",
    "--ocr",
    "--ocr-language", "deu+eng",
]
```

- [ ] **Step 2: Update `scan` process.arguments (line 136)**

Current (lines 136–146):
```swift
process.arguments = [
    "-u", "-m", "doc_cleaner", "scan",
    "--input", inputPath,
    "--output-root", outputPath,
    "--plan", planPath,
    "--jsonl", jsonlPath,
    "--model", model,
    "--confidence-threshold", String(confidenceThreshold),
    "--ollama-host", ollamaHost,
    "--output-format", "jsonl",
]
```

Replace with:
```swift
process.arguments = [
    "-u", "-m", "doc_cleaner", "scan",
    "--input", inputPath,
    "--output-root", outputPath,
    "--plan", planPath,
    "--jsonl", jsonlPath,
    "--model", model,
    "--confidence-threshold", String(confidenceThreshold),
    "--ollama-host", ollamaHost,
    "--output-format", "jsonl",
    "--ocr",
    "--ocr-language", "deu+eng",
]
```

- [ ] **Step 3: Verify `apply` and `undo` are unchanged**

Confirm that `process.arguments` at line 219 (`apply`) and line 259 (`undo`) do NOT contain `--ocr`. These commands work on the already-produced plan file and don't need OCR.

- [ ] **Step 4: Commit**

```bash
git add DocSorter/DocSorter/Bridge/PythonBridge.swift
git commit -m "feat: always pass --ocr to scan and suggest-taxonomy in Swift bridge"
```

---

### Task 5: Full regression run

**Files:** none changed

- [ ] **Step 1: Run full test suite**

```
pytest tests/ -v
```

Expected: all existing tests PASS, new tests PASS

- [ ] **Step 2: Confirm no import cycles**

```
python -c "from doc_cleaner.extractors import extract_text; print('ok')"
```

Expected: `ok` — no import errors
