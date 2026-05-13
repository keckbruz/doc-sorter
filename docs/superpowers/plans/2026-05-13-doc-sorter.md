# doc-sorter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first, privacy-preserving Python CLI that classifies documents via local Ollama, generates a reviewable CSV/JSONL plan, and applies moves with full undo support — no cloud, no deletion, dry-run by default.

**Architecture:** Single-pass pipeline — `scan` collects file metadata, extracts text locally, calls local Ollama per file, and streams results to CSV/JSONL. `apply` reads an approved plan and moves files. `undo` reverses moves using a JSON manifest. All state in flat files — no database.

**Tech Stack:** Python 3.11+, typer[all], pydantic v2, rich, httpx, pypdf, python-docx, pillow, python-magic, pytest, fpdf2 (dev only)

---

## File Map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Package config + dependencies |
| `doc_cleaner/__init__.py` | Version string `__version__ = "0.1.0"` |
| `doc_cleaner/__main__.py` | `python -m doc_cleaner` entry point |
| `doc_cleaner/cli.py` | typer app, 4 commands (scan / apply / undo / doctor) |
| `doc_cleaner/config.py` | `Config` dataclass with all CLI options and defaults |
| `doc_cleaner/taxonomy.py` | `load_taxonomy()`, `is_valid_category()`, `REVIEW_CATEGORY` constant |
| `doc_cleaner/scanner.py` | `FileMetadata` dataclass, `scan_files()` generator, skip rules, SHA-256 |
| `doc_cleaner/utils.py` | `sanitize_filename()`, `safe_target_path()`, `safe_move()` |
| `doc_cleaner/logging.py` | `setup_logging()`, local file + stderr |
| `doc_cleaner/extractors/__init__.py` | `extract_text(meta)` dispatcher → `ExtractionResult` |
| `doc_cleaner/extractors/text.py` | `.txt`, `.md`, `.csv` summary |
| `doc_cleaner/extractors/pdf.py` | pypdf text extraction |
| `doc_cleaner/extractors/docx.py` | python-docx extraction |
| `doc_cleaner/extractors/image_ocr.py` | pytesseract (soft dep, graceful degradation) |
| `doc_cleaner/classifier/__init__.py` | Empty |
| `doc_cleaner/classifier/schema.py` | `ClassificationResult`, `PlanRow`, `UndoEntry`, `UndoManifest` Pydantic models |
| `doc_cleaner/classifier/prompts.py` | `build_prompt()`, `select_excerpt()`, `PROMPT_VERSION` |
| `doc_cleaner/classifier/ollama.py` | `OllamaClient` — sole network module, localhost guard |
| `doc_cleaner/cache.py` | `ResultCache` keyed by file_hash + model + PROMPT_VERSION |
| `doc_cleaner/planner.py` | `compute_target()`, collision handling, `PlanWriter` (CSV + JSONL) |
| `doc_cleaner/applier.py` | `apply_plan()`, safe moves, undo manifest + shell script |
| `doc_cleaner/undo.py` | `undo_moves()` |
| `tests/conftest.py` | `tmp_path` fixtures, fake doc content, `mock_ollama_response` fixture |
| `tests/test_taxonomy.py` | Taxonomy loading + category validation |
| `tests/test_filename_sanitize.py` | Filename sanitization rules |
| `tests/test_schema.py` | ClassificationResult validation |
| `tests/test_scanner.py` | File walk, skip rules, metadata extraction |
| `tests/test_planner.py` | Target path generation, collisions, path traversal guard |
| `tests/test_apply_no_overwrite.py` | Apply safety: no overwrite, undo manifest written, approved=false skipped |
| `test_docs/generate_test_docs.py` | Generate fake PDF/DOCX/TXT document tree for e2e testing |
| `taxonomy.yaml` | Default category taxonomy |

---

## Core Types Reference

These types are used across multiple tasks. Refer back here for signatures.

```python
# scanner.py
@dataclass
class FileMetadata:
    original_path: Path
    relative_path: Path
    filename: str
    extension: str        # lowercase with dot, e.g. ".pdf"
    file_size: int        # bytes
    created_time: float | None
    modified_time: float
    mime_type: str
    file_hash: str        # SHA-256 hex

# extractors/__init__.py
@dataclass
class ExtractionResult:
    text: str
    extractor: str        # "pdf" | "docx" | "text" | "image_ocr" | "none" | "ocr_unavailable"
    error: str | None = None

# classifier/schema.py
class ClassificationResult(BaseModel):
    category: str
    subcategory: str | None = None
    document_date: str | None = None
    sender: str | None = None
    document_type: str | None = None
    suggested_filename: str
    confidence: int         # 0–100
    reason: str
    needs_review: bool

class PlanRow(BaseModel):
    approved: bool = False
    status: str             # "planned" | "review" | "error" | "skipped"
    original_path: str
    target_path: str
    category: str
    subcategory: str | None = None
    document_date: str | None = None
    sender: str | None = None
    document_type: str | None = None
    suggested_filename: str
    confidence: int
    needs_review: bool
    reason: str
    file_size: int
    file_hash: str
    modified_time: str      # ISO datetime string
    extractor: str
    model: str
    error: str = ""

class UndoEntry(BaseModel):
    original_path: str
    applied_path: str
    file_hash: str
    moved_at: str           # ISO datetime

class UndoManifest(BaseModel):
    created_at: str
    entries: list[UndoEntry]
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `taxonomy.yaml`
- Create: `doc_cleaner/__init__.py`
- Create: `doc_cleaner/__main__.py`
- Create: `doc_cleaner/cli.py`
- Create: `doc_cleaner/config.py` (stub — `pass` body, filled in Task 3)
- Create: `doc_cleaner/taxonomy.py` (stub)
- Create: `doc_cleaner/scanner.py` (stub)
- Create: `doc_cleaner/utils.py` (stub)
- Create: `doc_cleaner/logging.py` (stub)
- Create: `doc_cleaner/planner.py` (stub)
- Create: `doc_cleaner/applier.py` (stub)
- Create: `doc_cleaner/undo.py` (stub)
- Create: `doc_cleaner/cache.py` (stub)
- Create: `doc_cleaner/extractors/__init__.py` (stub)
- Create: `doc_cleaner/extractors/text.py` (stub)
- Create: `doc_cleaner/extractors/pdf.py` (stub)
- Create: `doc_cleaner/extractors/docx.py` (stub)
- Create: `doc_cleaner/extractors/image_ocr.py` (stub)
- Create: `doc_cleaner/classifier/__init__.py` (empty)
- Create: `doc_cleaner/classifier/schema.py` (stub)
- Create: `doc_cleaner/classifier/prompts.py` (stub)
- Create: `doc_cleaner/classifier/ollama.py` (stub)
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py` (stub)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "doc-cleaner"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer[all]>=0.9",
    "pydantic>=2",
    "rich>=13",
    "httpx>=0.27",
    "pypdf>=4",
    "python-docx>=1",
    "pillow>=10",
    "python-magic>=0.4",
]

