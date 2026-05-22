from __future__ import annotations
from pathlib import Path

_HEIC_EXTENSIONS = {".heic", ".heif"}


def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0, rotation_retry: bool = True) -> tuple[str, str | None]:
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
        fmt = img.format
        img = ImageOps.exif_transpose(img)
        if fmt == "HEIF":
            img = img.convert("RGB")
        if rotation_retry:
            text = ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=200)
        else:
            from doc_cleaner.extractors._rotation import _OCR_TIMEOUT
            try:
                text = pytesseract.image_to_string(img, lang=language, timeout=_OCR_TIMEOUT)
            except RuntimeError:
                return "", "ocr_timeout"
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
