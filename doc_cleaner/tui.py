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
    def __init__(self, input_dir: Path, output_root: Path, model: str) -> None:
        super().__init__()
        self.input_dir = input_dir
        self.output_root = output_root
        self.model = model

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Scan screen — coming in Task 4")
        yield Footer()


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
