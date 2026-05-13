import sys


def main() -> None:
    if len(sys.argv) == 1:
        from doc_cleaner.tui import run
        run()
    else:
        from doc_cleaner.cli import app
        app()


main()
