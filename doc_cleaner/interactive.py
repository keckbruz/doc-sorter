from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console


def default_plan_paths() -> tuple[Path, Path, Path]:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path.home() / ".doc-sorter" / "plans"
    return (
        base / f"plan-{ts}.csv",
        base / f"plan-{ts}.jsonl",
        base / f"undo-{ts}.json",
    )


def _arrow_select(title: str, options: list[tuple[str, str]]) -> str:
    """Full-screen arrow-navigable selection. Returns the key of the chosen option."""
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    cursor = [0]

    def render() -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = [("class:title", f"  {title}\n\n")]
        for i, (_, label) in enumerate(options):
            if i == cursor[0]:
                lines.append(("class:selected", f"  ▶ {label}\n"))
            else:
                lines.append(("class:item", f"    {label}\n"))
        lines.append(("class:hint", "\n  ↑↓ navigate   enter select\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        cursor[0] = max(0, cursor[0] - 1)

    @kb.add("down")
    def _down(event):
        cursor[0] = min(len(options) - 1, cursor[0] + 1)

    @kb.add("enter")
    def _enter(event):
        event.app.exit(result=options[cursor[0]][0])

    style = Style.from_dict({
        "title": "bold",
        "selected": "reverse",
        "item": "",
        "hint": "ansibrightblack italic",
    })

    layout = Layout(Window(content=FormattedTextControl(render)))
    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=True)
    return app.run()


def _path_prompt(label: str, default: str) -> Path:
    """Inline path prompt with directory tab-completion. Pre-fill ends with / to show contents immediately."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import PathCompleter
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("backspace")
    def _backspace(event):
        buf = event.current_buffer
        buf.delete_before_cursor()
        if buf.text.endswith("/") or not buf.text:
            buf.start_completion(select_first=False)

    session = PromptSession(
        completer=PathCompleter(only_directories=True, expanduser=True),
        complete_while_typing=True,
        key_bindings=kb,
    )
    value = session.prompt(f"{label}: ", default=default)
    return Path(value).expanduser().resolve()


def _model_prompt(default: str) -> str:
    """Inline model prompt with available Ollama models as completions."""
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter

    try:
        from doc_cleaner.classifier.ollama import OllamaClient
        models = OllamaClient().list_models()
    except Exception:
        models = []

    completer = WordCompleter(models, sentence=True) if models else None
    value = prompt(
        "Model: ",
        default=default,
        completer=completer,
        complete_while_typing=bool(models),
    )
    return value.strip() or default


def _threshold_prompt(default: int = 90) -> int:
    """Inline confidence threshold prompt."""
    from prompt_toolkit import prompt

    value = prompt("Confidence threshold: ", default=str(default))
    try:
        return max(0, min(100, int(value)))
    except ValueError:
        return default


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


def _suggest_taxonomy(
    input_dir: Path,
    model: str,
    console: Console,
    existing: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.scanner import scan_files

    all_meta = list(scan_files(input_dir, max_files=300))
    if not all_meta:
        return {}

    console.print(f"[dim]Peeking at {len(all_meta)} files to suggest taxonomy additions...[/dim]")
    files: list[tuple[str, str]] = []
    for meta in all_meta:
        try:
            result = extract_text(meta, max_chars=300, ocr=False)
            peek = result.text.strip()
        except Exception:
            peek = ""
        files.append((meta.filename, peek))

    try:
        client = OllamaClient(model=model)
        return client.suggest_taxonomy(files, existing=existing)
    except Exception:
        return {}


def scan_folder(console: Console) -> None:
    import yaml as _yaml
    from doc_cleaner.cli import scan
    from doc_cleaner.review_table import ReviewTableApp
    from doc_cleaner.taxonomy import load_taxonomy, merge_taxonomies, read_output_taxonomy

    cwd_slash = str(Path.cwd()) + "/"

    input_dir = _path_prompt("Scan folder", cwd_slash)
    while not input_dir.is_dir():
        console.print(f"[red]Not a directory:[/red] {input_dir}")
        input_dir = _path_prompt("Scan folder", str(input_dir.parent) + "/")

    output_root = _path_prompt("Output folder", cwd_slash)
    model = _model_prompt("qwen3.5:9b")
    threshold = _threshold_prompt(90)

    plan_path, jsonl_path, undo_path = default_plan_paths()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = Path.home() / ".doc-sorter" / "cache"

    # Build merged taxonomy: German base + existing output folder structure + LLM suggestion
    base_tax_path = Path(__file__).parent.parent / "taxonomy.yaml"
    base_tax = load_taxonomy(base_tax_path)
    resolved_output = output_root.expanduser().resolve()
    folder_tax = read_output_taxonomy(resolved_output)
    if folder_tax:
        console.print(
            f"[dim]Merging {len(folder_tax)} folder categories from output root.[/dim]"
        )
    existing_tax = merge_taxonomies(base_tax, folder_tax)
    suggested_tax = _suggest_taxonomy(input_dir, model, console, existing=existing_tax)
    if suggested_tax:
        from rich.tree import Tree
        tree = Tree("[bold]Suggested additions to taxonomy:[/bold]")
        for cat, subs in suggested_tax.items():
            branch = tree.add(f"[cyan]{cat}[/cyan]")
            for sub in subs:
                branch.add(sub)
        console.print(tree)
        if not typer.confirm("Add to taxonomy?", default=True):
            suggested_tax = {}
    merged_tax = merge_taxonomies(existing_tax, suggested_tax)
    tmp_tax_path = plan_path.parent / f"taxonomy-{plan_path.stem}.yaml"
    with open(tmp_tax_path, "w", encoding="utf-8") as _f:
        _yaml.dump(merged_tax, _f, allow_unicode=True, default_flow_style=False)

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
        cache_dir=cache_dir,
        taxonomy=tmp_tax_path,
        limit=None,
        verbose=False,
        quiet=False,
    )

    rows = _read_plan_as_review_rows(plan_path)
    if not rows:
        console.print("[yellow]No files to review.[/yellow]")
        return

    console.print(f"\n[bold]Opening review table[/bold] ({len(rows)} files) — press [bold]a[/bold] to apply, [bold]q[/bold] to quit without moving.\n")
    apply_cb = _make_apply_callback(plan_path, undo_path)
    applied = ReviewTableApp(rows, threshold=threshold, apply_callback=apply_cb).run()
    if applied:
        console.print(f"\n[green]Done.[/green] Undo manifest: {undo_path}")
    else:
        console.print("\n[yellow]No files moved.[/yellow] Run again or apply the plan manually.")


def apply_existing_plan(console: Console) -> None:
    from doc_cleaner.applier import apply_plan

    plan_path = prompt_existing_path(console, "Plan CSV")
    default_undo = Path.home() / ".doc-sorter" / "plans" / f"undo-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
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
    """Interactive workflow — goes straight to scan."""
    console = Console()
    scan_folder(console)
