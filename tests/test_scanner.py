from pathlib import Path
import pytest
from doc_cleaner.scanner import scan_files, FileMetadata


@pytest.fixture
def doc_tree(tmp_path):
    (tmp_path / "Finance").mkdir()
    (tmp_path / "Finance" / "invoice.txt").write_text("Invoice dated 2024-03-12")
    (tmp_path / "Legal").mkdir()
    (tmp_path / "Legal" / "contract.txt").write_text("Rental contract 2021-06-02")
    # Hidden file — should be skipped by default
    (tmp_path / ".DS_Store").write_bytes(b"hidden")
    # System dir — should be skipped
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.js").write_text("skip me")
    # Nested
    (tmp_path / "Finance" / "sub").mkdir()
    (tmp_path / "Finance" / "sub" / "deep.txt").write_text("deep file")
    return tmp_path


def test_scan_finds_regular_files(doc_tree):
    results = list(scan_files(doc_tree))
    paths = [r.filename for r in results]
    assert "invoice.txt" in paths
    assert "contract.txt" in paths


def test_scan_skips_hidden_files(doc_tree):
    results = list(scan_files(doc_tree))
    assert not any(r.filename.startswith(".") for r in results)


def test_scan_skips_node_modules(doc_tree):
    results = list(scan_files(doc_tree))
    # Check that no path component is literally "node_modules"
    # (avoid false positive: pytest tmp dir name includes "node_modules" from test name)
    assert not any(
        "node_modules" in r.original_path.parts
        for r in results
    )


def test_include_hidden_flag(doc_tree):
    results = list(scan_files(doc_tree, include_hidden=True))
    assert any(r.filename == ".DS_Store" for r in results)


def test_max_files_limit(doc_tree):
    results = list(scan_files(doc_tree, max_files=1))
    assert len(results) == 1


def test_max_depth(doc_tree):
    # max_depth=1: only files directly inside root-level subdirs
    # Finance/sub/deep.txt is at depth 2, should NOT appear
    results = list(scan_files(doc_tree, max_depth=1))
    assert not any(r.filename == "deep.txt" for r in results)


def test_metadata_fields(doc_tree):
    results = list(scan_files(doc_tree))
    meta = next(r for r in results if r.filename == "invoice.txt")
    assert isinstance(meta, FileMetadata)
    assert meta.extension == ".txt"
    assert meta.file_size > 0
    assert len(meta.file_hash) == 64  # SHA-256 hex
    assert meta.modified_time > 0
    assert meta.original_path.is_absolute()


def test_relative_path(doc_tree):
    results = list(scan_files(doc_tree))
    meta = next(r for r in results if r.filename == "invoice.txt")
    assert not meta.relative_path.is_absolute()
    assert str(meta.relative_path) == "Finance/invoice.txt"