[project.optional-dependencies]
ocr = ["pytesseract"]
dev = ["pytest>=8", "fpdf2>=2.7", "pytest-mock>=3"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `taxonomy.yaml`**

```yaml
Finance:
  - Banking
  - Taxes
  - Insurance
  - Investments
  - Invoices
  - Receipts
Legal:
  - Contracts
  - Government
  - Court
  - Other
Work:
  - Employment
  - Projects
  - Applications
  - Other
Education:
  - University
  - Certificates
  - Courses
  - Other
Health:
  - Bills
  - Reports
  - Insurance
  - Other
Household:
  - Rent
  - Utilities
  - Internet
  - Manuals
  - Other
Vehicles:
  - Insurance
  - Maintenance
  - Registration
  - Other
Personal:
  - Letters
  - Travel
  - Identity
  - Other
Media:
  - Photos
  - Screenshots
  - Videos
Software:
  - Licenses
  - Manuals
Archive: []
Review: []
Duplicates: []
```

- [ ] **Step 3: Write package init and entry point**

`doc_cleaner/__init__.py`:
```python
__version__ = "0.1.0"
```

`doc_cleaner/__main__.py`:
```python
from doc_cleaner.cli import app

app()
```

- [ ] **Step 4: Write CLI skeleton with all 4 commands**

`doc_cleaner/cli.py`:
```python
from __future__ import annotations
from pathlib import Path
import typer
from typing import Optional

app = typer.Typer(
    name="doc-cleaner",
    help="Local document classifier and organizer. Privacy-preserving, dry-run by default.",
    no_args_is_help=True,
)


@app.command()
def scan(
    input: Path = typer.Option(..., "--input", "-i", help="Folder to scan"),
    output_root: Path = typer.Option(..., "--output-root", help="Root for sorted output"),
    model: str = typer.Option("qwen3.5:9b", "--model", help="Ollama model name"),
    ollama_host: str = typer.Option("http://127.0.0.1:11434", "--ollama-host"),
    allow_remote_ollama: bool = typer.Option(False, "--allow-remote-ollama"),
    plan: Optional[Path] = typer.Option(None, "--plan", help="Output CSV plan path"),
    jsonl: Optional[Path] = typer.Option(None, "--jsonl", help="Output JSONL plan path"),
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
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    apply_all_above_threshold: bool = typer.Option(False, "--apply-all-above-threshold"),
) -> None:
    """Apply an approved move plan."""
    typer.echo("apply: not yet implemented")
    raise typer.Exit(1)


@app.command()
def undo(
    undo_manifest: Path = typer.Option(..., "--undo-manifest", help="Undo manifest JSON"),
) -> None:
    """Undo a previous apply run."""
    typer.echo("undo: not yet implemented")
    raise typer.Exit(1)


@app.command()
def doctor() -> None:
    """Check system dependencies: Ollama, Tesseract, extractors."""
    typer.echo("doctor: not yet implemented")
    raise typer.Exit(1)
```

- [ ] **Step 5: Install the package and verify --help works**

```bash
pip install -e ".[dev]"
python -m doc_cleaner --help
```

Expected output includes: `scan`, `apply`, `undo`, `doctor` listed as commands.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml taxonomy.yaml doc_cleaner/ tests/
git commit -m "feat: project scaffold with CLI skeleton"
```

---

## Task 2: taxonomy.py + test_taxonomy.py

**Files:**
- Create: `doc_cleaner/taxonomy.py`
- Create: `tests/test_taxonomy.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_taxonomy.py`:
```python
from pathlib import Path
import pytest
from doc_cleaner.taxonomy import load_taxonomy, is_valid_category, normalize_category, REVIEW_CATEGORY

TAXONOMY_PATH = Path(__file__).parent.parent / "taxonomy.yaml"


def test_load_taxonomy_returns_dict():
    t = load_taxonomy(TAXONOMY_PATH)
    assert isinstance(t, dict)
    assert "Finance" in t
    assert "Review" in t


def test_finance_subcategories():
    t = load_taxonomy(TAXONOMY_PATH)
    assert "Banking" in t["Finance"]
    assert "Insurance" in t["Finance"]


def test_review_is_always_valid():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Review", None, t) is True


def test_valid_category_with_subcategory():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finance", "Banking", t) is True


def test_invalid_category_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("CloudStorage", None, t) is False


def test_invalid_subcategory_rejected():
    t = load_taxonomy(TAXONOMY_PATH)
    assert is_valid_category("Finance", "Crypto", t) is False


def test_normalize_unknown_category_returns_review():
    t = load_taxonomy(TAXONOMY_PATH)
    cat, sub = normalize_category("WeirdCategory", None, t)
    assert cat == REVIEW_CATEGORY


def test_review_constant():
    assert REVIEW_CATEGORY == "Review"


def test_load_taxonomy_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_taxonomy(Path("/nonexistent/taxonomy.yaml"))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_taxonomy.py -v
```

Expected: FAIL with `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Implement `doc_cleaner/taxonomy.py`**

```python
from __future__ import annotations
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

REVIEW_CATEGORY = "Review"

# Dict[category_name -> list[subcategory_names]]
Taxonomy = dict[str, list[str]]


def load_taxonomy(path: Path) -> Taxonomy:
    if not path.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Taxonomy file must be a YAML mapping: {path}")
    # Normalize: values may be None (empty list in YAML) or a list
    return {k: (v or []) for k, v in raw.items()}


def is_valid_category(category: str, subcategory: str | None, taxonomy: Taxonomy) -> bool:
    if category not in taxonomy:
        return False
    if subcategory is None:
        return True
    subs = taxonomy[category]
    return not subs or subcategory in subs


def normalize_category(
    category: str, subcategory: str | None, taxonomy: Taxonomy
) -> tuple[str, str | None]:
    """Return (category, subcategory) forced to valid values, or Review if invalid."""
    if not is_valid_category(category, subcategory, taxonomy):
        return REVIEW_CATEGORY, None
    return category, subcategory
```

Note: Add `pyyaml` to `pyproject.toml` dependencies:
```toml
"pyyaml>=6",
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_taxonomy.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/taxonomy.py tests/test_taxonomy.py pyproject.toml
git commit -m "feat: taxonomy loading and category validation"
```

---

## Task 3: config.py + utils.py + test_filename_sanitize.py

**Files:**
- Create: `doc_cleaner/config.py`
- Create: `doc_cleaner/utils.py`
- Create: `tests/test_filename_sanitize.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_filename_sanitize.py`:
```python
from pathlib import Path
import pytest
from doc_cleaner.utils import sanitize_filename, safe_target_path


def test_basic_format():
    result = sanitize_filename(
        date="2024-03-12",
        sender="Allianz",
        document_type="Beitragsrechnung",
        original_stem="old_name",
        extension=".pdf",
    )
    assert result == "2024-03-12 - Allianz - Beitragsrechnung.pdf"


def test_no_date_uses_undated():
    result = sanitize_filename(
        date=None,
        sender="Sparkasse",
        document_type="Kontoauszug",
        original_stem="stmt",
        extension=".pdf",
    )
    assert result.startswith("undated - Sparkasse")


def test_no_sender_skips_sender():
    result = sanitize_filename(
        date="2024-01-01",
        sender=None,
        document_type="Invoice",
        original_stem="inv",
        extension=".pdf",
    )
    assert "None" not in result
    assert "2024-01-01" in result
    assert "Invoice" in result


def test_forbidden_chars_removed():
    result = sanitize_filename(
        date="2024-01-01",
        sender="Bad:Name/Company",
        document_type="Doc*Type",
        original_stem="x",
        extension=".pdf",
    )
    for ch in r':/"*?<>|\\':
        assert ch not in result


def test_max_length():
    long_sender = "A" * 200
    result = sanitize_filename(
        date="2024-01-01",
        sender=long_sender,
        document_type="Type",
        original_stem="x",
        extension=".pdf",
    )
    assert len(result) <= 200


def test_whitespace_normalized():
    result = sanitize_filename(
        date="2024-01-01",
        sender="  Allianz  ",
        document_type="  Invoice  ",
        original_stem="x",
        extension=".pdf",
    )
    assert "  " not in result


def test_safe_target_path_inside_root(tmp_path):
    target = safe_target_path(tmp_path, "Finance", "Banking", "2024-01-01 - Bank - Statement.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Finance" in str(target)
    assert "Banking" in str(target)


def test_safe_target_path_no_subcategory(tmp_path):
    target = safe_target_path(tmp_path, "Review", None, "unknown.pdf")
    assert str(target).startswith(str(tmp_path))
    assert "Review" in str(target)


def test_safe_target_path_blocks_traversal(tmp_path):
    with pytest.raises(ValueError, match="Path traversal"):
        safe_target_path(tmp_path, "../evil", None, "bad.pdf")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_filename_sanitize.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/utils.py`**

```python
from __future__ import annotations
import re
import shutil
import hashlib
from pathlib import Path

FORBIDDEN_CHARS = re.compile(r'[:/\\*?"<>|]')
MULTI_SPACE = re.compile(r' {2,}')
MAX_STEM_LEN = 196  # leaves room for " (2)" suffix


def sanitize_filename(
    date: str | None,
    sender: str | None,
    document_type: str | None,
    original_stem: str,
    extension: str,
) -> str:
    parts: list[str] = []

    parts.append(date if date else "undated")

    if sender:
        clean = FORBIDDEN_CHARS.sub("", sender).strip()
        clean = MULTI_SPACE.sub(" ", clean)
        if clean:
            parts.append(clean)

    type_part = document_type if document_type else original_stem
    clean_type = FORBIDDEN_CHARS.sub("", type_part).strip()
    clean_type = MULTI_SPACE.sub(" ", clean_type)
    if clean_type:
        parts.append(clean_type)

    stem = " - ".join(parts)
    stem = stem[:MAX_STEM_LEN]
    return stem + extension


def safe_target_path(
    output_root: Path,
    category: str,
    subcategory: str | None,
    filename: str,
) -> Path:
    # Sanitize category/subcategory to avoid injection via model output
    safe_cat = FORBIDDEN_CHARS.sub("", category).strip()
    safe_sub = FORBIDDEN_CHARS.sub("", subcategory).strip() if subcategory else None

    if safe_sub:
        target = output_root / safe_cat / safe_sub / filename
    else:
        target = output_root / safe_cat / filename

    # Path traversal guard
    try:
        target.resolve().relative_to(output_root.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: computed path {target} is not under {output_root}"
        )
    return target


def safe_move(src: Path, dst: Path) -> Path:
    """Move src to dst. Never overwrites. Returns the actual destination path used."""
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    actual = _collision_safe(dst)
    actual.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(actual))
    return actual


def _collision_safe(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    for i in range(2, 100):
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
    # Last resort: short hash
    h = hashlib.md5(str(dst).encode()).hexdigest()[:6]
    fallback = parent / f"{stem}-{h}{suffix}"
    if fallback.exists():
        raise FileExistsError(f"Cannot find a safe target path for {dst}")
    return fallback
```

- [ ] **Step 4: Implement `doc_cleaner/config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    input_dir: Path = Path(".")
    output_root: Path = Path("~/Documents/Sorted")
    model: str = "qwen3.5:9b"
    ollama_host: str = "http://127.0.0.1:11434"
    allow_remote_ollama: bool = False
    plan_path: Optional[Path] = None
    jsonl_path: Optional[Path] = None
    dry_run: bool = True
    confidence_threshold: int = 90
    max_files: Optional[int] = None
    max_depth: Optional[int] = None
    include_hidden: bool = False
    follow_symlinks: bool = False
    ocr: bool = False
    ocr_language: str = "deu+eng"
    workers: int = 1
    max_text_chars: int = 4000
    cache_dir: Optional[Path] = None
    taxonomy_path: Optional[Path] = None
    limit: Optional[int] = None
    verbose: bool = False
    quiet: bool = False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_filename_sanitize.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/config.py doc_cleaner/utils.py tests/test_filename_sanitize.py
git commit -m "feat: config dataclass, filename sanitization, path traversal guard"
```

---

## Task 4: scanner.py + test_scanner.py

**Files:**
- Create: `doc_cleaner/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_scanner.py`:
```python
from pathlib import Path
import pytest
from doc_cleaner.scanner import scan_files, FileMetadata


@pytest.fixture
def doc_tree(tmp_path):
    (tmp_path / "Finance").mkdir()
    (tmp_path / "Finance" / "invoice.txt").write_text("Invoice dated 2024-03-12")
    (tmp_path / "Legal").mkdir()
    (tmp_path / "Legal" / "contract.txt").write_text("Rental contract 2021-06-02")
    # Hidden file — should be skipped by default
    (tmp_path / ".DS_Store").write_bytes(b"hidden")
    # System dir — should be skipped
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.js").write_text("skip me")
    # Nested
    (tmp_path / "Finance" / "sub").mkdir()
    (tmp_path / "Finance" / "sub" / "deep.txt").write_text("deep file")
    return tmp_path


def test_scan_finds_regular_files(doc_tree):
    results = list(scan_files(doc_tree))
    paths = [r.filename for r in results]
    assert "invoice.txt" in paths
    assert "contract.txt" in paths


def test_scan_skips_hidden_files(doc_tree):
    results = list(scan_files(doc_tree))
    assert not any(r.filename.startswith(".") for r in results)


def test_scan_skips_node_modules(doc_tree):
    results = list(scan_files(doc_tree))
    assert not any("node_modules" in str(r.original_path) for r in results)


def test_include_hidden_flag(doc_tree):
    results = list(scan_files(doc_tree, include_hidden=True))
    assert any(r.filename == ".DS_Store" for r in results)


def test_max_files_limit(doc_tree):
    results = list(scan_files(doc_tree, max_files=1))
    assert len(results) == 1


def test_max_depth(doc_tree):
    # max_depth=1 means only root-level files (none here) + first level dirs
    results = list(scan_files(doc_tree, max_depth=1))
    # Should not find deep.txt (Finance/sub/deep.txt is depth 2)
    assert not any(r.filename == "deep.txt" for r in results)


def test_metadata_fields(doc_tree):
    results = list(scan_files(doc_tree))
    meta = next(r for r in results if r.filename == "invoice.txt")
    assert isinstance(meta, FileMetadata)
    assert meta.extension == ".txt"
    assert meta.file_size > 0
    assert len(meta.file_hash) == 64  # SHA-256 hex
    assert meta.modified_time > 0
    assert meta.original_path.is_absolute()


def test_relative_path(doc_tree):
    results = list(scan_files(doc_tree))
    meta = next(r for r in results if r.filename == "invoice.txt")
    assert not meta.relative_path.is_absolute()
    assert str(meta.relative_path) == "Finance/invoice.txt"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scanner.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/scanner.py`**

```python
from __future__ import annotations
import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", "Library", "Applications", "System",
    ".Trash", "__pycache__", ".venv", "venv", "env",
    "site-packages", ".tox", "dist", "build", "Caches",
})


@dataclass
class FileMetadata:
    original_path: Path
    relative_path: Path
    filename: str
    extension: str
    file_size: int
    created_time: float | None
    modified_time: float
    mime_type: str
    file_hash: str


def scan_files(
    input_dir: Path,
    max_depth: int | None = None,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    max_files: int | None = None,
) -> Iterator[FileMetadata]:
    count = 0
    input_dir = input_dir.resolve()

    for root, dirs, files in os.walk(str(input_dir), followlinks=follow_symlinks):
        root_path = Path(root)
        depth = len(root_path.relative_to(input_dir).parts)

        if max_depth is not None and depth >= max_depth:
            dirs.clear()
            continue

        # Filter subdirs in-place (modifies os.walk traversal)
        dirs[:] = sorted([
            d for d in dirs
            if (include_hidden or not d.startswith("."))
            and d not in SKIP_DIRS
        ])

        for filename in sorted(files):
            if max_files is not None and count >= max_files:
                return
            if not include_hidden and filename.startswith("."):
                continue

            file_path = root_path / filename
            if not follow_symlinks and file_path.is_symlink():
                continue

            try:
                meta = _build_metadata(file_path, input_dir)
                yield meta
                count += 1
            except (PermissionError, OSError):
                continue


def _build_metadata(file_path: Path, base_dir: Path) -> FileMetadata:
    stat = file_path.stat()
    return FileMetadata(
        original_path=file_path.resolve(),
        relative_path=file_path.relative_to(base_dir),
        filename=file_path.name,
        extension=file_path.suffix.lower(),
        file_size=stat.st_size,
        created_time=getattr(stat, "st_birthtime", None),
        modified_time=stat.st_mtime,
        mime_type=_detect_mime(file_path),
        file_hash=_sha256(file_path),
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_mime(path: Path) -> str:
    try:
        import magic
        return magic.from_file(str(path), mime=True)
    except (ImportError, Exception):
        guessed, _ = mimetypes.guess_type(path.name)
        return guessed or "application/octet-stream"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scanner.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/scanner.py tests/test_scanner.py
git commit -m "feat: file scanner with metadata, SHA-256, skip rules"
```

---

## Task 5: Extractors + test_extractors.py

**Files:**
- Create: `doc_cleaner/extractors/__init__.py`
- Create: `doc_cleaner/extractors/text.py`
- Create: `doc_cleaner/extractors/pdf.py`
- Create: `doc_cleaner/extractors/docx.py`
- Create: `doc_cleaner/extractors/image_ocr.py`
- Create: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_extractors.py`:
```python
from pathlib import Path
import pytest
from doc_cleaner.scanner import FileMetadata
from doc_cleaner.extractors import extract_text, ExtractionResult


def _make_meta(path: Path, ext: str, mime: str) -> FileMetadata:
    return FileMetadata(
        original_path=path,
        relative_path=Path(path.name),
        filename=path.name,
        extension=ext,
        file_size=path.stat().st_size,
        created_time=None,
        modified_time=path.stat().st_mtime,
        mime_type=mime,
        file_hash="abc123",
    )


def test_extract_plain_text(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Hello world from a text file.")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert isinstance(result, ExtractionResult)
    assert "Hello world" in result.text
    assert result.extractor == "text"
    assert result.error is None


def test_extract_markdown(tmp_path):
    p = tmp_path / "readme.md"
    p.write_text("# Title\n\nSome content here.")
    meta = _make_meta(p, ".md", "text/markdown")
    result = extract_text(meta)
    assert "Title" in result.text
    assert result.extractor == "text"


def test_extract_unsupported_returns_empty(tmp_path):
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x00\x01\x02")
    meta = _make_meta(p, ".bin", "application/octet-stream")
    result = extract_text(meta)
    assert result.text == ""
    assert result.extractor == "none"


def test_extract_empty_file_returns_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    meta = _make_meta(p, ".txt", "text/plain")
    result = extract_text(meta)
    assert result.text == ""
    assert result.error is None


def test_extraction_result_dataclass():
    r = ExtractionResult(text="hello", extractor="text")
    assert r.error is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_extractors.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/extractors/text.py`**

```python
from __future__ import annotations
from pathlib import Path


def extract_plain_text(path: Path, max_chars: int = 0) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if max_chars > 0:
            text = text[:max_chars]
        return text
    except Exception:
        return ""
```

- [ ] **Step 4: Implement `doc_cleaner/extractors/pdf.py`**

```python
from __future__ import annotations
from pathlib import Path


def extract_pdf_text(path: Path, max_chars: int = 0) -> tuple[str, str | None]:
    """Returns (text, error_or_none)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            parts.append(page_text)
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "pypdf not installed"
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 5: Implement `doc_cleaner/extractors/docx.py`**

```python
from __future__ import annotations
from pathlib import Path


def extract_docx_text(path: Path, max_chars: int = 0) -> tuple[str, str | None]:
    try:
        from docx import Document
        doc = Document(str(path))
        parts = [para.text for para in doc.paragraphs if para.text.strip()]
        text = "\n".join(parts)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "python-docx not installed"
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 6: Implement `doc_cleaner/extractors/image_ocr.py`**

```python
from __future__ import annotations
from pathlib import Path


def extract_ocr_text(path: Path, language: str = "deu+eng", max_chars: int = 0) -> tuple[str, str | None]:
    """OCR extraction via pytesseract. Returns (text, error_or_none).
    Gracefully degrades if pytesseract or Tesseract binary is unavailable."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img, lang=language)
        if max_chars > 0:
            text = text[:max_chars]
        return text, None
    except ImportError:
        return "", "ocr_unavailable"
    except Exception as e:
        return "", str(e)
```

- [ ] **Step 7: Implement `doc_cleaner/extractors/__init__.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from doc_cleaner.scanner import FileMetadata

TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".csv", ".log", ".json", ".xml", ".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}


@dataclass
class ExtractionResult:
    text: str
    extractor: str
    error: str | None = None


def extract_text(
    meta: FileMetadata,
    max_chars: int = 0,
    ocr: bool = False,
    ocr_language: str = "deu+eng",
) -> ExtractionResult:
    ext = meta.extension

    if ext in TEXT_EXTENSIONS:
        from doc_cleaner.extractors.text import extract_plain_text
        text = extract_plain_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="text")

    if ext in PDF_EXTENSIONS:
        from doc_cleaner.extractors.pdf import extract_pdf_text
        text, err = extract_pdf_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="pdf", error=err)

    if ext in DOCX_EXTENSIONS:
        from doc_cleaner.extractors.docx import extract_docx_text
        text, err = extract_docx_text(meta.original_path, max_chars)
        return ExtractionResult(text=text, extractor="docx", error=err)

    if ext in IMAGE_EXTENSIONS and ocr:
        from doc_cleaner.extractors.image_ocr import extract_ocr_text
        text, err = extract_ocr_text(meta.original_path, ocr_language, max_chars)
        extractor = "ocr_unavailable" if err == "ocr_unavailable" else "image_ocr"
        return ExtractionResult(text=text, extractor=extractor, error=err)

    return ExtractionResult(text="", extractor="none")
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_extractors.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add doc_cleaner/extractors/ tests/test_extractors.py
git commit -m "feat: text/PDF/DOCX extractors with OCR soft dependency"
```

---

## Task 6: classifier/schema.py + test_schema.py

**Files:**
- Create: `doc_cleaner/classifier/schema.py`
- Create: `tests/test_schema.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_schema.py`:
```python
import pytest
from pydantic import ValidationError
from doc_cleaner.classifier.schema import ClassificationResult, PlanRow, UndoEntry, UndoManifest


