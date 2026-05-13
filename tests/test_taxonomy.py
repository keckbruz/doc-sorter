from pathlib import Path
import pytest
from doc_cleaner.taxonomy import load_taxonomy, is_valid_category, normalize_category, REVIEW_CATEGORY

TAXONOMY_PATH = Path(__file__).parent.parent / "taxonomy.yaml"


def test_load_taxonomy_returns_dict():
    t = load_taxonomy(TAXONOMY_PATH)
    assert isinstance(t, dict)
    assert "Finance" in t
    assert "Review" in t


def test_finance_subcategories():
    t = load_taxonomy(TAXONOMY_PATH)
    assert "Banking" in t["Finance"]
    assert "Insurance" in t["Finance"]


def test_review_is_always_valid():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Review", None, t) is True


def test_valid_category_with_subcategory():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finance", "Banking", t) is True


def test_invalid_category_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("CloudStorage", None, t) is False


def test_invalid_subcategory_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finance", "Crypto", t) is False


def test_normalize_unknown_category_returns_review():
    t = load_taxonomy(TAXONOMY_PATH)
    cat, sub = normalize_category("WeirdCategory", None, t)
    assert cat == REVIEW_CATEGORY


def test_review_constant():
    assert REVIEW_CATEGORY == "Review"


def test_load_taxonomy_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_taxonomy(Path("/nonexistent/taxonomy.yaml"))
