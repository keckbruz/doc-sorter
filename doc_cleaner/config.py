from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    input_dir: Path = field(default_factory=lambda: Path("."))
    output_root: Path = field(default_factory=lambda: Path("~/Documents/Sorted"))
    model: str = "qwen3.5:9b"
    ollama_host: str = "http://127.0.0.1:11434"
    allow_remote_ollama: bool = False
    plan_path: Path | None = None
    jsonl_path: Path | None = None
    dry_run: bool = True
    confidence_threshold: int = 90
    max_files: int | None = None
    max_depth: int | None = None
    include_hidden: bool = False
    follow_symlinks: bool = False
    ocr: bool = False
    ocr_language: str = "deu+eng"
    workers: int = 1
    max_text_chars: int = 4000
    cache_dir: Path | None = None
    taxonomy_path: Path | None = None
    limit: int | None = None
    verbose: bool = False
    quiet: bool = False
