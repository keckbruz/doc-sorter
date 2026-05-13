from __future__ import annotations
from pathlib import Path

from textual.app import App, ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Label


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
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Config screen — coming in Task 3")
        yield Footer()


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
