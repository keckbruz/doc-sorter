import json
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from doc_cleaner.cli import app

runner = CliRunner()


def test_suggest_taxonomy_prints_json(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "rechnung.txt").write_text("Vodafone Rechnung")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    suggestion = {"Technik": ["Gerätehandbücher"]}

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.suggest_taxonomy.return_value = suggestion
        mock_cls.return_value = mock_client

        result = runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
            "--model", "qwen3.5:9b",
        ])

    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data == suggestion


def test_suggest_taxonomy_returns_empty_when_no_files(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("doc_cleaner.cli._ensure_ollama"):
        result = runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
        ])

    assert result.exit_code == 0
    assert json.loads(result.output.strip()) == {}


def test_suggest_taxonomy_merges_output_folder_as_existing(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "doc.txt").write_text("some document")
    output_dir = tmp_path / "output"
    (output_dir / "Finanzen" / "Steuern").mkdir(parents=True)

    captured_existing = {}

    def capture_suggest(files, existing=None):
        captured_existing.update(existing or {})
        return {}

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.suggest_taxonomy.side_effect = capture_suggest
        mock_cls.return_value = mock_client

        runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
        ])

    assert "Finanzen" in captured_existing
    assert "Steuern" in captured_existing["Finanzen"]


def test_suggest_taxonomy_returns_empty_on_llm_error(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "doc.txt").write_text("some document")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.suggest_taxonomy.side_effect = RuntimeError("LLM timeout")
        mock_cls.return_value = mock_client

        result = runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
        ])

    assert result.exit_code == 0
    # The warning goes to stderr (mixed into output by CliRunner); the last line is JSON
    json_line = result.output.strip().splitlines()[-1]
    assert json.loads(json_line) == {}


def test_suggest_taxonomy_passes_ocr_flag_to_extract_text(tmp_path, mocker):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "scan.jpg").write_bytes(b"\xff\xd8fake jpeg")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    captured_calls = []

    def fake_extract_text(meta, max_chars=0, ocr=False, ocr_language="deu+eng"):
        captured_calls.append({"ocr": ocr, "ocr_language": ocr_language})
        from doc_cleaner.extractors import ExtractionResult
        return ExtractionResult(text="", extractor="none")

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.extractors.extract_text", side_effect=fake_extract_text), \
         patch("doc_cleaner.classifier.ollama.OllamaClient") as mock_cls:
        mock_cls.return_value.suggest_taxonomy.return_value = {}
        runner.invoke(app, [
            "suggest-taxonomy",
            "--input", str(input_dir),
            "--output-root", str(output_dir),
            "--ocr",
            "--ocr-language", "eng",
        ])

    assert len(captured_calls) == 1
    assert captured_calls[0]["ocr"] is True
    assert captured_calls[0]["ocr_language"] == "eng"