def test_valid_classification():
    r = ClassificationResult(
        category="Finance",
        subcategory="Insurance",
        document_date="2024-03-12",
        sender="Allianz",
        document_type="Beitragsrechnung",
        suggested_filename="2024-03-12 - Allianz - Beitragsrechnung.pdf",
        confidence=92,
        reason="Contains Allianz and invoice date.",
        needs_review=False,
    )
    assert r.confidence == 92
    assert r.needs_review is False


def test_confidence_clamped_above_100():
    r = ClassificationResult(
        category="Review", suggested_filename="x.pdf",
        confidence=150, reason="test", needs_review=True,
    )
    assert r.confidence == 100


def test_confidence_clamped_below_0():
    r = ClassificationResult(
        category="Review", suggested_filename="x.pdf",
        confidence=-5, reason="test", needs_review=True,
    )
    assert r.confidence == 0


def test_null_fields_allowed():
    r = ClassificationResult(
        category="Review",
        document_date=None,
        sender=None,
        document_type=None,
        suggested_filename="unknown.pdf",
        confidence=10,
        reason="Cannot determine",
        needs_review=True,
    )
    assert r.sender is None
    assert r.document_date is None


def test_invalid_json_raises_validation_error():
    with pytest.raises((ValidationError, TypeError)):
        ClassificationResult.model_validate({"confidence": "not-a-number"})


