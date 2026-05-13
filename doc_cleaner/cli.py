from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path
import typer

app = typer.Typer(
    name="doc-cleaner",
    help="Local document classifier and organizer. Privacy-preserving, dry-run by default.",
    no_args_is_help=True,
)


def _ensure_ollama(host: str, console: object) -> None:
    """Start Ollama if not reachable. Tries macOS app first, then `ollama serve`."""
    import httpx
    from rich.console import Console
    con = console  # type: ignore[assignment]

    def reachable() -> bool:
        try:
            return httpx.get(f"{host}/api/tags", timeout=3).status_code == 200
        except Exception:
            return False

    if reachable():
        return

    con.print("[yellow]Ollama is not running — starting it...[/yellow]")

    # Try macOS app first
    started = False
    if sys.platform == "darwin":
        result = subprocess.run(["open", "-a", "Ollama"], capture_output=True)
        started = result.returncode == 0

    # Fall back to `ollama serve` as background process
    if not started:
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            started = True
        except FileNotFoundError:
            con.print("[red]Could not find Ollama. Install it from https://ollama.com[/red]")
            raise typer.Exit(1)

    # Poll until ready (up to 20 seconds)
    with con.status("Waiting for Ollama to start..."):  # type: ignore[attr-defined]
        for _ in range(40):
            time.sleep(0.5)
            if reachable():
                con.print("[green]Ollama is ready.[/green]")
                return

    con.print("[red]Ollama did not start in time. Try running `ollama serve` manually.[/red]")
    raise typer.Exit(1)


