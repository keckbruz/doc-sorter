# EXIF Auto-Rotate, Adaptive OSD Retry & Swift Always-On OCR — Design Spec

**Date:** 2026-05-21

## Problem

1. Phone photos taken in portrait/landscape orientation embed an EXIF rotation tag rather than rotating the pixel data. `pytesseract` reads the raw pixel order and receives rotated text, causing degraded or zero OCR output for phone-captured documents (ID cards, receipts, contracts).

2. Image-based PDFs where the embedded image is rotated have no EXIF layer that pymupdf exposes. If the PDF `/Rotate` metadata is absent or wrong, the rendered pixmap is rotated and OCR returns little or no text.

3. The DocSorter Swift app invokes the Python CLI to scan and classify documents but never passes `--ocr`, making the OCR pipeline dead for every file processed through the UI.

---

## Design

### Feature 1 — EXIF auto-rotate in `doc_cleaner/extractors/image_ocr.py`

Apply `PIL.ImageOps.exif_transpose(img)` immediately after `Image.open()`, before the HEIF format check and before passing the image to `pytesseract`. This is a strict no-op when the image has no EXIF tag.

```python
from PIL import Image, ImageOps

img = Image.open(str(path))
img = ImageOps.exif_transpose(img)   # honour EXIF orientation; no-op if absent
if img.format == "HEIF":
    img = img.convert("RGB")
text = pytesseract.image_to_string(img, lang=language)
```

---

### Feature 2 — Adaptive OSD rotation retry

OSD (orientation and script detection via `pytesseract.image_to_osd`) is expensive and unreliable on text-sparse images. Running it unconditionally would hurt performance and return spurious results on most documents. The adaptive strategy: **run OSD only when the first OCR pass returns sparse output**.

The assumption is: if the image is correctly oriented, OCR will return meaningful text. If OCR returns very little, rotation is a plausible cause — try OSD, rotate if needed, and re-run OCR. Return whichever pass produced more text.

#### Sparseness threshold

| Context | Threshold |
|---|---|
| Single image file | `< 20` non-whitespace characters |
| Single PDF page | `< 50` non-whitespace characters (matches existing PDF sparseness check) |

#### Shared helper: `_ocr_with_rotation_retry`

A private helper extracted into both `image_ocr.py` and `pdf_ocr.py` (or a shared `_rotation.py` utility):

```python
def _ocr_with_rotation_retry(
    img: "Image.Image",
    pytesseract: Any,
    language: str,
    sparse_threshold: int,
) -> str:
    text = pytesseract.image_to_string(img, lang=language)
    non_ws = len("".join(text.split()))
    if non_ws >= sparse_threshold:
        return text
    # Sparse — try OSD to detect rotation
    try:
        osd = pytesseract.image_to_osd(img, lang=language, output_type=pytesseract.Output.DICT)
        angle = osd.get("rotate", 0)
    except Exception:
        return text   # OSD failed — keep original result
    if angle == 0:
        return text
    rotated = img.rotate(-angle, expand=True)
    retry = pytesseract.image_to_string(rotated, lang=language)
    return retry if len("".join(retry.split())) > non_ws else text
```

#### `image_ocr.py` integration

After EXIF transpose and HEIF→RGB conversion, replace the direct `image_to_string` call with `_ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=20)`.

#### `pdf_ocr.py` integration

In the per-page loop, replace the direct `image_to_string` call with `_ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=50)`.

---

### Feature 3 — Always-on OCR in `DocSorter/DocSorter/Bridge/PythonBridge.swift`

Add `"--ocr"` and `"--ocr-language", "deu+eng"` to `process.arguments` in both the `scan()` and `suggestTaxonomy()` methods. No Settings key, no toggle, no UI change.

```swift
// scan()
process.arguments = ["-m", "doc_cleaner", "scan", "--ocr", "--ocr-language", "deu+eng", ...]

// suggestTaxonomy()
process.arguments = ["-m", "doc_cleaner", "suggest-taxonomy", "--ocr", "--ocr-language", "deu+eng", ...]
```

The Python CLI already gates OCR behind the flag; the Swift layer simply passes it unconditionally. A toggle would require UI, Settings, and state management overhead with no benefit.

---

## Tests

| Test | File | What it checks |
|---|---|---|
| EXIF-rotated image → `exif_transpose` is applied | `test_extractors.py` | Mocked `ImageOps.exif_transpose` is called |
| Normal OCR output → OSD not triggered | `test_extractors.py` | `image_to_osd` not called when text ≥ threshold |
| Sparse OCR output → OSD triggered, rotation applied, retry OCR | `test_extractors.py` | `image_to_osd` called; rotated image passed to second `image_to_string` call |
| OSD raises exception → original sparse text returned | `test_extractors.py` | No crash; falls back to first-pass text |
| OSD returns 0° → no retry, original text returned | `test_extractors.py` | `img.rotate` not called |
| Retry text worse than original → original returned | `test_extractors.py` | Returns first-pass text when retry is sparser |
| PDF page sparse → OSD triggered per page | `test_extractors.py` | Same OSD path exercised in pdf_ocr context |
| Swift scan args include `--ocr` | code review | Verified by reading `PythonBridge.swift` |

> Swift unit tests are out of scope. The `PythonBridge.swift` change is a two-line addition.

---

## Out of scope

- **OSD run unconditionally on every image** — too slow, too unreliable on sparse documents.
- **Configurable OCR language in Swift UI** — the default `deu+eng` covers the target user base.
- **Windows/Linux builds of the Swift app** — macOS only.
- **Mixed-orientation PDFs** — the sparseness check is per-page, so each page is handled independently.
