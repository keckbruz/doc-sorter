from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path
import typer

app = typer.Typer(
    name="doc-sorter",
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
    taxonomy: Path | None = typer.Option(None, "--taxonomy"),
    limit: int | None = typer.Option(None, "--limit"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
    output_format: str = typer.Option("text", "--output-format", help="Output format: text or jsonl"),
) -> None:
    """Scan and classify documents. Writes a reviewable plan. Never moves files."""
    import json
    import time
    from datetime import datetime
    from rich.console import Console

    from doc_cleaner.scanner import scan_files
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.classifier.prompts import build_prompt
    from doc_cleaner.classifier.schema import ClassificationResult, PlanRow
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

    setup_logging(Path("/tmp/doc_sorter.log"), verbose=verbose)

    try:
        ollama = OllamaClient(
            host=ollama_host,
            model=model,
            allow_remote=allow_remote_ollama,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    counts = {"scanned": 0, "classified": 0, "review": 0, "errors": 0}
    existing_targets: set[Path] = set()
    debug_log_path = plan_path.with_suffix(".debug.jsonl")
    debug_log_path.parent.mkdir(parents=True, exist_ok=True)
    debug_log_path.write_text("")  # reset on each scan

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
            if not quiet and output_format != "jsonl":
                console.print(f"  [dim]{meta.relative_path}[/dim]", end="\r")

            error_msg = ""
            extractor_name = "none"
            extracted_text = ""
            classification: ClassificationResult | None = None
            cat = REVIEW_CATEGORY
            sub: str | None = None
            status = "error"

            try:
                extraction = extract_text(
                    meta,
                    max_chars=max_text_chars,
                    ocr=ocr,
                    ocr_language=ocr_language,
                )
                extractor_name = extraction.extractor
                extracted_text = extraction.text
                prompt = build_prompt(meta, extraction.text, tax)
                classification = ollama.classify(prompt)

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
                if output_format == "jsonl":
                    print(json.dumps({"event": "error", "message": str(e)}), flush=True)
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

            non_ws = len("".join(extracted_text.split()))
            debug_entry = {
                "file": meta.filename,
                "extractor": extractor_name,
                "text_chars": non_ws,
                "text_preview": extracted_text[:300].replace("\n", " "),
                "confidence": classification.confidence if classification else 0,
                "category": f"{cat}/{sub}" if sub else cat,
                "document_type": classification.document_type if classification else "",
                "reason": classification.reason if classification else "",
                "error": error_msg,
            }
            try:
                with open(debug_log_path, "a", encoding="utf-8") as dbf:
                    dbf.write(json.dumps(debug_entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

            if output_format == "jsonl":
                print(json.dumps({
                    "event": "progress",
                    "file": meta.filename,
                    "status": "classified" if status == "planned" else status,
                    "classified": counts["classified"],
                    "review": counts["review"],
                    "errors": counts["errors"],
                    "total": None,
                }), flush=True)

    if output_format == "jsonl":
        print(json.dumps({
            "event": "done",
            "plan": str(plan_path),
            "undo": None,
            "classified": counts["classified"],
            "review": counts["review"],
            "errors": counts["errors"],
        }), flush=True)

    elapsed = time.time() - start_time
    if not quiet:
        console.print()  # clear the \r line
        console.print(f"[bold green]Scan complete[/bold green] ({elapsed:.1f}s)")
        console.print(f"  Scanned:       {counts['scanned']}")
        console.print(f"  Classified:    {counts['classified']}")
        console.print(f"  Needs review:  {counts['review']}")
        console.print(f"  Errors:        {counts['errors']}")
        console.print(f"  Plan written to: {plan_path}")


@app.command("run")
def run_pipeline(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Root for sorted output"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    plan: Path | None = typer.Option(None, "--plan"),
    jsonl: Path | None = typer.Option(None, "--jsonl"),
    undo: Path | None = typer.Option(None, "--undo"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold", min=0, max=100),
    max_files: int | None = typer.Option(None, "--max-files"),
    max_depth: int | None = typer.Option(None, "--max-depth"),
    include_hidden: bool = typer.Option(False, "--include-hidden"),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
    ocr_language: str = typer.Option("deu+eng", "--ocr-language"),
    workers: int = typer.Option(1, "--workers"),
    max_text_chars: int = typer.Option(4000, "--max-text-chars"),
    taxonomy: Path | None = typer.Option(None, "--taxonomy"),
    limit: int | None = typer.Option(None, "--limit"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Required to move files without confirmation"),
) -> None:
    """Scan and apply confident matches in one non-interactive pipeline."""
    from datetime import datetime
    from rich.console import Console
    from doc_cleaner.applier import apply_plan

    console = Console()
    if not yes:
        console.print("[red]Refusing to move files without --yes.[/red]")
        console.print("Use `scan` for a plan-only run, or add `--yes` to run the full pipeline.")
        raise typer.Exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_path = plan or Path(f"plans/plan-{ts}.csv")
    jsonl_path = jsonl or Path(f"plans/plan-{ts}.jsonl")
    undo_path = undo or Path(f"plans/undo-{ts}.json")

    scan(
        input=input,
        output_root=output_root,
        model=model,
        ollama_host=ollama_host,
        allow_remote_ollama=allow_remote_ollama,
        plan=plan_path,
        jsonl=jsonl_path,
        dry_run=True,
        confidence_threshold=confidence_threshold,
        max_files=max_files,
        max_depth=max_depth,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
        ocr=ocr,
        ocr_language=ocr_language,
        workers=workers,
        max_text_chars=max_text_chars,
        taxonomy=taxonomy,
        limit=limit,
        verbose=verbose,
        quiet=quiet,
        output_format="text",
    )

    result = apply_plan(
        plan_path,
        undo_path,
        yes=True,
        apply_all_above_threshold=True,
        confidence_threshold=confidence_threshold,
    )

    if not quiet:
        console.print(f"\n[bold green]Pipeline complete[/bold green]")
        console.print(f"  Moved:         {result.moved}")
        console.print(f"  Skipped:       {result.skipped}")
        console.print(f"  Errors:        {len(result.errors)}")
        console.print(f"  Plan:          {plan_path}")
        console.print(f"  Undo manifest: {undo_path}")
        for err in result.errors:
            console.print(f"    [red]{err}[/red]")


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
def doctor(
    output_format: str = typer.Option("text", "--output-format", help="Output format: text or jsonl"),
) -> None:
    """Check system dependencies: Ollama, Tesseract, extractors, write permissions."""
    import json
    import sys
    import platform
    from rich.console import Console
    from rich.table import Table

    checks: list[dict] = []

    def add(name: str, status: str, detail: str, required: bool) -> None:
        checks.append({"event": "check", "name": name, "status": status, "detail": detail, "required": required})

    try:
        from doc_cleaner.classifier.ollama import OllamaClient
        client = OllamaClient()
        if client.check_health():
            models = client.list_models()
            add("Ollama", "ok", f"{len(models)} model(s) available", required=True)
        else:
            add("Ollama", "fail", "Not reachable — run: ollama serve", required=True)
    except Exception as e:
        add("Ollama", "fail", f"Error: {str(e)[:80]}", required=True)

    try:
        import pypdf  # noqa: F401
        add("pypdf", "ok", "PDF text extraction available", required=True)
    except ImportError:
        add("pypdf", "fail", "Not installed — run: pip install pypdf", required=True)

    try:
        import docx  # noqa: F401
        add("python-docx", "ok", "DOCX extraction available", required=False)
    except ImportError:
        add("python-docx", "warn", "Not installed — run: pip install python-docx", required=False)

    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        add("Tesseract", "ok", f"v{version} — image OCR available", required=False)
    except ImportError:
        add("Tesseract", "warn", "Not installed — run: pip install pytesseract && brew install tesseract tesseract-lang", required=False)
    except Exception:
        add("Tesseract", "warn", "Binary not found — run: brew install tesseract tesseract-lang", required=False)

    try:
        import ocrmypdf  # noqa: F401
        add("ocrmypdf", "ok", "PDF OCR embedding available", required=False)
    except ImportError:
        add("ocrmypdf", "warn", "Not installed — run: pip install ocrmypdf", required=False)

    if output_format == "jsonl":
        for check in checks:
            print(json.dumps(check), flush=True)
        return

    console = Console()
    table = Table(title="doc-sorter doctor", show_header=True)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    table.add_row("Python", "[green]OK[/green]", sys.version[:40])
    table.add_row("Platform", "[green]OK[/green]", platform.platform()[:40])

    status_map = {"ok": "[green]OK[/green]", "fail": "[red]FAIL[/red]", "warn": "[yellow]OPTIONAL[/yellow]"}
    for c in checks:
        table.add_row(c["name"], status_map.get(c["status"], c["status"]), c["detail"])

    console.print(table)


@app.command("suggest-taxonomy")
def suggest_taxonomy_cmd(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Output folder (used as existing taxonomy context)"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    max_text_chars: int = typer.Option(300, "--max-text-chars"),
    output_format: str = typer.Option("text", "--output-format", help="Output format: text or jsonl"),
    ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
    ocr_language: str = typer.Option("deu+eng", "--ocr-language"),
    embed_sparse: bool = typer.Option(False, "--embed-sparse/--no-embed-sparse",
                                      help="Embed OCR into scanned PDFs before peeking"),
    min_chars: int = typer.Option(50, "--min-chars", help="Char threshold below which a PDF is considered scanned"),
) -> None:
    """Suggest taxonomy additions for a folder of documents. Prints JSON to stdout."""
    import json
    from rich.console import Console
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.extractors.pdf import extract_pdf_text
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
        if output_format == "jsonl":
            print(json.dumps({"event": "taxonomy", "additions": {}}), flush=True)
        else:
            print(json.dumps({}))
        return

    # --- Optional: embed OCR into sparse PDFs before peeking ---
    if embed_sparse:
        try:
            import ocrmypdf
            pdf_meta = [m for m in all_meta if m.extension == ".pdf"]
            embed_total = len(pdf_meta)
            embed_done = 0
            for meta in pdf_meta:
                text, _, _ = extract_pdf_text(meta.original_path, max_chars=min_chars * 2)
                non_ws = len("".join(text.split()))
                if non_ws >= min_chars:
                    status = "skipped"
                else:
                    try:
                        ocrmypdf.ocr(
                            meta.original_path, meta.original_path,
                            language=ocr_language,
                            skip_text=True,
                            progress_bar=False,
                        )
                        status = "embedded"
                    except Exception as e:
                        status = "error"
                embed_done += 1
                if output_format == "jsonl":
                    print(json.dumps({
                        "event": "embed",
                        "file": meta.filename,
                        "status": status,
                        "done": embed_done,
                        "total": embed_total,
                    }), flush=True)
        except ImportError:
            if output_format == "jsonl":
                print(json.dumps({"event": "embed_unavailable"}), flush=True)

    total = len(all_meta)
    files: list[tuple[str, str]] = []
    for i, meta in enumerate(all_meta):
        try:
            result = extract_text(meta, max_chars=max_text_chars, ocr=ocr, ocr_language=ocr_language, rotation_retry=False)
            peek = result.text.strip()
        except Exception:
            peek = ""
        files.append((meta.filename, peek))
        if output_format == "jsonl":
            print(json.dumps({"event": "peek", "file": meta.filename, "done": i + 1, "total": total}), flush=True)

    base_tax_path = Path(__file__).parent.parent / "taxonomy.yaml"
    try:
        base_tax = load_taxonomy(base_tax_path)
    except FileNotFoundError:
        base_tax = {}
    folder_tax = read_output_taxonomy(resolved_output)
    existing = merge_taxonomies(base_tax, folder_tax)

    try:
        client = OllamaClient(host=ollama_host, model=model, allow_remote=allow_remote_ollama)
        additions = client.suggest_taxonomy(files, existing=existing)
    except Exception as e:
        console.print(f"[yellow]Warning: taxonomy suggestion failed ({e}), returning empty result[/yellow]")
        additions = {}

    if output_format == "jsonl":
        print(json.dumps({"event": "taxonomy", "additions": additions}), flush=True)
    else:
        print(json.dumps(additions, ensure_ascii=False))


@app.command("embed-ocr")
def embed_ocr(
    input: Path = typer.Option(..., "--input", "-i", help="Folder of PDFs to process"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output folder (default: overwrite in place)"),
    language: str = typer.Option("deu+eng", "--language", "-l"),
    workers: int = typer.Option(4, "--workers"),
    output_format: str = typer.Option("text", "--output-format"),
) -> None:
    """Add searchable OCR text layer to scanned PDFs using ocrmypdf. Skips PDFs that already have text."""
    import json
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    console = Console(stderr=True)

    try:
        import ocrmypdf
    except ImportError:
        console.print("[red]ocrmypdf not installed.[/red] Run: pip install ocrmypdf")
        raise typer.Exit(1)

    resolved_input = input.expanduser().resolve()
    resolved_output = output.expanduser().resolve() if output else None
    if resolved_output and resolved_output != resolved_input:
        resolved_output.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in resolved_input.rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        console.print("[yellow]No PDF files found.[/yellow]")
        return

    counts = {"done": 0, "skipped": 0, "errors": 0}
    total = len(pdfs)

    if output_format == "jsonl":
        print(json.dumps({"event": "start", "total": total}), flush=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        disable=output_format == "jsonl",
    ) as progress:
        task = progress.add_task("Embedding OCR…", total=total)

        for pdf in pdfs:
            dest = (resolved_output / pdf.relative_to(resolved_input)) if resolved_output else pdf
            dest.parent.mkdir(parents=True, exist_ok=True)
            progress.update(task, description=f"[dim]{pdf.name}[/dim]")

            try:
                result = ocrmypdf.ocr(
                    pdf,
                    dest,
                    language=language,
                    skip_text=True,
                    progress_bar=False,
                    jobs=workers,
                )
                if result == ocrmypdf.ExitCode.already_done_ocr:
                    counts["skipped"] += 1
                    status = "skipped"
                else:
                    counts["done"] += 1
                    status = "done"
            except Exception as e:
                counts["errors"] += 1
                status = "error"
                if output_format != "jsonl":
                    console.print(f"\n[red]Error:[/red] {pdf.name}: {e}")

            progress.advance(task)

            if output_format == "jsonl":
                print(json.dumps({
                    "event": "progress",
                    "file": pdf.name,
                    "status": status,
                    "done": counts["done"],
                    "skipped": counts["skipped"],
                    "errors": counts["errors"],
                    "total": total,
                }), flush=True)

    if output_format == "jsonl":
        print(json.dumps({"event": "done", **counts, "total": total}), flush=True)

    if output_format != "jsonl":
        console.print(f"\n[bold green]Done[/bold green]")
        console.print(f"  Embedded:  {counts['done']}")
        console.print(f"  Skipped:   {counts['skipped']} (already had text)")
        console.print(f"  Errors:    {counts['errors']}")
        if resolved_output:
            console.print(f"  Output:    {resolved_output}")


@app.command()
def ui() -> None:
    """Launch the simple interactive terminal workflow."""
    from doc_cleaner.interactive import run
    run()