def test_plan_row_defaults():
    row = PlanRow(
        status="planned",
        original_path="/tmp/a.pdf",
        target_path="/out/Finance/Banking/a.pdf",
        category="Finance",
        suggested_filename="a.pdf",
        confidence=90,
        needs_review=False,
        reason="test",
        file_size=1024,
        file_hash="abc",
        modified_time="2024-01-01T00:00:00",
        extractor="pdf",
        model="qwen3.5:9b",
    )
    assert row.approved is False
    assert row.error == ""


def test_undo_manifest_roundtrip():
    entry = UndoEntry(
        original_path="/tmp/a.pdf",
        applied_path="/out/Finance/a.pdf",
        file_hash="abc123",
        moved_at="2026-05-13T10:00:00",
    )
    manifest = UndoManifest(created_at="2026-05-13T10:00:00", entries=[entry])
    json_str = manifest.model_dump_json()
    restored = UndoManifest.model_validate_json(json_str)
    assert restored.entries[0].original_path == "/tmp/a.pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_schema.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/classifier/schema.py`**

```python
from __future__ import annotations
from pydantic import BaseModel, field_validator, Field
from typing import Optional


class ClassificationResult(BaseModel):
    category: str
    subcategory: Optional[str] = None
    document_date: Optional[str] = None
    sender: Optional[str] = None
    document_type: Optional[str] = None
    suggested_filename: str
    confidence: int = Field(default=0)
    reason: str = ""
    needs_review: bool = True

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> int:
        try:
            return max(0, min(100, int(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0


class PlanRow(BaseModel):
    approved: bool = False
    status: str
    original_path: str
    target_path: str
    category: str
    subcategory: Optional[str] = None
    document_date: Optional[str] = None
    sender: Optional[str] = None
    document_type: Optional[str] = None
    suggested_filename: str
    confidence: int
    needs_review: bool
    reason: str
    file_size: int
    file_hash: str
    modified_time: str
    extractor: str
    model: str
    error: str = ""


class UndoEntry(BaseModel):
    original_path: str
    applied_path: str
    file_hash: str
    moved_at: str


class UndoManifest(BaseModel):
    created_at: str
    entries: list[UndoEntry]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_schema.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/classifier/schema.py tests/test_schema.py
git commit -m "feat: Pydantic schemas for ClassificationResult, PlanRow, UndoManifest"
```

---

## Task 7: classifier/prompts.py + test_prompts.py

**Files:**
- Create: `doc_cleaner/classifier/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_prompts.py`:
```python
from pathlib import Path
import pytest
from doc_cleaner.classifier.prompts import build_prompt, select_excerpt, PROMPT_VERSION
from doc_cleaner.scanner import FileMetadata


def _meta(tmp_path, filename="invoice.pdf"):
    p = tmp_path / filename
    p.write_text("x")
    return FileMetadata(
        original_path=p,
        relative_path=Path(filename),
        filename=filename,
        extension=".pdf",
        file_size=1,
        created_time=None,
        modified_time=1700000000.0,
        mime_type="application/pdf",
        file_hash="abc123",
    )


def test_prompt_version_is_string():
    assert isinstance(PROMPT_VERSION, str)
    assert len(PROMPT_VERSION) > 0


def test_build_prompt_contains_filename(tmp_path):
    taxonomy = {"Finance": ["Banking"], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "Some invoice text", taxonomy)
    assert "invoice.pdf" in prompt


def test_build_prompt_contains_categories(tmp_path):
    taxonomy = {"Finance": ["Banking"], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "text", taxonomy)
    assert "Finance" in prompt
    assert "Review" in prompt


def test_build_prompt_json_instruction(tmp_path):
    taxonomy = {"Finance": [], "Review": []}
    prompt = build_prompt(_meta(tmp_path), "text", taxonomy)
    assert "Return valid JSON only" in prompt
    assert "markdown" in prompt.lower()


def test_select_excerpt_short_text():
    text = "short text"
    result = select_excerpt(text, first_n=1500, last_n=500)
    assert result == text


def test_select_excerpt_includes_first_and_last():
    text = "A" * 3000
    result = select_excerpt(text, first_n=100, last_n=50)
    assert result.startswith("A" * 100)


def test_select_excerpt_empty():
    assert select_excerpt("") == ""


def test_select_excerpt_captures_keyword_lines():
    text = "boring line\nRechnung from Allianz\nboring line 2\n12.03.2024 payment"
    result = select_excerpt(text, first_n=5, last_n=5)
    assert "Rechnung" in result or "2024" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompts.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/classifier/prompts.py`**

```python
from __future__ import annotations
import re
from datetime import datetime
from doc_cleaner.scanner import FileMetadata

PROMPT_VERSION = "v1"

_DATE_RE = re.compile(r'\d{1,2}[.\/\-]\d{1,2}[.\/\-]\d{2,4}|\d{4}[.\/\-]\d{2}[.\/\-]\d{2}')
_KEYWORD_RE = re.compile(
    r'\b(Rechnung|Invoice|Kontoauszug|Statement|Vertrag|Contract|'
    r'Bescheid|Beitragsrechnung|Steuerbescheid|Mahnung|Quittung|Receipt|'
    r'Zertifikat|Certificate|Kundigung|Kündigung|Mietvertrag|'
    r'Lohnabrechnung|Gehaltsabrechnung|Versicherung|Insurance|'
    r'Bank|IBAN|GmbH|AG|UG|Ltd|Corp|Inc|Sparkasse|Finanzamt)\b',
    re.IGNORECASE,
)


def select_excerpt(
    text: str,
    first_n: int = 1500,
    last_n: int = 500,
    max_keyword_lines: int = 20,
) -> str:
    if not text:
        return ""

    first = text[:first_n]
    last = text[-last_n:] if len(text) > first_n + last_n else ""

    keyword_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and (_DATE_RE.search(stripped) or _KEYWORD_RE.search(stripped)):
            keyword_lines.append(stripped)
            if len(keyword_lines) >= max_keyword_lines:
                break

    parts = [first]
    if last:
        parts.extend(["\n[...]\n", last])
    if keyword_lines:
        parts.extend(["\n[Key lines:]\n", "\n".join(keyword_lines)])

    return "".join(parts)


def build_prompt(
    meta: FileMetadata,
    text: str,
    taxonomy: dict[str, list[str]],
    first_n: int = 1500,
    last_n: int = 500,
) -> str:
    categories_str = "\n".join(
        f"- {cat}" + (f": {', '.join(subs)}" if subs else "")
        for cat, subs in taxonomy.items()
    )
    excerpt = select_excerpt(text, first_n, last_n)
    modified_iso = datetime.fromtimestamp(meta.modified_time).strftime("%Y-%m-%d")

    return f"""You are a document classifier. Classify the following document.

ALLOWED CATEGORIES AND SUBCATEGORIES:
{categories_str}

FILE METADATA:
- Filename: {meta.filename}
- Extension: {meta.extension}
- Size: {meta.file_size} bytes
- Modified: {modified_iso}
- MIME: {meta.mime_type}
- Path hint (may be unreliable): {meta.relative_path}

DOCUMENT TEXT EXCERPT:
{excerpt or "(no text extracted)"}

INSTRUCTIONS:
- Choose category and subcategory ONLY from the allowed list above.
- Use "Review" if you are not confident about the category.
- Do not hallucinate dates, senders, or document types that are not present in the text.
- If the date is unknown, set document_date to null.
- If the sender is unknown, set sender to null.
- confidence must be an integer 0-100.
- Set needs_review to true if confidence < 80 or if category is "Review".
- Return valid JSON only. Do not include markdown. Do not include explanations outside the JSON object.

Return exactly this JSON structure:
{{
  "category": "...",
  "subcategory": "... or null",
  "document_date": "YYYY-MM-DD or null",
  "sender": "... or null",
  "document_type": "...",
  "suggested_filename": "YYYY-MM-DD - Sender - DocumentType.ext",
  "confidence": 0,
  "reason": "...",
  "needs_review": true
}}"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_prompts.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/classifier/prompts.py tests/test_prompts.py
git commit -m "feat: prompt builder with excerpt selection"
```

