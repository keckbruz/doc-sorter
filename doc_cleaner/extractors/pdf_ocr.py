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
