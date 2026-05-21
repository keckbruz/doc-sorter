from __future__ import annotations
from typing import Any


def ocr_with_rotation_retry(
    img: Any,
    pytesseract: Any,
    language: str,
    sparse_threshold: int,
) -> str:
    """Run OCR; if result is sparse, use OSD to detect rotation, rotate, and retry.

    Returns whichever pass produced more non-whitespace text.
    Falls back to the first-pass result if OSD raises or returns 0°.
    """
    text = pytesseract.image_to_string(img, lang=language)
    non_ws = len("".join(text.split()))
    if non_ws >= sparse_threshold:
        return text
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        angle = osd.get("rotate", 0)
    except Exception:
        return text
    if angle == 0:
        return text
    rotated = img.rotate(-angle, expand=True)
    retry = pytesseract.image_to_string(rotated, lang=language)
    return retry if len("".join(retry.split())) > non_ws else text