---

## Task 8: cache.py + classifier/ollama.py + test_ollama.py

**Files:**
- Create: `doc_cleaner/cache.py`
- Create: `doc_cleaner/classifier/ollama.py`
- Create: `tests/test_ollama.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_ollama.py`:
```python
from pathlib import Path
import json
import pytest
from unittest.mock import MagicMock, patch
from doc_cleaner.classifier.ollama import OllamaClient, parse_classification
from doc_cleaner.classifier.schema import ClassificationResult
from doc_cleaner.cache import ResultCache


VALID_JSON = json.dumps({
    "category": "Finance",
    "subcategory": "Insurance",
    "document_date": "2024-03-12",
    "sender": "Allianz",
    "document_type": "Beitragsrechnung",
    "suggested_filename": "2024-03-12 - Allianz - Beitragsrechnung.pdf",
    "confidence": 92,
    "reason": "Contains Allianz.",
    "needs_review": False,
})


def test_parse_valid_json():
    result = parse_classification(VALID_JSON)
    assert isinstance(result, ClassificationResult)
    assert result.category == "Finance"
    assert result.confidence == 92


def test_parse_invalid_json_returns_review():
    result = parse_classification("not json at all {{broken")
    assert result.category == "Review"
    assert result.needs_review is True
    assert result.confidence == 0


def test_parse_json_with_markdown_fences():
    wrapped = f"```json\n{VALID_JSON}\n```"
    result = parse_classification(wrapped)
    assert result.category == "Finance"


def test_ollama_client_blocks_non_localhost():
    with pytest.raises(ValueError, match="allow-remote-ollama"):
        OllamaClient(host="https://api.example.com", model="test", allow_remote=False)


def test_ollama_client_allows_localhost():
    client = OllamaClient(host="http://127.0.0.1:11434", model="test")
    assert client.host == "http://127.0.0.1:11434"


def test_result_cache_miss(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    result = cache.get("abc123", "model-name")
    assert result is None


def test_result_cache_set_and_get(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    r = ClassificationResult(
        category="Finance", suggested_filename="x.pdf",
        confidence=90, reason="test", needs_review=False,
    )
    cache.set("abc123", "model-name", r)
    retrieved = cache.get("abc123", "model-name")
    assert retrieved is not None
    assert retrieved.category == "Finance"


def test_result_cache_different_model_is_miss(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    r = ClassificationResult(
        category="Finance", suggested_filename="x.pdf",
        confidence=90, reason="test", needs_review=False,
    )
    cache.set("abc123", "model-a", r)
    assert cache.get("abc123", "model-b") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ollama.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/cache.py`**

```python
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Optional
from doc_cleaner.classifier.schema import ClassificationResult
from doc_cleaner.classifier.prompts import PROMPT_VERSION


class ResultCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, file_hash: str, model: str) -> str:
        raw = f"{file_hash}:{model}:{PROMPT_VERSION}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, file_hash: str, model: str) -> Optional[ClassificationResult]:
        path = self._path(self._key(file_hash, model))
        if not path.exists():
            return None
        try:
            return ClassificationResult.model_validate_json(path.read_text())
        except Exception:
            return None

    def set(self, file_hash: str, model: str, result: ClassificationResult) -> None:
        path = self._path(self._key(file_hash, model))
        path.write_text(result.model_dump_json())
```

- [ ] **Step 4: Implement `doc_cleaner/classifier/ollama.py`**

```python
from __future__ import annotations
import json
import re
from urllib.parse import urlparse
import httpx
from doc_cleaner.classifier.schema import ClassificationResult

_LOCALHOST = {"127.0.0.1", "localhost", "::1"}
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_classification(raw: str) -> ClassificationResult:
    """Parse raw Ollama response string into ClassificationResult.
    Strips markdown fences. Returns Review result on any parse failure."""
    text = raw.strip()

    # Strip markdown code fences if present
    fence_match = _JSON_FENCE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
        return ClassificationResult.model_validate(data)
    except Exception:
        return ClassificationResult(
            category="Review",
            suggested_filename="",
            confidence=0,
            reason=f"Failed to parse model response: {raw[:200]}",
            needs_review=True,
        )


class OllamaClient:
    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:9b",
        timeout: int = 120,
        allow_remote: bool = False,
    ):
        parsed = urlparse(host)
        if not allow_remote and parsed.hostname not in _LOCALHOST:
            raise ValueError(
                f"Non-localhost Ollama host '{host}' requires --allow-remote-ollama. "
                "This flag acknowledges that document content will leave this machine."
            )
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str) -> str:
        """POST to Ollama /api/generate and return the response string."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Ollama is not running at {self.host}.\n"
                "Start it with: ollama serve"
            )

    def classify(self, prompt: str) -> ClassificationResult:
        """Generate + parse. Retries once with a stricter repair prompt on failure."""
        raw = self.generate(prompt)
        result = parse_classification(raw)

        if result.category == "Review" and result.confidence == 0:
            # Retry with repair prompt
            repair_prompt = (
                f"The following is not valid JSON. "
                f"Return ONLY the JSON object, no markdown, no explanation:\n{raw[:500]}"
            )
            raw2 = self.generate(repair_prompt)
            result2 = parse_classification(raw2)
            if result2.category != "Review" or result2.confidence > 0:
                return result2

        return result

    def check_health(self) -> bool:
        try:
            resp = self._client.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            resp = self._client.get(f"{self.host}/api/tags", timeout=10)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_ollama.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add doc_cleaner/cache.py doc_cleaner/classifier/ollama.py tests/test_ollama.py
git commit -m "feat: OllamaClient with localhost guard, ResultCache, JSON parsing with retry"
```

---

## Task 9: planner.py + test_planner.py

**Files:**
- Create: `doc_cleaner/planner.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_planner.py`:
```python
from pathlib import Path
import csv
import pytest
from doc_cleaner.planner import PlanWriter, compute_target
from doc_cleaner.classifier.schema import PlanRow


def _row(**kwargs) -> PlanRow:
    defaults = dict(
        approved=False, status="planned",
        original_path="/tmp/a.pdf", target_path="/out/a.pdf",
        category="Finance", suggested_filename="a.pdf",
        confidence=90, needs_review=False, reason="test",
        file_size=1024, file_hash="abc", modified_time="2024-01-01T00:00:00",
        extractor="pdf", model="qwen3.5:9b",
    )
    defaults.update(kwargs)
    return PlanRow(**defaults)


def test_plan_writer_creates_csv(tmp_path):
    csv_path = tmp_path / "plan.csv"
    with PlanWriter(csv_path) as writer:
        writer.write(_row())

    assert csv_path.exists()
    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 1
    assert rows[0]["category"] == "Finance"


def test_plan_writer_creates_jsonl(tmp_path):
    csv_path = tmp_path / "plan.csv"
    jsonl_path = tmp_path / "plan.jsonl"
    with PlanWriter(csv_path, jsonl_path) as writer:
        writer.write(_row())

    lines = jsonl_path.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    data = json.loads(lines[0])
    assert data["category"] == "Finance"


def test_compute_target_basic(tmp_path):
    seen: set[Path] = set()
    result = compute_target(tmp_path, "Finance", "Banking", "2024-01-01 - Bank.pdf", seen)
    assert result == tmp_path / "Finance" / "Banking" / "2024-01-01 - Bank.pdf"
    assert result in seen


def test_compute_target_collision(tmp_path):
    existing = tmp_path / "Finance" / "Banking" / "file.pdf"
    existing.parent.mkdir(parents=True)
    existing.touch()

    seen: set[Path] = {existing}
    result = compute_target(tmp_path, "Finance", "Banking", "file.pdf", seen)
    assert result != existing
    assert "file (2)" in result.name or "-" in result.stem


def test_compute_target_no_subcategory(tmp_path):
    seen: set[Path] = set()
    result = compute_target(tmp_path, "Review", None, "unknown.pdf", seen)
    assert str(result) == str(tmp_path / "Review" / "unknown.pdf")


def test_compute_target_path_traversal_blocked(tmp_path):
    seen: set[Path] = set()
    with pytest.raises(ValueError, match="Path traversal"):
        compute_target(tmp_path, "../evil", None, "bad.pdf", seen)


def test_plan_writer_writes_multiple_rows(tmp_path):
    csv_path = tmp_path / "plan.csv"
    with PlanWriter(csv_path) as writer:
        writer.write(_row(category="Finance"))
        writer.write(_row(category="Legal"))

    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 2
    cats = [r["category"] for r in rows]
    assert "Finance" in cats
    assert "Legal" in cats
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_planner.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/planner.py`**

