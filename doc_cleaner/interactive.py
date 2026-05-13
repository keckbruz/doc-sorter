from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console


def default_plan_paths() -> tuple[Path, Path, Path]:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (
        Path(f"plans/plan-{ts}.csv"),
        Path(f"plans/plan-{ts}.jsonl"),
        Path(f"plans/undo-{ts}.json"),
    )


def select(console: Console, title: str, options: list[tuple[str, str]]) -> str:
    console.print(f"[bold]{title}[/bold]")
    for index, (_, label) in enumerate(options, start=1):
        console.print(f"  {index}. {label}")

    while True:
        value = typer.prompt("Select", default=1)
        try:
            index = int(value)
        except ValueError:
            console.print("[red]Enter a number from the list.[/red]")
            continue

        if 1 <= index <= len(options):
            return options[index - 1][0]
        console.print("[red]Enter a number from the list.[/red]")


def prompt_existing_path(console: Console, label: str) -> Path:
    while True:
        path = Path(typer.prompt(label)).expanduser()
        if path.exists():
            return path
        console.print(f"[red]Not found:[/red] {path}")


def print_apply_result(console: Console, result: object, undo_path: Path) -> None:
    console.print()
    console.print("[bold green]Apply complete[/bold green]")
    console.print(f"  Moved:   {result.moved}")  # type: ignore[attr-defined]
    console.print(f"  Skipped: {result.skipped}")  # type: ignore[attr-defined]
    if result.errors:  # type: ignore[attr-defined]
        console.print(f"  Errors:  {len(result.errors)}")  # type: ignore[attr-defined]
        for error in result.errors:  # type: ignore[attr-defined]
            console.print(f"    [red]{error}[/red]")
    console.print(f"  Undo manifest: {undo_path}")


def _read_plan_as_review_rows(plan_csv: Path) -> list:
    import csv as _csv
    from doc_cleaner.review_table import ReviewRow
    rows = []
    with open(plan_csv, newline="", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            cat = row["category"]
            if row.get("subcategory"):
                cat = f"{cat}/{row['subcategory']}"
            try:
                confidence = int(row["confidence"] or 0)
            except ValueError:
                confidence = 0
            orig_path = Path(row["original_path"])
            rows.append(ReviewRow(
                original_path=orig_path,
                original_name=orig_path.name,
                target_path=Path(row["target_path"]),
                new_name=row["suggested_filename"],
                category=cat,
                confidence=confidence,
                needs_review=row["needs_review"].lower() == "true",
            ))
    return rows


def _make_apply_callback(plan_csv: Path, undo_path: Path):
    import csv as _csv
    import os as _os

    def apply(rows: list) -> None:
        from doc_cleaner.applier import apply_plan  # inside closure for test patchability

        approved = {str(r.original_path): r for r in rows}

        rows_data = []
        with open(plan_csv, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            for row_data in reader:
                path = row_data["original_path"]
                if path in approved:
                    row_data["approved"] = "true"
                    review_row = approved[path]
                    if review_row.user_edited:
                        row_data["target_path"] = str(review_row.target_path)
                        row_data["suggested_filename"] = review_row.new_name
                rows_data.append(row_data)

        tmp = plan_csv.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_data)
        _os.replace(tmp, plan_csv)

        apply_plan(
            plan_csv, undo_path,
            yes=True,
            apply_all_above_threshold=False,
            confidence_threshold=0,
        )

    return apply


def scan_folder(console: Console) -> None:
    from doc_cleaner.cli import scan
    from doc_cleaner.review_table import ReviewTableApp

    input_dir = Path(typer.prompt("Folder to scan", default=str(Path.cwd()))).expanduser()
    while not input_dir.is_dir():
        console.print(f"[red]Folder not found:[/red] {input_dir}")
        input_dir = Path(typer.prompt("Folder to scan", default=str(Path.cwd()))).expanduser()

    output_root = Path(typer.prompt("Sorted output folder")).expanduser()
    model = typer.prompt("Ollama model", default="qwen3.5:9b")
    threshold = typer.prompt("Confidence threshold", default=90, type=int)

    plan_path, jsonl_path, undo_path = default_plan_paths()
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    console.print()
    scan(
        input=input_dir,
        output_root=output_root,
        model=model,
        ollama_host="http://127.0.0.1:11434",
        allow_remote_ollama=False,
        plan=plan_path,
        jsonl=jsonl_path,
        dry_run=True,
        confidence_threshold=threshold,
        max_files=None,
        max_depth=None,
        include_hidden=False,
        follow_symlinks=False,
        ocr=False,
        ocr_language="deu+eng",
        workers=1,
        max_text_chars=4000,
        cache_dir=None,
        taxonomy=None,
        limit=None,
        verbose=False,
        quiet=False,
    )

    rows = _read_plan_as_review_rows(plan_path)
    if not rows:
        console.print("[yellow]No files to review.[/yellow]")
        return

    apply_cb = _make_apply_callback(plan_path, undo_path)
    ReviewTableApp(rows, threshold=threshold, apply_callback=apply_cb).run()

    console.print(f"\n[green]Done.[/green] Undo manifest: {undo_path}")


def apply_existing_plan(console: Console) -> None:
    from doc_cleaner.applier import apply_plan

    plan_path = prompt_existing_path(console, "Plan CSV")
    default_undo = Path(f"plans/undo-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    undo_path = Path(typer.prompt("Undo manifest", default=str(default_undo))).expanduser()
    threshold = typer.prompt("Confidence threshold", default=90, type=int)

    mode = select(
        console,
        "Apply mode",
        [
            ("approved", "Apply only rows marked approved=true."),
            ("confident", f"Apply approved rows plus confidence >= {threshold}."),
        ],
    )
    result = apply_plan(
        plan_path,
        undo_path,
        yes=False,
        apply_all_above_threshold=mode == "confident",
        confidence_threshold=threshold,
    )
    print_apply_result(console, result, undo_path)


def undo_previous_apply(console: Console) -> None:
    from doc_cleaner.undo import undo_moves

    undo_path = prompt_existing_path(console, "Undo manifest JSON")
    result = undo_moves(undo_path)
    console.print()
    console.print("[bold green]Undo complete[/bold green]")
    console.print(f"  Restored: {result.restored}")
    console.print(f"  Skipped:  {result.skipped}")
    for conflict in result.conflicts:
        console.print(f"  [yellow]Conflict:[/yellow] {conflict}")


def run() -> None:
    """Run a simple terminal-first workflow without a full-screen TUI."""
    from doc_cleaner.cli import doctor

    console = Console()
    console.print("[bold]doc-sorter[/bold]")
    console.print("Use arrow-free terminal prompts: type a number, press Enter.")
    console.print()

    while True:
        action = select(
            console,
            "What do you want to do?",
            [
                ("scan", "Scan a folder and create a plan."),
                ("apply", "Apply an existing reviewed plan."),
                ("undo", "Undo a previous apply."),
                ("doctor", "Check local setup."),
                ("quit", "Quit."),
            ],
        )
        console.print()

        if action == "scan":
            scan_folder(console)
        elif action == "apply":
            apply_existing_plan(console)
        elif action == "undo":
            undo_previous_apply(console)
        elif action == "doctor":
            doctor()
        else:
            return

        console.print()
