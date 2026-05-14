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


def test_generate_disables_thinking_output():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "{}"}
    client._client.post = MagicMock(return_value=mock_response)  # type: ignore[method-assign]

    client.generate("prompt")

    payload = client._client.post.call_args.kwargs["json"]  # type: ignore[union-attr]
    assert payload["think"] is False
    assert "think" not in payload["options"]


def test_suggest_taxonomy_parses_valid_json():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    payload = {"Finanzen": ["Rechnungen", "Steuern"], "Wohnen": ["Miete"]}
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": json.dumps(payload)}
    client._client.post = MagicMock(return_value=mock_response)

    result = client.suggest_taxonomy([("rechnung.pdf", "Vodafone GmbH Rechnung"), ("mietvertrag.docx", "")])
    assert result == payload


def test_suggest_taxonomy_strips_fences():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    payload = {"Finanzen": ["Steuern"]}
    wrapped = f"```json\n{json.dumps(payload)}\n```"
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": wrapped}
    client._client.post = MagicMock(return_value=mock_response)

    result = client.suggest_taxonomy([("steuerbescheid.pdf", "Finanzamt München")])
    assert result == payload


def test_suggest_taxonomy_returns_empty_on_bad_json():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "not json at all"}
    client._client.post = MagicMock(return_value=mock_response)

    result = client.suggest_taxonomy([("file.pdf", "")])
    assert result == {}


def test_suggest_taxonomy_returns_empty_on_non_dict():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": '["list", "not", "dict"]'}
    client._client.post = MagicMock(return_value=mock_response)

    result = client.suggest_taxonomy([("file.pdf", "")])
    assert result == {}


def test_suggest_taxonomy_normalises_non_list_values():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    payload = {"Finanzen": "Rechnungen"}  # string instead of list
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": json.dumps(payload)}
    client._client.post = MagicMock(return_value=mock_response)

    result = client.suggest_taxonomy([("file.pdf", "")])
    assert result["Finanzen"] == []


def test_suggest_taxonomy_includes_peek_in_prompt():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "{}"}
    client._client.post = MagicMock(return_value=mock_response)

    client.suggest_taxonomy([("rechnung.pdf", "Vodafone GmbH Rechnung März 2024")])

    prompt = client._client.post.call_args.kwargs["json"]["prompt"]
    assert "Vodafone GmbH" in prompt
    assert "rechnung.pdf" in prompt


def test_suggest_taxonomy_omits_empty_peek():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "{}"}
    client._client.post = MagicMock(return_value=mock_response)

    client.suggest_taxonomy([("image.jpg", "")])

    prompt = client._client.post.call_args.kwargs["json"]["prompt"]
    assert '""' not in prompt
    assert "image.jpg" in prompt


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