```python
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
from typing import Optional
from doc_cleaner.classifier.schema import PlanRow
from doc_cleaner.utils import safe_target_path

CSV_COLUMNS = [
    "approved", "status", "original_path", "target_path", "category",
    "subcategory", "document_date", "sender", "document_type",
    "suggested_filename", "confidence", "needs_review", "reason",
    "file_size", "file_hash", "modified_time", "extractor", "model", "error",
]


class PlanWriter:
    def __init__(self, csv_path: Path, jsonl_path: Optional[Path] = None):
        self.csv_path = csv_path
        self.jsonl_path = jsonl_path
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._csv_file, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        self._writer.writeheader()
        if jsonl_path:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._jsonl_file = open(jsonl_path, "w", encoding="utf-8")
        else:
            self._jsonl_file = None

    def write(self, row: PlanRow) -> None:
        d = row.model_dump()
        # Booleans must be lowercase strings in CSV
        d["approved"] = str(d["approved"]).lower()
        d["needs_review"] = str(d["needs_review"]).lower()
        # None → empty string
        for k, v in d.items():
            if v is None:
                d[k] = ""
        self._writer.writerow(d)
        self._csv_file.flush()
        if self._jsonl_file:
            self._jsonl_file.write(row.model_dump_json() + "\n")
            self._jsonl_file.flush()

    def close(self) -> None:
        self._csv_file.close()
        if self._jsonl_file:
            self._jsonl_file.close()

    def __enter__(self) -> "PlanWriter":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def compute_target(
    output_root: Path,
    category: str,
    subcategory: Optional[str],
    suggested_filename: str,
    existing_paths: set[Path],
) -> Path:
    # safe_target_path raises ValueError on path traversal
    base = safe_target_path(output_root, category, subcategory, suggested_filename)

    if base not in existing_paths:
        existing_paths.add(base)
        return base

    # Collision resolution
    stem = base.stem
    suffix = base.suffix
    parent = base.parent
    for i in range(2, 100):
        candidate = parent / f"{stem} ({i}){suffix}"
        if candidate not in existing_paths:
            existing_paths.add(candidate)
            return candidate

    # Last resort hash suffix
    h = hashlib.md5(suggested_filename.encode()).hexdigest()[:6]
    fallback = parent / f"{stem}-{h}{suffix}"
    existing_paths.add(fallback)
    return fallback
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_planner.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/planner.py tests/test_planner.py
git commit -m "feat: PlanWriter (CSV+JSONL) and compute_target with collision handling"
```

---

## Task 10: cli.py scan command (full wire-up)

**Files:**
- Modify: `doc_cleaner/cli.py` — replace `scan` stub with full implementation
- Create: `doc_cleaner/logging.py`

- [ ] **Step 1: Implement `doc_cleaner/logging.py`**

```python
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional


def setup_logging(log_file: Optional[Path] = None, verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("doc_cleaner")
    logger.setLevel(level)

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)

        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(level)
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("doc_cleaner")
```

- [ ] **Step 2: Replace the `scan` stub in `doc_cleaner/cli.py`**

Replace the existing `scan` function body:

```python
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
    import time
    from datetime import datetime
    from rich.console import Console
    from doc_cleaner.scanner import scan_files
    from doc_cleaner.extractors import extract_text
    from doc_cleaner.classifier.ollama import OllamaClient
    from doc_cleaner.classifier.prompts import build_prompt
    from doc_cleaner.classifier.schema import PlanRow
    from doc_cleaner.cache import ResultCache
    from doc_cleaner.planner import PlanWriter, compute_target
    from doc_cleaner.taxonomy import load_taxonomy, normalize_category, REVIEW_CATEGORY
    from doc_cleaner.utils import sanitize_filename
    from doc_cleaner.logging import setup_logging

    console = Console(stderr=True)
    start_time = time.time()

    # Resolve taxonomy
    taxonomy_path = taxonomy or (Path(__file__).parent.parent / "taxonomy.yaml")
    tax = load_taxonomy(taxonomy_path)

    # Resolve plan paths
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_path = plan or Path(f"plans/plan-{ts}.csv")
    jsonl_path = jsonl or Path(f"plans/plan-{ts}.jsonl")

    # Resolve cache dir
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

    with PlanWriter(plan_path, jsonl_path) as writer:
        files = scan_files(
            input.expanduser().resolve(),
            max_depth=max_depth,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
            max_files=limit or max_files,
        )

        for meta in files:
            counts["scanned"] += 1
            if not quiet:
                console.print(f"  [dim]{meta.relative_path}[/dim]", end="\r")

            error_msg = ""
            extractor_name = "none"
            classification = None

            try:
                # Check cache first
                classification = cache.get(meta.file_hash, model)
                if classification:
                    counts["cached"] += 1
                else:
                    extraction = extract_text(meta, max_chars=max_text_chars, ocr=ocr, ocr_language=ocr_language)
                    extractor_name = extraction.extractor
                    prompt = build_prompt(meta, extraction.text, tax)
                    classification = ollama.classify(prompt)
                    cache.set(meta.file_hash, model, classification)

                # Force needs_review if below threshold
                if classification.confidence < confidence_threshold:
                    classification = classification.model_copy(update={"needs_review": True})

                # Validate + normalize category
                cat, sub = normalize_category(classification.category, classification.subcategory, tax)

                # Build safe filename
                safe_name = sanitize_filename(
                    date=classification.document_date,
                    sender=classification.sender,
                    document_type=classification.document_type,
                    original_stem=meta.original_path.stem,
                    extension=meta.extension,
                )

                target = compute_target(output_root.expanduser().resolve(), cat, sub, safe_name, existing_targets)
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
                target = compute_target(output_root.expanduser().resolve(), cat, sub, safe_name, existing_targets)
                status = "error"
                classification = classification or _error_classification(str(e))

            row = PlanRow(
                approved=False,
                status=status,
                original_path=str(meta.original_path),
                target_path=str(target),
                category=cat,
                subcategory=sub,
                document_date=getattr(classification, "document_date", None),
                sender=getattr(classification, "sender", None),
                document_type=getattr(classification, "document_type", None),
                suggested_filename=safe_name,
                confidence=getattr(classification, "confidence", 0),
                needs_review=getattr(classification, "needs_review", True),
                reason=getattr(classification, "reason", ""),
                file_size=meta.file_size,
                file_hash=meta.file_hash,
                modified_time=str(meta.modified_time),
                extractor=extractor_name,
                model=model,
                error=error_msg,
            )
            writer.write(row)

    elapsed = time.time() - start_time
    if not quiet:
        console.print(f"\n[bold green]Scan complete[/bold green] ({elapsed:.1f}s)")
        console.print(f"  Scanned:       {counts['scanned']}")
        console.print(f"  Classified:    {counts['classified']}")
        console.print(f"  Needs review:  {counts['review']}")
        console.print(f"  Errors:        {counts['errors']}")
        console.print(f"  Cached:        {counts['cached']}")
        console.print(f"  Plan written to: {plan_path}")
        console.print(f"\n[yellow]No files were moved.[/yellow] Review the plan, then run apply.")


def _error_classification(msg: str):
    from doc_cleaner.classifier.schema import ClassificationResult
    return ClassificationResult(
        category="Review", suggested_filename="",
        confidence=0, reason=f"Error: {msg}", needs_review=True,
    )
```

- [ ] **Step 3: Smoke test the scan command (no Ollama required, just check --help)**

```bash
python -m doc_cleaner scan --help
```

Expected: Help text shows all flags.

- [ ] **Step 4: Commit**

```bash
git add doc_cleaner/cli.py doc_cleaner/logging.py
git commit -m "feat: wire up scan command end-to-end"
```

---

## Task 11: applier.py + test_apply_no_overwrite.py

**Files:**
- Create: `doc_cleaner/applier.py`
- Create: `tests/test_apply_no_overwrite.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_apply_no_overwrite.py`:
```python
from pathlib import Path
import csv
import json
import pytest
from doc_cleaner.applier import apply_plan
from doc_cleaner.classifier.schema import UndoManifest


def _write_plan(path: Path, rows: list[dict]) -> None:
    columns = [
        "approved", "status", "original_path", "target_path", "category",
        "subcategory", "document_date", "sender", "document_type",
        "suggested_filename", "confidence", "needs_review", "reason",
        "file_size", "file_hash", "modified_time", "extractor", "model", "error",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            full = {c: row.get(c, "") for c in columns}
            writer.writerow(full)


def test_apply_moves_approved_file(tmp_path):
    src = tmp_path / "src" / "invoice.pdf"
    src.parent.mkdir(parents=True)
    src.write_text("Invoice content")
    dst = tmp_path / "out" / "Finance" / "invoice.pdf"

    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()

    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": h,
        "file_size": "15",
    }])

    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 1
    assert result.skipped == 0
    assert dst.exists()
    assert not src.exists()


def test_apply_skips_unapproved(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "false",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": "abc",
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 0
    assert src.exists()


def test_apply_does_not_overwrite(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    dst.parent.mkdir(parents=True)
    dst.write_text("existing!")  # target already exists

    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true",
        "status": "planned",
        "original_path": str(src),
        "target_path": str(dst),
        "file_hash": h,
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    # File should be moved to a collision-safe path, not overwriting dst
    assert dst.read_text() == "existing!"
    assert result.moved == 1


def test_apply_writes_undo_manifest(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    import hashlib
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true", "status": "planned",
        "original_path": str(src), "target_path": str(dst),
        "file_hash": h, "file_size": "7",
    }])
    apply_plan(plan, undo, yes=True)
    assert undo.exists()
    manifest = UndoManifest.model_validate_json(undo.read_text())
    assert len(manifest.entries) == 1
    assert manifest.entries[0].original_path == str(src)


def test_apply_skips_hash_mismatch(tmp_path):
    src = tmp_path / "file.pdf"
    src.write_text("content")
    dst = tmp_path / "out" / "file.pdf"
    plan = tmp_path / "plan.csv"
    undo = tmp_path / "undo.json"
    _write_plan(plan, [{
        "approved": "true", "status": "planned",
        "original_path": str(src), "target_path": str(dst),
        "file_hash": "wronghash000",
        "file_size": "7",
    }])
    result = apply_plan(plan, undo, yes=True)
    assert result.moved == 0
    assert result.skipped == 1
    assert src.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_apply_no_overwrite.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `doc_cleaner/applier.py`**

```python
from __future__ import annotations
import csv
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from doc_cleaner.classifier.schema import UndoEntry, UndoManifest
from doc_cleaner.utils import safe_move


