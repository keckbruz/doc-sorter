from __future__ import annotations
import re
from datetime import datetime
from doc_cleaner.scanner import FileMetadata

PROMPT_VERSION = "v3"

_DATE_RE = re.compile(r'\d{1,2}[.\/\-]\d{1,2}[.\/\-]\d{2,4}|\d{4}[.\/\-]\d{2}[.\/\-]\d{2}')
_KEYWORD_RE = re.compile(
    r'\b(Rechnung|Invoice|Kontoauszug|Statement|Vertrag|Contract|'
    r'Bescheid|Beitragsrechnung|Steuerbescheid|Mahnung|Quittung|Receipt|'
    r'Zertifikat|Certificate|Kundigung|Kündigung|Mietvertrag|'
    r'Lohnabrechnung|Gehaltsabrechnung|Versicherung|Insurance|'
    r'Bank|IBAN|GmbH|AG|UG|Ltd|Corp|Inc|Sparkasse|Finanzamt)\b',
    re.IGNORECASE,
)


def select_excerpt(
    text: str,
    first_n: int = 1500,
    last_n: int = 500,
    max_keyword_lines: int = 20,
) -> str:
    if not text:
        return ""

    first = text[:first_n]
    last = text[-last_n:] if len(text) > first_n + last_n else ""

    keyword_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and (_DATE_RE.search(stripped) or _KEYWORD_RE.search(stripped)):
            keyword_lines.append(stripped)
            if len(keyword_lines) >= max_keyword_lines:
                break

    parts = [first]
    if last:
        parts.extend(["\n[...]\n", last])
    if keyword_lines:
        parts.extend(["\n[Key lines:]\n", "\n".join(keyword_lines)])

    return "".join(parts)


def build_prompt(
    meta: FileMetadata,
    text: str,
    taxonomy: dict[str, list[str]],
    first_n: int = 1500,
    last_n: int = 500,
) -> str:
    categories_str = "\n".join(
        f"- {cat}" + (f": {', '.join(subs)}" if subs else "")
        for cat, subs in taxonomy.items()
    )
    excerpt = select_excerpt(text, first_n, last_n)
    modified_iso = datetime.fromtimestamp(meta.modified_time).strftime("%Y-%m-%d")

    return f"""You are a document classifier. Classify the following document.
Respond in German. Use German for document_type, reason, and suggested_filename.

ALLOWED CATEGORIES AND SUBCATEGORIES:
{categories_str}

FILE METADATA:
- Filename: {meta.filename}
- Extension: {meta.extension}
- Size: {meta.file_size} bytes
- Modified: {modified_iso}
- MIME: {meta.mime_type}
- Path hint (may be unreliable): {meta.relative_path}

DOCUMENT TEXT EXCERPT:
{excerpt or "(no text extracted)"}

INSTRUCTIONS:
- Choose category and subcategory ONLY from the allowed list above.
- Use "Review" if you are not confident about the category.
- Do not hallucinate dates, senders, or document types that are not present in the text.
- If the date is unknown, set document_date to null.
- If the sender is unknown, set sender to null.
- confidence must be an integer 0-100.
- Set needs_review to true if confidence < 80 or if category is "Review".
- document_type must be specific, not generic. Include the product, subject, or topic when the type alone would be ambiguous. Prefer "FritzBox-7590-Benutzerhandbuch" over "Benutzerhandbuch", "Mietvertrag-Hauptstrasse-12" over "Mietvertrag".
- Return valid JSON only. Do not include markdown. Do not include explanations outside the JSON object.

Return exactly this JSON structure:
{{
  "category": "...",
  "subcategory": "... or null",
  "document_date": "YYYY-MM-DD or null",
  "sender": "... or null",
  "document_type": "...",
  "suggested_filename": "YYYY-MM_documenttype_sender.ext",
  "confidence": 0,
  "reason": "...",
  "needs_review": true
}}"""
