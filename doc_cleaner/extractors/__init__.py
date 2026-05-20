from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from doc_cleaner.scanner import FileMetadata

TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".log", ".json", ".xml", ".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".heic", ".heif"}


@dataclass
class ExtractionResult:
    text: str
    extractor: str   # "pdf" | "pdf_ocr" | "docx" | "text" | "image_ocr" | "none" | error code if dependency missing
    error: str | None = None


def extract_text(
    meta: FileMetadata,
    max_chars: int = 0,
    ocr: bool = False,
    ocr_language: str = "deu+eng",
) -> ExtractionResult:
    ext = meta.extension

    if ext in TEXT_EXTENSIONS:
        from doc_cleaner.extractors.text import extract_plain_text
        text = extract_plain_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="text")

    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err, page_count = extract_pdf_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="pdf", error=err)

    if ext in DOCX_EXTENSIONS:
        from doc_cleaner.extractors.docx import extract_docx_text
        text, err = extract_docx_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="docx", error=err)

    if ext in IMAGE_EXTENSIONS and ocr:
        from doc_cleaner.extractors.image_ocr import extract_ocr_text
        text, err = extract_ocr_text(meta.original_path, ocr_language, max_chars)
        extractor = "ocr_unavailable" if err == "ocr_unavailable" else "image_ocr"
        return ExtractionResult(text=text, extractor=extractor, error=err)

    return ExtractionResult(text="", extractor="none")
