from pathlib import Path
import pytest
from doc_cleaner.classifier.prompts import build_prompt, select_excerpt, PROMPT_VERSION
from doc_cleaner.scanner import FileMetadata


def _meta(tmp_path, filename="invoice.pdf"):
    p = tmp_path / filename
    p.write_text("x")
    return FileMetadata(
        original_path=p,
        relative_path=Path(filename),
        filename=filename,
        extension=".pdf",
        file_size=1,
        created_time=None,
        modified_time=1700000000.0,
        mime_type="application/pdf",
        file_hash="abc123",
    )


def test_prompt_version_is_string():
    assert isinstance(PROMPT_VERSION, str)
    assert len(PROMPT_VERSION) > 0


def test_build_prompt_contains_filename(tmp_path):
    taxonomy = {"Finance": ["Banking"], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "Some invoice text", taxonomy)
    assert "invoice.pdf" in prompt


def test_build_prompt_contains_categories(tmp_path):
    taxonomy = {"Finance": ["Banking"], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "text", taxonomy)
    assert "Finance" in prompt
    assert "Review" in prompt


def test_build_prompt_json_instruction(tmp_path):
    taxonomy = {"Finance": [], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "text", taxonomy)
    assert "Return valid JSON only" in prompt
    assert "markdown" in prompt.lower()


def test_select_excerpt_short_text():
    text = "short text"
    result = select_excerpt(text, first_n=1500, last_n=500)
    assert result == text


def test_select_excerpt_includes_first_and_last():
    text = "A" * 3000
    result = select_excerpt(text, first_n=100, last_n=50)
    assert result.startswith("A" * 100)


def test_select_excerpt_empty():
    assert select_excerpt("") == ""


def test_select_excerpt_captures_keyword_lines():
    text = "boring line\nRechnung from Allianz\nboring line 2\n12.03.2024 payment"
    result = select_excerpt(text, first_n=5, last_n=5)
    assert "Rechnung" in result or "2024" in result
