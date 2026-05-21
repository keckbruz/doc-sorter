# EXIF Auto-Rotate & Swift Always-On OCR — Design Spec

**Date:** 2026-05-21

## Problem

1. Phone photos taken in portrait/landscape orientation embed an EXIF rotation tag rather than rotating the pixel data. `pytesseract` reads the raw pixel order and receives rotated text, causing degraded or zero OCR output for common phone-captured documents (ID cards, receipts, contracts).

2. The DocSorter Swift app invokes the Python CLI to scan and classify documents but never passes `--ocr`, making the OCR pipeline dead for every file processed through the UI — even though OCR is now a core feature.

---

## Design

### Feature 1 — EXIF auto-rotate in `doc_cleaner/extractors/image_ocr.py`

Apply `PIL.ImageOps.exif_transpose(img)` immediately after `Image.open()`, before the HEIF format check and before passing the image to `pytesseract`.

```python
from PIL import ImageOps

img = Image.open(str(path))
img = ImageOps.exif_transpose(img)   # honour EXIF orientation; no-op if absent
if img.format == "HEIF":
    img = img.convert("RGB")
text = pytesseract.image_to_string(img, lang=language)
```

**Why this approach:**
- `ImageOps.exif_transpose` is part of Pillow's public API — no extra dependencies.
- It is a strict no-op when the image has no EXIF tag or the tag is absent/identity.
- OSD (pytesseract's orientation detection) was evaluated and rejected: it requires sufficient text density to work reliably, adds latency, and returns spurious results on sparse documents like ID cards.
- One-line change with zero risk to non-rotated images.

**Scope:** `image_ocr.py` only. PDF OCR (`pdf_ocr.py`) renders pages via pymupdf at a fixed coordinate system, so EXIF does not apply there.

---

### Feature 2 — Always-on OCR in `DocSorter/DocSorter/Bridge/PythonBridge.swift`

Add `"--ocr"` and `"--ocr-language", "deu+eng"` to `process.arguments` in both the `scan()` and `suggestTaxonomy()` methods. No Settings key, no toggle, no UI change.

```swift
// scan()
process.arguments = ["-m", "doc_cleaner", "scan", "--ocr", "--ocr-language", "deu+eng", ...]

// suggestTaxonomy()
process.arguments = ["-m", "doc_cleaner", "suggest-taxonomy", "--ocr", "--ocr-language", "deu+eng", ...]
```

**Why always-on:**
- OCR is required for the app to be useful on the document types users throw at it (photos, scans, HEIC images from iPhone).
- A toggle would require UI, Settings, and state management overhead with no benefit — users expect their documents to be read, not silently classified as unreadable.
- The Python CLI already gates OCR behind the flag; the Swift layer simply passes it unconditionally.

---

## Tests

| Test | File | What it checks |
|---|---|---|
| EXIF-rotated image gets correct OCR | `test_extractors.py` | Mocked `ImageOps.exif_transpose` is called; text returned correctly |
| Non-EXIF image: exif_transpose still called (no-op) | `test_extractors.py` | No error raised when image has no EXIF |
| Swift scan args include --ocr | `(manual / UI test)` | Verified by reading PythonBridge.swift |

> Note: Swift unit tests are out of scope. The `PythonBridge.swift` change is a two-line addition verified by code review.

---

## Out of scope

- **OSD / content-based rotation detection** — not robust enough for sparse documents; rejected.
- **Configurable OCR language in Swift UI** — the default `deu+eng` serves the target user base. A language picker is a separate feature.
- **PDF page rotation** — pymupdf handles PDF coordinate systems; EXIF does not apply.
- **Windows/Linux builds of the Swift app** — macOS only.
