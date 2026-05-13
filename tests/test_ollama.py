from pathlib import Path
import json
import pytest
from unittest.mock import MagicMock, patch
from doc_cleaner.classifier.ollama import OllamaClient, parse_classification
from doc_cleaner.classifier.schema import ClassificationResult
from doc_cleaner.cache import ResultCache


VALID_JSON = json.dumps({
    "category": "Finance",
    "subcategory": "Insurance",
    "document_date": "2024-03-12",
    "sender": "Allianz",
    "document_type": "Beitragsrechnung",
    "suggested_filename": "2024-03-12 - Allianz - Beitragsrechnung.pdf",
    "confidence": 92,
    "reason": "Contains Allianz.",
    "needs_review": False,
})


def test_parse_valid_json():
    result = parse_classification(VALID_JSON)
    assert isinstance(result, ClassificationResult)
    assert result.category == "Finance"
    assert result.confidence == 92


def test_parse_invalid_json_returns_review():
    result = parse_classification("not json at all {{broken")
    assert result.category == "Review"
    assert result.needs_review is True
    assert result.confidence == 0


def test_parse_json_with_markdown_fences():
    wrapped = f"```json\n{VALID_JSON}\n```"
    result = parse_classification(wrapped)
    assert result.category == "Finance"


def test_ollama_client_blocks_non_localhost():
    with pytest.raises(ValueError, match="allow-remote-ollama"):
        OllamaClient(host="https://api.example.com", model="test", allow_remote=False)


def test_ollama_client_allows_localhost():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    assert client.host == "http://127.0.0.1:11434"


def test_result_cache_miss(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    result = cache.get("abc123", "model-name")
    assert result is None


def test_result_cache_set_and_get(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    r = ClassificationResult(
        category="Finance", suggested_filename="x.pdf",
        confidence=90, reason="test", needs_review=False,
    )
    cache.set("abc123", "model-name", r)
    retrieved = cache.get("abc123", "model-name")
    assert retrieved is not None
    assert retrieved.category == "Finance"


def test_result_cache_different_model_is_miss(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    r = ClassificationResult(
        category="Finance", suggested_filename="x.pdf",
        confidence=90, reason="test", needs_review=False,
    )
    cache.set("abc123", "model-a", r)
    assert cache.get("abc123", "model-b") is None
