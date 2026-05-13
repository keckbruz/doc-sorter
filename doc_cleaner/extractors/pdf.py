from __future__ import annotations
from pathlib import Path


def extract_pdf_text(path: Path, max_chars: int = 0) -> tuple[str, str | None]:
    """Returns (text, error_or_none)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            parts.append(page_text)
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "pypdf not installed"
    except Exception as e:
        return "", str(e)
