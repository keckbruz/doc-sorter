from pathlib import Path
import pytest
from doc_cleaner.scanner import FileMetadata
from doc_cleaner.extractors import extract_text, ExtractionResult


def _make_meta(path: Path, ext: str, mime: str) -> FileMetadata:
    return FileMetadata(
        original_path=path,
        relative_path=Path(path.name),
        filename=path.name,
        extension=ext,
        file_size=path.stat().st_size,
        created_time=None,
        modified_time=path.stat().st_mtime,
        mime_type=mime,
        file_hash="abc123",
    )


def test_extract_plain_text(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Hello world from a text file.")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert isinstance(result, ExtractionResult)
    assert "Hello world" in result.text
    assert result.extractor == "text"
    assert result.error is None


def test_extract_markdown(tmp_path):
    p = tmp_path / "readme.md"
    p.write_text("# Title\n\nSome content here.")
    meta = _make_meta(p, ".md", "text/markdown")
    result = extract_text(meta)
    assert "Title" in result.text
    assert result.extractor == "text"


def test_extract_unsupported_returns_empty(tmp_path):
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x00\x01\x02")
    meta = _make_meta(p, ".bin", "application/octet-stream")
    result = extract_text(meta)
    assert result.text == ""
    assert result.extractor == "none"


def test_extract_empty_file_returns_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert result.text == ""
    assert result.error is None


def test_extraction_result_dataclass():
    r = ExtractionResult(text="hello", extractor="text")
    assert r.error is None
