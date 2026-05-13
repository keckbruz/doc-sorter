from __future__ import annotations
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Footer, Header,
    Input, Label, Static,
)


class ProgressUpdate(Message):
    def __init__(self, current: str, scanned: int, classified: int, review: int, errors: int) -> None:
        super().__init__()
        self.current = current
        self.scanned = scanned
        self.classified = classified
        self.review = review
        self.errors = errors


class ScanDone(Message):
    def __init__(self, rows: list, error: str = "") -> None:
        super().__init__()
        self.rows = rows
        self.error = error


class ConfigScreen(Screen):
    CSS = """
    #config-form {
        align: center middle;
        width: 60;
        height: auto;
        padding: 2 4;
        border: round $primary;
    }
    #config-form Label { margin-bottom: 1; }
    #config-form Input { margin-bottom: 2; }
    #start { width: 100%; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="config-form"):
            yield Label("Folder to scan:")
            yield Input(value=str(Path.cwd()), id="input-dir")
            yield Label("Output root (where sorted files go):")
            yield Input(placeholder="e.g. ~/Documents/Sorted", id="output-root")
            yield Label("Ollama model:")
            yield Input(value="qwen3.5:9b", id="model")
            yield Button("Start Scan", id="start", variant="primary", disabled=True)
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        output_val = self.query_one("#output-root", Input).value.strip()
        self.query_one("#start", Button).disabled = not output_val

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "start":
            return
        input_dir = Path(self.query_one("#input-dir", Input).value.strip()).expanduser()
        output_root = Path(self.query_one("#output-root", Input).value.strip()).expanduser()
        model = self.query_one("#model", Input).value.strip() or "qwen3.5:9b"

        if not input_dir.is_dir():
            self.notify(f"Folder not found: {input_dir}", severity="error")
            return

        self.app.push_screen(ScanScreen(input_dir, output_root, model))


class ScanScreen(Screen):
    CSS = """
    #scan-box {
        align: center middle;
        width: 70;
        height: auto;
        padding: 2 4;
        border: round $primary;
    }
    #current-file { color: $text-muted; margin-bottom: 2; }
    #counters { margin-bottom: 1; }
    """

    def __init__(self, input_dir: Path, output_root: Path, model: str) -> None:
        super().__init__()
        self.input_dir = input_dir
        self.output_root = output_root
        self.model = model

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="scan-box"):
            yield Label("Starting…", id="current-file")
            yield Label("Scanned: 0  |  Classified: 0  |  Review: 0  |  Errors: 0", id="counters")
        yield Footer()

    def on_mount(self) -> None:
        self._run_scan()

    @work(thread=True)
    def _run_scan(self) -> None:
        import subprocess
        import sys
        import time
        import httpx

        rows: list = []
        counts = {"scanned": 0, "classified": 0, "review": 0, "errors": 0}

        def update_ui(current: str) -> None:
            self.app.call_from_thread(
                self.query_one("#current-file", Label).update,
                f"[dim]{current}[/dim]",
            )
            self.app.call_from_thread(
                self.query_one("#counters", Label).update,
                f"Scanned: {counts['scanned']}  |  "
                f"Classified: {counts['classified']}  |  "
                f"Review: {counts['review']}  |  "
                f"Errors: {counts['errors']}",
            )

        host = "http://127.0.0.1:11434"

        def reachable() -> bool:
            try:
                return httpx.get(f"{host}/api/tags", timeout=3).status_code == 200
            except Exception:
                return False

        if not reachable():
            self.app.call_from_thread(
                self.query_one("#current-file", Label).update,
                "Starting Ollama…",
            )
            started = False
            if sys.platform == "darwin":
                started = subprocess.run(["open", "-a", "Ollama"], capture_output=True).returncode == 0
            if not started:
                try:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    started = True
                except FileNotFoundError:
                    self.app.call_from_thread(
                        self.post_message,
                        ScanDone([], error="Ollama not found. Install from https://ollama.com"),
                    )
                    return

            for _ in range(40):
                time.sleep(0.5)
                if reachable():
                    break
            else:
                self.app.call_from_thread(
                    self.post_message,
                    ScanDone([], error="Ollama did not start in time. Run `ollama serve` manually."),
                )
                return

        try:
            from doc_cleaner.scanner import scan_files
            from doc_cleaner.extractors import extract_text
            from doc_cleaner.classifier.ollama import OllamaClient
            from doc_cleaner.classifier.prompts import build_prompt
            from doc_cleaner.classifier.schema import ClassificationResult, PlanRow
            from doc_cleaner.cache import ResultCache
            from doc_cleaner.planner import compute_target
            from doc_cleaner.taxonomy import load_taxonomy, normalize_category, REVIEW_CATEGORY
            from doc_cleaner.utils import sanitize_filename

            taxonomy_path = Path(__file__).parent / "taxonomy.yaml"
            if not taxonomy_path.exists():
                taxonomy_path = Path(__file__).parent.parent / "taxonomy.yaml"
            tax = load_taxonomy(taxonomy_path)
            cache = ResultCache(Path(".doc-cleaner-cache"))
            ollama = OllamaClient(host=host, model=self.model)
            existing_targets: set[Path] = set()

            for meta in scan_files(self.input_dir.resolve()):
                update_ui(str(meta.relative_path))
                counts["scanned"] += 1
                error_msg = ""
                extractor_name = "none"
                status = "error"
                cat = REVIEW_CATEGORY
                sub = None

                try:
                    cached = cache.get(meta.file_hash, self.model)
                    if cached:
                        classification = cached
                        extractor_name = "cached"
                    else:
                        extraction = extract_text(meta, max_chars=4000)
                        extractor_name = extraction.extractor
                        prompt = build_prompt(meta, extraction.text, tax)
                        classification = ollama.classify(prompt)
                        cache.set(meta.file_hash, self.model, classification)

                    cat, sub = normalize_category(classification.category, classification.subcategory, tax)
                    safe_name = sanitize_filename(
                        date=classification.document_date,
                        sender=classification.sender,
                        document_type=classification.document_type,
                        original_stem=meta.original_path.stem,
                        extension=meta.extension,
                    )
                    target = compute_target(self.output_root.resolve(), cat, sub, safe_name, existing_targets)
                    existing_targets.add(target)
                    status = "review" if classification.needs_review else "planned"
                    if classification.needs_review:
                        counts["review"] += 1
                    else:
                        counts["classified"] += 1

                except Exception as e:
                    error_msg = str(e)
                    extractor_name = "none"
                    counts["errors"] += 1
                    safe_name = meta.filename
                    classification = ClassificationResult(
                        category=REVIEW_CATEGORY,
                        suggested_filename=meta.filename,
                        confidence=0,
                        reason=f"Error: {error_msg}",
                        needs_review=True,
                    )
                    target = compute_target(self.output_root.resolve(), REVIEW_CATEGORY, None, safe_name, existing_targets)
                    existing_targets.add(target)

                rows.append(PlanRow(
                    approved=False,
                    status=status,
                    original_path=str(meta.original_path),
                    target_path=str(target),
                    category=cat,
                    subcategory=sub,
                    document_date=classification.document_date,
                    sender=classification.sender,
                    document_type=classification.document_type,
                    suggested_filename=safe_name,
                    confidence=classification.confidence,
                    needs_review=classification.needs_review,
                    reason=classification.reason,
                    file_size=meta.file_size,
                    file_hash=meta.file_hash,
                    modified_time=str(meta.modified_time),
                    extractor=extractor_name,
                    model=self.model,
                    error=error_msg,
                ))
                update_ui(str(meta.relative_path))

        except Exception as e:
            self.app.call_from_thread(self.post_message, ScanDone(rows, error=str(e)))
            return

        self.app.call_from_thread(self.post_message, ScanDone(rows))

    def on_scan_done(self, event: ScanDone) -> None:
        if event.error:
            self.notify(event.error, severity="error", timeout=10)
            self.app.pop_screen()
            return
        self.app.switch_screen(ReviewScreen(event.rows, self.input_dir, self.output_root))


class ReviewScreen(Screen):
    def __init__(self, rows: list, input_dir: Path, output_root: Path) -> None:
        super().__init__()
        self._rows = rows
        self.input_dir = input_dir
        self.output_root = output_root

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Review screen — coming in Task 5")
        yield Footer()


class DocCleanerApp(App):
    TITLE = "doc-cleaner"
    BINDINGS = [("q", "quit", "Quit"), ("ctrl+c", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(ConfigScreen())


def run() -> None:
    DocCleanerApp().run()
