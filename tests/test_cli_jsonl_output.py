from pathlib import Path
import json
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from doc_cleaner.cli import app
from doc_cleaner.classifier.schema import ClassificationResult

runner = CliRunner()


def _stdout(result) -> str:
    """Return only stdout content (not stderr) from a CliRunner result."""
    if hasattr(result, "stdout_bytes"):
        return result.stdout_bytes.decode("utf-8")
    # Fallback: typer mixes streams, use full output
    return result.output


MOCK_CLASSIFICATION = ClassificationResult(
    category="Finanzen",
    subcategory="Rechnungen",
    document_date="2024-03-01",
    sender="Vodafone",
    document_type="Rechnung",
    suggested_filename="2024-03_rechnung_vodafone.txt",
    confidence=95,
    reason="Clear invoice",
    needs_review=False,
)


def _run_scan_jsonl(tmp_path):
    doc = tmp_path / "input" / "rechnung.txt"
    doc.parent.mkdir()
    doc.write_text("Vodafone Rechnung 2024")
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    plan = tmp_path / "plan.csv"

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_client_cls, \
         patch("doc_cleaner.cache.ResultCache") as mock_cache_cls:

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_client = MagicMock()
        mock_client.classify.return_value = MOCK_CLASSIFICATION
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, [
            "scan",
            "--input", str(doc.parent),
            "--output-root", str(out_dir),
            "--plan", str(plan),
            "--output-format", "jsonl",
        ])
    return result


def test_jsonl_output_emits_progress_event(tmp_path):
    result = _run_scan_jsonl(tmp_path)
    assert result.exit_code == 0
    stdout = _stdout(result)
    lines = [l for l in stdout.strip().splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    progress = [e for e in events if e["event"] == "progress"]
    assert len(progress) == 1
    assert progress[0]["file"] == "rechnung.txt"
    assert progress[0]["status"] == "classified"
    assert progress[0]["classified"] == 1
    assert progress[0]["review"] == 0
    assert progress[0]["errors"] == 0


def test_jsonl_output_emits_done_event(tmp_path):
    result = _run_scan_jsonl(tmp_path)
    stdout = _stdout(result)
    lines = [l for l in stdout.strip().splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    done = [e for e in events if e["event"] == "done"]
    assert len(done) == 1
    assert done[0]["classified"] == 1
    assert "plan" in done[0]


def test_jsonl_output_emits_error_event_on_connection_error(tmp_path):
    doc = tmp_path / "input" / "rechnung.txt"
    doc.parent.mkdir()
    doc.write_text("Vodafone Rechnung 2024")
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    plan = tmp_path / "plan.csv"

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_client_cls, \
         patch("doc_cleaner.cache.ResultCache") as mock_cache_cls:

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_client = MagicMock()
        mock_client.classify.side_effect = ConnectionError("Ollama is not running at http://127.0.0.1:11434")
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, [
            "scan",
            "--input", str(doc.parent),
            "--output-root", str(out_dir),
            "--plan", str(plan),
            "--output-format", "jsonl",
        ])

    assert result.exit_code == 1
    stdout = _stdout(result)
    lines = [l for l in stdout.strip().splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert "Ollama" in error_events[0]["message"]


def test_text_format_emits_no_json(tmp_path):
    doc = tmp_path / "input" / "rechnung.txt"
    doc.parent.mkdir()
    doc.write_text("Vodafone Rechnung 2024")
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_client_cls, \
         patch("doc_cleaner.cache.ResultCache") as mock_cache_cls:

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_client = MagicMock()
        mock_client.classify.return_value = MOCK_CLASSIFICATION
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, [
            "scan",
            "--input", str(doc.parent),
            "--output-root", str(out_dir),
        ])

    assert result.exit_code == 0
    # stdout should be empty (rich output goes to stderr)
    stdout = _stdout(result)
    assert stdout.strip() == ""