@app.command()
def scan(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Root for sorted output"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    plan: Path | None = typer.Option(None, "--plan"),
    jsonl: Path | None = typer.Option(None, "--jsonl"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold", min=0, max=100),
    max_files: int | None = typer.Option(None, "--max-files"),
    max_depth: int | None = typer.Option(None, "--max-depth"),
    include_hidden: bool = typer.Option(False, "--include-hidden"),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
    ocr_language: str = typer.Option("deu+eng", "--ocr-language"),
    workers: int = typer.Option(1, "--workers"),
    max_text_chars: int = typer.Option(4000, "--max-text-chars"),
    cache_dir: Path | None = typer.Option(None, "--cache-dir"),
    taxonomy: Path | None = typer.Option(None, "--taxonomy"),
    limit: int | None = typer.Option(None, "--limit"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Scan and classify documents. Writes a reviewable plan. Never moves files."""
    import time
    from datetime import datetime
    from rich.console import Console

    from doc_cleaner.scanner import scan_files
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.classifier.prompts import build_prompt
    from doc_cleaner.classifier.schema import ClassificationResult, PlanRow
    from doc_cleaner.cache import ResultCache
    from doc_cleaner.planner import PlanWriter, compute_target
    from doc_cleaner.taxonomy import load_taxonomy, normalize_category, REVIEW_CATEGORY
    from doc_cleaner.utils import sanitize_filename
    from doc_cleaner.logging import setup_logging

    console = Console(stderr=True)
    start_time = time.time()

    _ensure_ollama(ollama_host, console)

    # Resolve taxonomy path
    taxonomy_path = taxonomy or (Path(__file__).parent.parent / "taxonomy.yaml")
    try:
        tax = load_taxonomy(taxonomy_path)
    except FileNotFoundError as e:
        console.print(f"[red]Taxonomy file not found:[/red] {e}")
        raise typer.Exit(1)

    # Resolve plan paths
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_path = plan or Path(f"plans/plan-{ts}.csv")
    jsonl_path = jsonl or Path(f"plans/plan-{ts}.jsonl")

    # Cache dir
    cache_path = cache_dir or Path(".doc-cleaner-cache")

    setup_logging(Path("doc_cleaner.log"), verbose=verbose)

    try:
        ollama = OllamaClient(
            host=ollama_host,
            model=model,
            allow_remote=allow_remote_ollama,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    cache = ResultCache(cache_path)

    counts = {"scanned": 0, "classified": 0, "review": 0, "errors": 0, "cached": 0}
    existing_targets: set[Path] = set()

    # effective file limit (--limit takes precedence over --max-files for usability)
    effective_limit = limit if limit is not None else max_files

    with PlanWriter(plan_path, jsonl_path) as writer:
        for meta in scan_files(
            input.expanduser().resolve(),
            max_depth=max_depth,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
            max_files=effective_limit,
        ):
            counts["scanned"] += 1
            if not quiet:
                console.print(f"  [dim]{meta.relative_path}[/dim]", end="\r")

            error_msg = ""
            extractor_name = "none"
            classification: ClassificationResult | None = None
            cat = REVIEW_CATEGORY
            sub: str | None = None
            status = "error"

            try:
                # Cache check
                cached = cache.get(meta.file_hash, model)
                if cached:
                    classification = cached
                    extractor_name = "cached"
                    counts["cached"] += 1
                else:
                    extraction = extract_text(
                        meta,
                        max_chars=max_text_chars,
                        ocr=ocr,
                        ocr_language=ocr_language,
                    )
                    extractor_name = extraction.extractor
                    prompt = build_prompt(meta, extraction.text, tax)
                    classification = ollama.classify(prompt)
                    cache.set(meta.file_hash, model, classification)

                # Force needs_review if below confidence threshold
                if classification.confidence < confidence_threshold:
                    classification = classification.model_copy(update={"needs_review": True})

                # Normalize category to taxonomy
                cat, sub = normalize_category(classification.category, classification.subcategory, tax)

                # Build safe filename
                safe_name = sanitize_filename(
                    date=classification.document_date,
                    sender=classification.sender,
                    document_type=classification.document_type,
                    original_stem=meta.original_path.stem,
                    extension=meta.extension,
                )

                target = compute_target(
                    output_root.expanduser().resolve(),
                    cat,
                    sub,
                    safe_name,
                    existing_targets,
                )

                status = "review" if classification.needs_review else "planned"
                if classification.needs_review:
                    counts["review"] += 1
                else:
                    counts["classified"] += 1

            except ConnectionError as e:
                console.print(f"\n[red]{e}[/red]")
                raise typer.Exit(1)
            except Exception as e:
                error_msg = str(e)
                counts["errors"] += 1
                cat = REVIEW_CATEGORY
                sub = None
                safe_name = meta.filename
                target = compute_target(
                    output_root.expanduser().resolve(),
                    cat,
                    sub,
                    safe_name,
                    existing_targets,
                )
                status = "error"
                classification = ClassificationResult(
                    category=REVIEW_CATEGORY,
                    suggested_filename=meta.filename,
                    confidence=0,
                    reason=f"Error during processing: {error_msg}",
                    needs_review=True,
                )

            writer.write(PlanRow(
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
                model=model,
                error=error_msg,
            ))

    elapsed = time.time() - start_time
    if not quiet:
        console.print()  # clear the \r line
        console.print(f"[bold green]Scan complete[/bold green] ({elapsed:.1f}s)")
        console.print(f"  Scanned:       {counts['scanned']}")
        console.print(f"  Classified:    {counts['classified']}")
        console.print(f"  Needs review:  {counts['review']}")
        console.print(f"  Errors:        {counts['errors']}")
        console.print(f"  Cached:        {counts['cached']}")
        console.print(f"  Plan written to: {plan_path}")
        console.print()
        console.print("[yellow]No files were moved.[/yellow] Review the plan, then run apply.")


@app.command()
def apply(
    plan: Path = typer.Option(..., "--plan", help="Reviewed plan CSV"),
    undo: Path = typer.Option(..., "--undo", help="Path for undo manifest JSON"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    apply_all_above_threshold: bool = typer.Option(False, "--apply-all-above-threshold"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold", min=0, max=100),
) -> None:
    """Apply an approved move plan."""
    from rich.console import Console
    from doc_cleaner.applier import apply_plan

    console = Console()
    result = apply_plan(plan, undo, yes=yes,
                        apply_all_above_threshold=apply_all_above_threshold,
                        confidence_threshold=confidence_threshold)

    console.print(f"\n[bold green]Apply complete[/bold green]")
    console.print(f"  Moved:   {result.moved}")
    console.print(f"  Skipped: {result.skipped}")
    if result.errors:
        console.print(f"  Errors:  {len(result.errors)}")
        for err in result.errors:
            console.print(f"    [red]{err}[/red]")
    console.print(f"  Undo manifest: {undo}")


@app.command()
def undo(
    undo_manifest: Path = typer.Option(..., "--undo-manifest"),
) -> None:
    """Undo a previous apply run."""
    from rich.console import Console
    from doc_cleaner.undo import undo_moves

    console = Console()
    result = undo_moves(undo_manifest)

    console.print(f"[bold green]Undo complete[/bold green]")
    console.print(f"  Restored: {result.restored}")
    console.print(f"  Skipped:  {result.skipped}")
    for conflict in result.conflicts:
        console.print(f"  [yellow]Conflict:[/yellow] {conflict}")


@app.command()
def doctor() -> None:
    """Check system dependencies: Ollama, Tesseract, extractors, write permissions."""
    import sys
    import platform
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="doc-cleaner doctor", show_header=True)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    py = sys.version
    table.add_row("Python", "[green]OK[/green]", py[:20])

    table.add_row("Platform", "[green]OK[/green]", platform.platform()[:40])

    try:
        from doc_cleaner.classifier.ollama import OllamaClient
        client = OllamaClient()
        if client.check_health():
            models = client.list_models()
            table.add_row("Ollama", "[green]OK[/green]", f"{len(models)} models")
        else:
            table.add_row("Ollama", "[red]FAIL[/red]", "Not reachable — run: ollama serve")
    except Exception as e:
        table.add_row("Ollama", "[red]FAIL[/red]", str(e)[:60])

    try:
        import pypdf  # noqa: F401
        table.add_row("pypdf", "[green]OK[/green]", "PDF extraction available")
    except ImportError:
        table.add_row("pypdf", "[red]MISSING[/red]", "pip install pypdf")

    try:
        import docx  # noqa: F401
        table.add_row("python-docx", "[green]OK[/green]", "DOCX extraction available")
    except ImportError:
        table.add_row("python-docx", "[red]MISSING[/red]", "pip install python-docx")

    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        table.add_row("Tesseract", "[green]OK[/green]", f"v{version} — OCR available")
    except ImportError:
        table.add_row("Tesseract", "[yellow]OPTIONAL[/yellow]", "pip install pytesseract (then install Tesseract binary)")
    except Exception as e:
        table.add_row("Tesseract", "[yellow]OPTIONAL[/yellow]", f"Not found: {e}")

    console.print(table)


@app.command()
def ui() -> None:
    """Launch the interactive TUI."""
    from doc_cleaner.tui import run
    run()
