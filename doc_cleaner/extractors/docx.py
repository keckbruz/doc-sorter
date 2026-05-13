from __future__ import annotations
from pathlib import Path


def extract_docx_text(path: Path, max_chars: int = 0) -> tuple[str, str | None]:
    try:
        from docx import Document
        doc = Document(str(path))
        parts = [para.text for para in doc.paragraphs if para.text.strip()]
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "python-docx not installed"
    except Exception as e:
        return "", str(e)
