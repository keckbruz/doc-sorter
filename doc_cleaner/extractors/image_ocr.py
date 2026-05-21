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
        if img.format == "HEIF":
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang=language)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
