from pathlib import Path
import pytest
from doc_cleaner.taxonomy import (
    load_taxonomy,
    is_valid_category,
    normalize_category,
    read_output_taxonomy,
    merge_taxonomies,
    REVIEW_CATEGORY,
)

TAXONOMY_PATH = Path(__file__).parent.parent / "taxonomy.yaml"


def test_load_taxonomy_returns_dict():
    t = load_taxonomy(TAXONOMY_PATH)
    assert isinstance(t, dict)
    assert "Finanzen" in t
    assert "Review" in t


def test_finanzen_subcategories():
    t = load_taxonomy(TAXONOMY_PATH)
    assert "Bankwesen" in t["Finanzen"]
    assert "Versicherung" in t["Finanzen"]


def test_review_is_always_valid():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Review", None, t) is True


def test_valid_category_with_subcategory():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finanzen", "Steuern", t) is True


def test_invalid_category_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("CloudStorage", None, t) is False


def test_invalid_subcategory_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finanzen", "Crypto", t) is False


def test_normalize_unknown_category_returns_review():
    t = load_taxonomy(TAXONOMY_PATH)
    cat, sub = normalize_category("WeirdCategory", None, t)
    assert cat == REVIEW_CATEGORY


def test_review_constant():
    assert REVIEW_CATEGORY == "Review"


def test_load_taxonomy_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_taxonomy(Path("/nonexistent/taxonomy.yaml"))


# --- read_output_taxonomy ---

def test_read_output_taxonomy_empty_dir(tmp_path):
    result = read_output_taxonomy(tmp_path)
    assert result == {}


def test_read_output_taxonomy_nonexistent(tmp_path):
    result = read_output_taxonomy(tmp_path / "does-not-exist")
    assert result == {}


def test_read_output_taxonomy_reads_two_levels(tmp_path):
    (tmp_path / "Finanzen").mkdir()
    (tmp_path / "Finanzen" / "Steuern").mkdir()
    (tmp_path / "Finanzen" / "Rechnungen").mkdir()
    (tmp_path / "Wohnen").mkdir()

    result = read_output_taxonomy(tmp_path)
    assert "Finanzen" in result
    assert "Steuern" in result["Finanzen"]
    assert "Rechnungen" in result["Finanzen"]
    assert "Wohnen" in result
    assert result["Wohnen"] == []


def test_read_output_taxonomy_skips_hidden(tmp_path):
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "Arbeit").mkdir()

    result = read_output_taxonomy(tmp_path)
    assert ".hidden" not in result
    assert "Arbeit" in result


def test_read_output_taxonomy_skips_files(tmp_path):
    (tmp_path / "Finanzen").mkdir()
    (tmp_path / "readme.txt").write_text("hello")

    result = read_output_taxonomy(tmp_path)
    assert "readme.txt" not in result
    assert "Finanzen" in result


# --- merge_taxonomies ---

def test_merge_taxonomies_adds_new_category():
    base = {"Finanzen": ["Steuern"], "Review": []}
    overlay = {"Arbeit": ["Verträge"]}
    merged = merge_taxonomies(base, overlay)
    assert "Arbeit" in merged
    assert merged["Arbeit"] == ["Verträge"]


def test_merge_taxonomies_adds_new_subcategory():
    base = {"Finanzen": ["Steuern"], "Review": []}
    overlay = {"Finanzen": ["Sonstiges"]}
    merged = merge_taxonomies(base, overlay)
    assert "Steuern" in merged["Finanzen"]
    assert "Sonstiges" in merged["Finanzen"]


def test_merge_taxonomies_no_duplicates():
    base = {"Finanzen": ["Steuern"], "Review": []}
    overlay = {"Finanzen": ["Steuern"]}
    merged = merge_taxonomies(base, overlay)
    assert merged["Finanzen"].count("Steuern") == 1


def test_merge_taxonomies_does_not_mutate_base():
    base = {"Finanzen": ["Steuern"], "Review": []}
    overlay = {"Finanzen": ["Sonstiges"], "Neu": []}
    merge_taxonomies(base, overlay)
    assert "Sonstiges" not in base["Finanzen"]
    assert "Neu" not in base


def test_merge_taxonomies_preserves_review():
    base = {"Finanzen": ["Steuern"], "Review": []}
    overlay = {"Arbeit": []}
    merged = merge_taxonomies(base, overlay)
    assert "Review" in merged
    assert merged["Review"] == []
