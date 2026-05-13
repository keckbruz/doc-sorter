from __future__ import annotations
from pathlib import Path


def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
    """OCR via pytesseract. Soft dependency — returns graceful error if not installed."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img, lang=language)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "ocr_unavailable"
    except Exception as e:
        return "", str(e)