@dataclass
class ApplyResult:
    moved: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def apply_plan(
    plan_path: Path,
    undo_path: Path,
    yes: bool = False,
    apply_all_above_threshold: bool = False,
    confidence_threshold: int = 90,
) -> ApplyResult:
    rows = _read_rows(plan_path, apply_all_above_threshold, confidence_threshold)

    if not yes:
        import typer
        from rich.console import Console
        console = Console()
        console.print(f"\n[bold]About to move {len(rows)} files.[/bold]")
        confirmed = typer.confirm("Proceed?", default=False)
        if not confirmed:
            console.print("Aborted.")
            raise typer.Exit()

    entries: list[UndoEntry] = []
    result = ApplyResult()

    for row in rows:
        src = Path(row["original_path"])
        dst = Path(row["target_path"])

        if not src.exists():
            result.errors.append(f"Source not found: {src}")
            continue

        # Verify file hasn't changed
        current_hash = _sha256(src)
        expected_hash = row.get("file_hash", "")
        if expected_hash and current_hash != expected_hash:
            result.skipped += 1
            result.errors.append(f"Hash mismatch (file changed since scan): {src}")
            continue

        try:
            actual_dst = safe_move(src, dst)
            entries.append(UndoEntry(
                original_path=str(src),
                applied_path=str(actual_dst),
                file_hash=current_hash,
                moved_at=datetime.now().isoformat(),
            ))
            result.moved += 1
        except Exception as e:
            result.errors.append(f"Error moving {src}: {e}")

    manifest = UndoManifest(
        created_at=datetime.now().isoformat(),
        entries=entries,
    )
    undo_path.parent.mkdir(parents=True, exist_ok=True)
    undo_path.write_text(manifest.model_dump_json(indent=2))

    _write_undo_script(undo_path.with_suffix(".sh"), entries)

    return result


