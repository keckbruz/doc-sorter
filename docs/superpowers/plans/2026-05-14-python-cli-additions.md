# Python CLI Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new CLI entry points to the Python backend that the SwiftUI app needs: JSONL progress streaming from `scan`, and a standalone `suggest-taxonomy` subcommand.

**Architecture:** Both additions live in `doc_cleaner/cli.py`. The JSONL output is additive — `scan` gets a new `--output-format` flag that defaults to `text` (existing behaviour unchanged). `suggest-taxonomy` is a new `@app.command()` that reuses existing `OllamaClient.suggest_taxonomy()` and `read_output_taxonomy()`. No existing commands change behaviour.

**Tech Stack:** Python 3.11, Typer, existing doc_cleaner modules.

---

## File Structure

- **Modify:** `doc_cleaner/cli.py` — add `--output-format` to `scan`, add `suggest-taxonomy` command
- **Create:** `tests/test_cli_jsonl_output.py` — tests for JSONL progress events
- **Create:** `tests/test_cli_suggest_taxonomy.py` — tests for suggest-taxonomy command

---

### Task 1: Add `--output-format jsonl` to `scan`

**Files:**
- Modify: `doc_cleaner/cli.py:63-88` (scan signature)
- Modify: `doc_cleaner/cli.py:138-260` (scan body — per-file loop and completion)
- Create: `tests/test_cli_jsonl_output.py`

The scan command should emit one JSON line to stdout per file when `--output-format jsonl` is passed. Rich output goes to stderr (already the case via `Console(stderr=True)`), so stdout is clean for machine consumption.

**JSONL event shapes:**

```python
# Per-file progress:
{"event": "progress", "file": "steuerbescheid.pdf", "status": "classified", "classified": 12, "review": 3, "errors": 0, "total": null}
# "total" is null because we don't know file count until scan finishes

# On completion:
{"event": "done", "plan": "/path/to/plan.csv", "undo": null, "classified": 19, "review": 5, "errors": 0}
# "undo" is null because scan is always dry-run; undo path comes from apply

# On fatal error (ConnectionError etc.):
{"event": "error", "message": "Ollama is not running at http://127.0.0.1:11434"}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_jsonl_output.py`:

```python
from pathlib import Path
import json
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from doc_cleaner.cli import app
from doc_cleaner.classifier.schema import ClassificationResult

runner = CliRunner(mix_stderr=False)

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
         patch("doc_cleaner.cli.OllamaClient") as mock_client_cls, \
         patch("doc_cleaner.cli.ResultCache") as mock_cache_cls:

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
    lines = [l for l in result.output.strip().splitlines() if l.strip()]
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
    lines = [l for l in result.output.strip().splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    done = [e for e in events if e["event"] == "done"]
    assert len(done) == 1
    assert done[0]["classified"] == 1
    assert "plan" in done[0]


def test_text_format_emits_no_json(tmp_path):
    doc = tmp_path / "input" / "rechnung.txt"
    doc.parent.mkdir()
    doc.write_text("Vodafone Rechnung 2024")
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.cli.OllamaClient") as mock_client_cls, \
         patch("doc_cleaner.cli.ResultCache") as mock_cache_cls:

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
    assert result.output.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli_jsonl_output.py -v
```

Expected: FAIL — `--output-format` option not yet recognised.

- [ ] **Step 3: Add `--output-format` parameter to `scan` signature**

In `doc_cleaner/cli.py`, add one parameter to the `scan` function signature (after `quiet`):

```python
    quiet: bool = typer.Option(False, "--quiet"),
    output_format: str = typer.Option("text", "--output-format", help="Output format: text or jsonl"),
) -> None:
```

- [ ] **Step 4: Add JSONL emission inside the scan loop**

In `doc_cleaner/cli.py`, at the end of the per-file `try/except` block (after `writer.write(...)`), add:

```python
            if output_format == "jsonl":
                import json as _json
                print(_json.dumps({
                    "event": "progress",
                    "file": meta.filename,
                    "status": status,
                    "classified": counts["classified"],
                    "review": counts["review"],
                    "errors": counts["errors"],
                    "total": None,
                }), flush=True)
```

- [ ] **Step 5: Add JSONL done event after the scan loop**

After the `with PlanWriter(...) as writer:` block closes, add:

```python
    if output_format == "jsonl":
        import json as _json
        print(_json.dumps({
            "event": "done",
            "plan": str(plan_path),
            "undo": None,
            "classified": counts["classified"],
            "review": counts["review"],
            "errors": counts["errors"],
        }), flush=True)
```

