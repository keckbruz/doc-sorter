from __future__ import annotations
from pathlib import Path


def extract_plain_text(path: Path, max_chars: int = 0) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if max_chars > 0:
            text = text[:max_chars]
        return text
    except Exception:
        return ""