def _read_rows(
    plan_path: Path,
    apply_all_above_threshold: bool,
    confidence_threshold: int,
) -> list[dict]:
    with open(plan_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    approved = []
    for row in rows:
        is_approved = row.get("approved", "").lower() == "true"
        confidence = int(row.get("confidence", 0) or 0)
        if is_approved or (apply_all_above_threshold and confidence >= confidence_threshold):
            approved.append(row)
    return approved


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_undo_script(sh_path: Path, entries: list[UndoEntry]) -> None:
    lines = ["#!/bin/bash", "# Undo script — moves files back to original locations", "set -e", ""]
    for entry in entries:
        lines.append(f'mv "{entry.applied_path}" "{entry.original_path}"')
    sh_path.write_text("\n".join(lines) + "\n")
    sh_path.chmod(0o755)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_apply_no_overwrite.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add doc_cleaner/applier.py tests/test_apply_no_overwrite.py
git commit -m "feat: apply_plan with safe moves, no-overwrite, undo manifest"
```

---

## Task 12: undo.py + complete cli.py (apply / undo / doctor)

**Files:**
- Create: `doc_cleaner/undo.py`
- Modify: `doc_cleaner/cli.py` — replace `apply`, `undo`, `doctor` stubs

- [ ] **Step 1: Implement `doc_cleaner/undo.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from doc_cleaner.classifier.schema import UndoManifest
from doc_cleaner.utils import safe_move


@dataclass
class UndoResult:
    restored: int = 0
    skipped: int = 0
    conflicts: list[str] = field(default_factory=list)


def undo_moves(manifest_path: Path) -> UndoResult:
    manifest = UndoManifest.model_validate_json(manifest_path.read_text())
    result = UndoResult()

    for entry in manifest.entries:
        src = Path(entry.applied_path)
        dst = Path(entry.original_path)

        if not src.exists():
            result.conflicts.append(f"Applied path no longer exists: {src}")
            result.skipped += 1
            continue

        if dst.exists():
            result.conflicts.append(
                f"Original path is occupied, cannot restore: {dst}. "
                f"Applied file remains at: {src}"
            )
            result.skipped += 1
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            result.restored += 1
        except Exception as e:
            result.conflicts.append(f"Error restoring {src} → {dst}: {e}")
            result.skipped += 1

    return result
```

- [ ] **Step 2: Replace `apply`, `undo`, `doctor` stubs in `doc_cleaner/cli.py`**

```python
@app.command()
def apply(
    plan: Path = typer.Option(..., "--plan", help="Reviewed plan CSV"),
    undo: Path = typer.Option(..., "--undo", help="Path for undo manifest JSON"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    apply_all_above_threshold: bool = typer.Option(False, "--apply-all-above-threshold"),
    confidence_threshold: int = typer.Option(90, "--confidence-threshold"),
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

    # Python version
    py = sys.version
    table.add_row("Python", "[green]OK[/green]", py[:20])

    # Platform
    table.add_row("Platform", "[green]OK[/green]", platform.platform()[:40])

    # Ollama reachable
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

    # pypdf
    try:
        import pypdf  # noqa: F401
        table.add_row("pypdf", "[green]OK[/green]", "PDF extraction available")
    except ImportError:
        table.add_row("pypdf", "[red]MISSING[/red]", "pip install pypdf")

    # python-docx
    try:
        import docx  # noqa: F401
        table.add_row("python-docx", "[green]OK[/green]", "DOCX extraction available")
    except ImportError:
        table.add_row("python-docx", "[red]MISSING[/red]", "pip install python-docx")

    # Tesseract / pytesseract
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        table.add_row("Tesseract", "[green]OK[/green]", f"v{version} — OCR available")
    except ImportError:
        table.add_row("Tesseract", "[yellow]OPTIONAL[/yellow]", "pip install pytesseract (then install Tesseract binary)")
    except Exception as e:
        table.add_row("Tesseract", "[yellow]OPTIONAL[/yellow]", f"Not found: {e}")

    console.print(table)
```

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add doc_cleaner/undo.py doc_cleaner/cli.py
git commit -m "feat: undo command, complete apply/doctor CLI commands"
```

---

## Task 13: test_docs/generate_test_docs.py

**Files:**
- Create: `test_docs/generate_test_docs.py`

This script generates a realistic fake document tree for end-to-end testing. It requires `fpdf2` and `python-docx` (already in dev dependencies).

- [ ] **Step 1: Create `test_docs/generate_test_docs.py`**

```python
#!/usr/bin/env python3
"""
Generate a fake document tree for end-to-end testing of doc-cleaner.
Run: python test_docs/generate_test_docs.py [--output-dir ./test_docs/generated]
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path


FAKE_DOCS = [
    # (relative_path, content, format)
    ("Finance/allianz_beitragsrechnung.pdf",
     "Allianz SE\nMünchen, den 12.03.2024\n\nBeitragsrechnung\n\nVersicherungsnehmer: Max Mustermann\nPolice-Nr.: 123456789\n\nHiermit stellen wir Ihnen Ihren Beitrag in Rechnung:\nJahresbeitrag 2024: 1.234,56 EUR\n\nFällig: 01.04.2024\nIBAN: DE12 3456 7890 1234 5678 90",
     "pdf"),

    ("Finance/sparkasse_kontoauszug.pdf",
     "Sparkasse München\nKontoauszug Nr. 11/2023\nKontoinhaber: Max Mustermann\nKontonummer: 987654321\nBIC: SSKMDEMM\nIBAN: DE98 7654 3210 9876 5432 10\n\nDatum: 04.11.2023\n\nAnfangssaldo: 2.500,00 EUR\nEingang: Gehalt Oktober 3.200,00 EUR\nAusgang: Miete -950,00 EUR\nEndsaldo: 4.750,00 EUR",
     "pdf"),

    ("Finance/finanzamt_steuerbescheid.pdf",
     "Finanzamt München\nFinanzamt-Nr.: 143/234\n\nEinkommensteuerbescheid 2022\nSteuerpflichtige/r: Max Mustermann\nSteuer-Identifikationsnummer: 12 345 678 901\n\nFestsetzung vom 19.08.2022\n\nEinkommensteuer: 8.450,00 EUR\nSolidaritätszuschlag: 0,00 EUR\n\nIhre zu zahlende Steuer: 8.450,00 EUR",
     "pdf"),

    ("Finance/amazon_quittung.txt",
     "Amazon.de\nBestellnummer: 302-1234567-8901234\nDatum: 15.02.2024\n\nArtikel: USB-C Kabel 2m\nMenge: 2\nEinzelpreis: 9,99 EUR\nGesamtbetrag: 19,98 EUR\n\nZahlungsmethode: VISA ***1234\nLieferadresse: Max Mustermann, Musterstr. 1, 80333 München",
     "txt"),

    ("Legal/mietvertrag.docx",
     "Mietvertrag\n\nzwischen\nVermieter: Hans Vermieter, Hauptstr. 5, 80333 München\nund\nMieter: Max Mustermann, Musterstr. 1, 80333 München\n\nDatum: 02.06.2021\n\n§1 Mietobjekt\nDie Wohnung im 2. OG, Musterstr. 1, 80333 München,\nca. 65 qm, wird vermietet.\n\n§2 Miete\nMonatliche Kaltmiete: 950,00 EUR\nNebenkosten: 150,00 EUR\nGesamtmiete: 1.100,00 EUR",
     "docx"),

    ("Legal/unbekannter_vertrag.txt",
     "Vereinbarung\n\nDie Parteien vereinbaren hiermit folgende Konditionen:\n1. Die Lieferung erfolgt bis Ende des Monats.\n2. Die Zahlung ist innerhalb von 30 Tagen fällig.\n\nDiese Vereinbarung tritt mit Unterzeichnung in Kraft.",
     "txt"),

    ("Work/arbeitsvertrag.docx",
     "Arbeitsvertrag\n\nzwischen\nArbeitgeber: Muster GmbH, Industriestr. 10, 80339 München\nund\nArbeitnehmer: Max Mustermann\n\nDatum: 01.03.2020\n\n§1 Beginn und Art der Tätigkeit\nHerr Mustermann wird ab 01.04.2020 als Software Engineer eingestellt.\n\n§2 Vergütung\nMonatliches Bruttogehalt: 5.500,00 EUR",
     "docx"),

    ("Education/uni_zeugnis.pdf",
     "Ludwig-Maximilians-Universität München\n\nZeugnis\n\nHerr Max Mustermann\nMatrikel-Nr.: 12345678\n\nhat den Bachelor of Science in Informatik\nmit der Gesamtnote: 1,8 (gut)\n\nam 15.07.2019 erfolgreich abgeschlossen.\n\nMünchen, 15.07.2019\nProf. Dr. Müller, Dekan",
     "pdf"),

    ("Health/krankenhaus_rechnung.pdf",
     "Klinikum München\nPatientenrechnung\n\nPatient: Max Mustermann, geb. 01.01.1990\nFallnummer: KLM-2023-98765\n\nBehandlungszeitraum: 05.06.2023 - 07.06.2023\n\nLeistungen:\n- Aufnahme und Behandlung: 850,00 EUR\n- Laboruntersuchungen: 220,00 EUR\n\nGesamtbetrag: 1.070,00 EUR\nVersicherungsanteil (AOK): -856,00 EUR\nZuzahlung Patient: 214,00 EUR",
     "pdf"),

    ("Household/vodafone_rechnung.txt",
     "Vodafone GmbH\nKundennummer: 0987654321\n\nRechnung vom 01.04.2024\nRechnungsnummer: VF-2024-03-001\n\nInternetflatrate (100 Mbit/s): 29,99 EUR\nTelefonflat: 0,00 EUR\nGesamtbetrag: 29,99 EUR\n\nFällig: 15.04.2024\nSEPA-Lastschrift von IBAN DE12 ...",
     "txt"),

    # Edge cases
    ("edge_cases/ambiguous_letter.txt",
     "Sehr geehrte Damen und Herren,\n\nbei Rückfragen stehen wir Ihnen gerne zur Verfügung.\n\nMit freundlichen Grüßen",
     "txt"),

    ("edge_cases/no_date_invoice.pdf",
     "Rechnung\n\nAn: Max Mustermann\n\nPosition 1: Beratungsleistung 500,00 EUR\nNetto: 500,00 EUR\nMwSt. 19%: 95,00 EUR\nBrutto: 595,00 EUR\n\nZahlungsziel: 14 Tage nach Rechnungserhalt",
     "pdf"),

    ("edge_cases/duplicate_a.pdf",
     "Duplikat Test Dokument\nInhalt: Identischer Text in beiden Dateien.\nDieses Dokument ist ein Duplikat.",
     "pdf"),

    ("edge_cases/duplicate_b.pdf",
     "Duplikat Test Dokument\nInhalt: Identischer Text in beiden Dateien.\nDieses Dokument ist ein Duplikat.",
     "pdf"),

    ("edge_cases/empty.txt", "", "txt"),

    ("mixed_formats/router_handbuch.txt",
     "Benutzerhandbuch\nFritzBox 7590\n\nKapitel 1: Einrichtung\nVerbinden Sie das Gerät mit dem DSL-Anschluss.\n\nKapitel 2: WLAN\nDas WLAN-Passwort finden Sie auf der Unterseite des Geräts.",
     "txt"),

    ("mixed_formats/notizen.md",
     "# Notizen\n\n## Meeting 2024-03-15\n\n- Projektstart vereinbart\n- Budget genehmigt\n- Nächster Termin: 2024-04-01\n",
     "txt"),

    ("deeply/nested/subfolder/deep_document.txt",
     "Dieses Dokument liegt tief in einer Ordnerstruktur.\nDatum: 01.01.2024\nAussteller: Tief GmbH",
     "txt"),
]


def make_pdf(output_path: Path, content: str) -> None:
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 required: pip install fpdf2")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in content.splitlines():
        pdf.cell(0, 8, line, ln=True)
    pdf.output(str(output_path))


def make_docx(output_path: Path, content: str) -> None:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx required: pip install python-docx")
    doc = Document()
    for line in content.splitlines():
        doc.add_paragraph(line)
    doc.save(str(output_path))


def generate(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for rel_path, content, fmt in FAKE_DOCS:
        path = output_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "pdf":
            make_pdf(path, content)
        elif fmt == "docx":
            make_docx(path, content)
        else:
            path.write_text(content, encoding="utf-8")
        print(f"  Created: {rel_path}")

    print(f"\nGenerated {len(FAKE_DOCS)} test documents in {output_dir}")
    print("\nNext step (once Ollama is running):")
    print(f"  python -m doc_cleaner scan \\")
    print(f"    --input {output_dir} \\")
    print(f"    --output-root /tmp/sorted-test \\")
    print(f"    --plan /tmp/test-plan.csv \\")
    print(f"    --jsonl /tmp/test-plan.jsonl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fake test documents")
    parser.add_argument("--output-dir", default="test_docs/generated", type=Path)
    args = parser.parse_args()
    generate(args.output_dir)
```

- [ ] **Step 2: Run the generator to verify it works**

```bash
python test_docs/generate_test_docs.py --output-dir /tmp/test-docs-check
ls /tmp/test-docs-check/Finance/
ls /tmp/test-docs-check/edge_cases/
```

Expected: PDF, DOCX, and TXT files present in each category folder.

- [ ] **Step 3: Commit**

```bash
git add test_docs/generate_test_docs.py
git commit -m "feat: fake document generator for end-to-end testing"
```

---

## Task 14: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# doc-cleaner

A local-first, privacy-preserving CLI for classifying and organizing messy document folders on macOS.

**All processing is local. No cloud APIs. No telemetry. No account required.**

## What it does

1. Scans a folder recursively and extracts text from PDFs, DOCX, and text files
2. Classifies each file using a local Ollama model (e.g. qwen3.5:9b)
3. Generates a human-reviewable CSV/JSONL plan with suggested moves and renames
4. Applies approved moves when you're ready — with full undo support

## Privacy model

- The only network call is to `http://127.0.0.1:11434` (your local Ollama instance)
- Document text never leaves your machine
- No API keys, no accounts, no analytics, no logs uploaded anywhere
- Fully usable offline after Ollama and models are installed

## Installation

```bash
git clone <repo>
cd doc-cleaner
pip install -e .
```

## Ollama setup

```bash
# Install Ollama: https://ollama.com
ollama serve
ollama pull qwen3.5:9b

# Verify
python -m doc_cleaner doctor
```

## OCR setup (optional)

```bash
brew install tesseract tesseract-lang
pip install pytesseract
python -m doc_cleaner doctor   # should show Tesseract OK
```

## Usage

### 1. Scan (dry-run, no files moved)

```bash
python -m doc_cleaner scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --model qwen3.5:9b \
  --plan ./plans/downloads-plan.csv \
  --jsonl ./plans/downloads-plan.jsonl
```

Output:
```
Scan complete (142.3s)
  Scanned:       428
  Classified:    391
  Needs review:  52
  Errors:        7
  Cached:        0
  Plan written to: plans/downloads-plan.csv

No files were moved. Review the plan, then run apply.
```

### 2. Review the plan

Open `plans/downloads-plan.csv` in Numbers, Excel, or a text editor. For each row:
- Set `approved=true` to approve the move
- Set `approved=false` to skip (default)
- Edit `target_path` if you want a different destination

### 3. Apply approved moves

```bash
python -m doc_cleaner apply \
  --plan ./plans/downloads-plan.csv \
  --undo ./plans/undo-2026-05-13.json
```

You'll see a summary and a confirmation prompt before any files are moved.

### 4. Undo

```bash
python -m doc_cleaner undo \
  --undo-manifest ./plans/undo-2026-05-13.json
```

Or run the generated shell script:
```bash
bash ./plans/undo-2026-05-13.sh
```

### 5. Classify only first 50 files (for testing)

```bash
python -m doc_cleaner scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --limit 50
```

## Recommended workflow

1. **Start with a test copy** — copy 20–30 files to a temp folder first
2. **Dry-run first** — `scan` never moves anything
3. **Review the CSV** — check categories and filenames before approving
4. **Apply in small batches** — approve 10–20 rows at a time initially
5. **Keep backups** — Time Machine or a manual copy before applying to important folders

## Limitations

- Scanned PDFs (image-only) need OCR to extract text; without OCR, classification is based on filename only
- Model quality varies — always review before applying
- Very large files are truncated before sending to the model (see `--max-text-chars`)
- Sequential by default — classifying thousands of files takes time on a 16 GB Mac
```

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation, usage, and workflow guide"
```

---

## Final Verification

- [ ] **Run all tests**

```bash
pytest -v
```

Expected: all tests pass, no failures.

- [ ] **Verify CLI --help works for all commands**

```bash
python -m doc_cleaner --help
python -m doc_cleaner scan --help
python -m doc_cleaner apply --help
python -m doc_cleaner undo --help
python -m doc_cleaner doctor
```

- [ ] **Generate test docs and run doctor**

```bash
python test_docs/generate_test_docs.py
python -m doc_cleaner doctor
```

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: final verification pass"
```

---

## End-to-End Test (requires Ollama)

Once `ollama serve` is running and `qwen3.5:9b` is downloaded:

```bash
# Generate test documents
python test_docs/generate_test_docs.py

# Scan
python -m doc_cleaner scan \
  --input test_docs/generated \
  --output-root /tmp/sorted-test \
  --plan /tmp/test-plan.csv \
  --jsonl /tmp/test-plan.jsonl \
  --confidence-threshold 70

# Open /tmp/test-plan.csv, set approved=true on a few rows

# Apply
python -m doc_cleaner apply \
  --plan /tmp/test-plan.csv \
  --undo /tmp/undo-test.json

# Check results
ls /tmp/sorted-test/

# Undo
python -m doc_cleaner undo --undo-manifest /tmp/undo-test.json

# Verify originals restored
ls test_docs/generated/Finance/
```