Also wrap the `ConnectionError` raise to emit an error event first:

```python
            except ConnectionError as e:
                if output_format == "jsonl":
                    import json as _json
                    print(_json.dumps({"event": "error", "message": str(e)}), flush=True)
                console.print(f"\n[red]{e}[/red]")
                raise typer.Exit(1)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli_jsonl_output.py -v
```

Expected: 3 PASS.

- [ ] **Step 7: Run full suite to check for regressions**

```bash
python3 -m pytest --tb=short -q
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add doc_cleaner/cli.py tests/test_cli_jsonl_output.py
git commit -m "feat: add --output-format jsonl to scan command"
```

---

### Task 2: Add `suggest-taxonomy` subcommand

**Files:**
- Modify: `doc_cleaner/cli.py` — new `@app.command("suggest-taxonomy")`
- Create: `tests/test_cli_suggest_taxonomy.py`

This command runs the peek-read + LLM taxonomy suggestion and prints JSON to stdout. It is used by the SwiftUI app before starting a scan.

```
python3 -m doc_cleaner suggest-taxonomy \
  --input ~/Downloads \
  --output-root ~/Documents \
  --model qwen3.5:9b
```

Stdout (JSON, not JSONL):
```json
{"Technik": ["Gerätehandbücher"], "Persönliches": ["Reise"]}
```

Returns `{}` if no additions needed. Always exits 0 unless Ollama is unreachable.

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_suggest_taxonomy.py`:

```python
import json
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from doc_cleaner.cli import app

runner = CliRunner(mix_stderr=False)


def test_suggest_taxonomy_prints_json(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "rechnung.txt").write_text("Vodafone Rechnung")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    suggestion = {"Technik": ["Gerätehandbücher"]}

    with patch("doc_cleaner.cli._ensure_ollama"), \
         patch("doc_cleaner.cli.OllamaClient") as mock_cls:
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
         patch("doc_cleaner.cli.OllamaClient") as mock_cls:
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_cli_suggest_taxonomy.py -v
```

Expected: FAIL — `suggest-taxonomy` command not yet defined.

- [ ] **Step 3: Implement `suggest-taxonomy` command**

Add to `doc_cleaner/cli.py` after the existing `doctor` command:

```python
@app.command("suggest-taxonomy")
def suggest_taxonomy_cmd(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Output folder (used as existing taxonomy context)"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    max_text_chars: int = typer.Option(300, "--max-text-chars"),
) -> None:
    """Suggest taxonomy additions for a folder of documents. Prints JSON to stdout."""
    import json as _json
    from rich.console import Console
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.scanner import scan_files
    from doc_cleaner.taxonomy import (
        load_taxonomy, merge_taxonomies, read_output_taxonomy
    )

    console = Console(stderr=True)
    _ensure_ollama(ollama_host, console)

    resolved_input = input.expanduser().resolve()
    resolved_output = output_root.expanduser().resolve()

    all_meta = list(scan_files(resolved_input, max_files=300))
    if not all_meta:
        print(_json.dumps({}))
        return

    files: list[tuple[str, str]] = []
    for meta in all_meta:
        try:
            result = extract_text(meta, max_chars=max_text_chars, ocr=False)
            peek = result.text.strip()
        except Exception:
            peek = ""
        files.append((meta.filename, peek))

    base_tax_path = Path(__file__).parent.parent / "taxonomy.yaml"
    base_tax = load_taxonomy(base_tax_path)
    folder_tax = read_output_taxonomy(resolved_output)
    existing = merge_taxonomies(base_tax, folder_tax)

    try:
        client = OllamaClient(host=ollama_host, model=model, allow_remote=allow_remote_ollama)
        additions = client.suggest_taxonomy(files, existing=existing)
    except Exception:
        additions = {}

    print(_json.dumps(additions, ensure_ascii=False))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_cli_suggest_taxonomy.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest --tb=short -q
```

Expected: all passing.

- [ ] **Step 6: Smoke-test manually**

```bash
python3 -m doc_cleaner suggest-taxonomy \
  --input test_docs/generated \
  --output-root sorted
```

Expected: JSON printed to stdout, e.g. `{"Persönliches": ["Reise"]}` or `{}`.

- [ ] **Step 7: Commit**

```bash
git add doc_cleaner/cli.py tests/test_cli_suggest_taxonomy.py
git commit -m "feat: add suggest-taxonomy subcommand for SwiftUI bridge"
```
