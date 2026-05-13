from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer

app = typer.Typer(
    name="doc-cleaner",
    help="Local document classifier and organizer. Privacy-preserving, dry-run by default.",
    no_args_is_help=True,
)


@app.command()
def scan(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Root for sorted output"),
    model: str = typer.Option("qwen3.5:9b", "--model"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    plan: Optional[Path] = typer.Option(None, "--plan"),
    jsonl: Optional[Path] = typer.Option(None, "--jsonl"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold"),
    max_files: Optional[int] = typer.Option(None, "--max-files"),
    max_depth: Optional[int] = typer.Option(None, "--max-depth"),
    include_hidden: bool = typer.Option(False, "--include-hidden"),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
    ocr_language: str = typer.Option("deu+eng", "--ocr-language"),
    workers: int = typer.Option(1, "--workers"),
    max_text_chars: int = typer.Option(4000, "--max-text-chars"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    taxonomy: Optional[Path] = typer.Option(None, "--taxonomy"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    verbose: bool = typer.Option(False, "--verbose"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Scan and classify documents. Writes a reviewable plan. Never moves files."""
    typer.echo("scan: not yet implemented")
    raise typer.Exit(1)


@app.command()
def apply(
    plan: Path = typer.Option(..., "--plan", help="Reviewed plan CSV"),
    undo: Path = typer.Option(..., "--undo", help="Path for undo manifest JSON"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    apply_all_above_threshold: bool = typer.Option(False, "--apply-all-above-threshold"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold"),
) -> None:
    """Apply an approved move plan."""
    typer.echo("apply: not yet implemented")
    raise typer.Exit(1)


@app.command()
def undo(
    undo_manifest: Path = typer.Option(..., "--undo-manifest"),
) -> None:
    """Undo a previous apply run."""
    typer.echo("undo: not yet implemented")
    raise typer.Exit(1)


@app.command()
def doctor() -> None:
    """Check system dependencies: Ollama, Tesseract, extractors."""
    typer.echo("doctor: not yet implemented")
    raise typer.Exit(1)
