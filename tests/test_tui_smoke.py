from pathlib import Path
from doc_cleaner.tui import ConfigScreen, DocCleanerApp


def test_config_screen_instantiates():
    screen = ConfigScreen()
    assert screen is not None


def test_app_instantiates():
    app = DocCleanerApp()
    assert app is not None
