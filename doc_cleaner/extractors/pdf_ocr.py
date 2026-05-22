from __future__ import annotations
from pathlib import Path

_MAX_OCR_PAGES = 10


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
            accumulated = 0
            for page in doc:
                if page.number >= _MAX_OCR_PAGES:
                    break
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                page_text = ocr_with_rotation_retry(img, pytesseract, language, sparse_threshold=50)
                parts.append(page_text)
                accumulated += len("".join(page_text.split()))
                if max_chars > 0 and accumulated >= max_chars:
                    break
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except Exception as e:
        return "", str(e)
