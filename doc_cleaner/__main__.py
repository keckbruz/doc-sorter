import sys


def main() -> None:
    if len(sys.argv) == 1:
        from doc_cleaner.interactive import run
        run()
    else:
        from doc_cleaner.cli import app
        app()


if __name__ == "__main__":
    main()
