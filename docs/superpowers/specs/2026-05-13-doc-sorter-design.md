# doc-sorter Design Spec
_Date: 2026-05-13_

## Overview

A local-first, privacy-preserving CLI tool for macOS that scans messy document folders, classifies each file using a local Ollama model, generates a human-reviewable move plan (CSV/JSONL), and only moves files when explicitly approved. No cloud services, no deletion, dry-run by default.

---

## Goals & Non-Goals

**Goals**
- Scan thousands of mixed files recursively
- Extract text locally (PDF, DOCX, TXT, MD; OCR optional)
- Classify each file via local Ollama into a fixed taxonomy
- Generate a reviewable CSV/JSONL plan
- Apply moves safely with undo support
- Work fully offline after initial setup

**Non-Goals (MVP)**
- No cloud APIs, no telemetry, no login
- No file deletion
- No image OCR in MVP (soft dependency, degraded mode)
- No SQLite history, no HTML review UI, no Finder tags
- No parallel Ollama calls

---

## Architecture

### Approach: Single-pass pipeline

`scan` processes files one-by-one: metadata → cache check → extract → prompt → classify → plan row. Results stream to CSV/JSONL as each file finishes. Reruns are cheap via the hash-based cache.

### Module layout

```
doc_cleaner/
  cli.py          ← typer app: scan, apply, undo, doctor commands
  config.py       ← Config dataclass (all flags + thresholds)
  taxonomy.py     ← load/validate YAML taxonomy, enforce allowed categories
  scanner.py      ← recursive walk, skip rules, FileMetadata + SHA-256 hash
  extractors/
    __init__.py   ← dispatcher: picks extractor by MIME/extension
    pdf.py        ← pypdf text extraction; hint if scanned/empty
    docx.py       ← python-docx
    text.py       ← .txt, .md, .csv summary
    image_ocr.py  ← pytesseract (soft optional dependency)
  classifier/
    ollama.py     ← sole network module; localhost-only guard
    prompts.py    ← prompt template + excerpt selection logic
    schema.py     ← Pydantic ClassificationResult model
  planner.py      ← target path generation, collision handling, CSV/JSONL writer
  applier.py      ← reads approved rows, moves files, writes undo manifest
  undo.py         ← reads undo manifest, moves files back
  cache.py        ← JSON cache keyed by hash + model + prompt_version
  utils.py        ← filename sanitize, path traversal guard, safe_move
  logging.py      ← local log file + rich stderr setup

tests/
  conftest.py           ← tmp dirs, mock_ollama fixture, fake doc fixtures
  test_schema.py
  test_filename_sanitize.py
  test_planner.py
  test_apply_no_overwrite.py
  test_taxonomy.py

test_docs/              ← generated fake document tree for end-to-end testing
  generate_test_docs.py ← script using fpdf2 + python-docx to create all fixtures
  Finance/
    2024-03-12 - Allianz - Beitragsrechnung.pdf
    2023-11-04 - Sparkasse - Kontoauszug.pdf
    2022-08-19 - Finanzamt München - Steuerbescheid.pdf
    receipt_amazon.txt
  Legal/
    2021-06-02 - Vermieter - Mietvertrag.docx
    unknown_contract.pdf
  Work/
    employment_contract_draft.docx
  Education/
    university_certificate.pdf
  Health/
    hospital_bill.pdf
  edge_cases/
    ambiguous_letter.txt        ← no date, no sender, vague content
    no_date_invoice.pdf         ← invoice without readable date
    duplicate_a.pdf             ← identical content to duplicate_b.pdf
    duplicate_b.pdf
    empty.txt                   ← zero bytes
    image_scan.png              ← image of text (tests OCR path)
    deeply/nested/subfolder/doc.txt
  mixed_formats/
    manual.pdf
    spreadsheet_summary.csv
    readme.md

taxonomy.yaml     ← default category tree
pyproject.toml
README.md
```

---

## Data Flow

### scan command

```
for each file in recursive_walk(input):
  1. scanner     → FileMetadata (path, size, sha256, dates, mime)
  2. cache        → hit? return cached result, skip 3–6
  3. extractor    → extracted text string (truncated to --max-text-chars)
  4. prompts      → build prompt:
                    first_n (1500) + last_n (500) chars
                    + lines matching date/sender/invoice keyword patterns (≤20)
  5. ollama       → POST /api/generate → raw string
  6. schema       → parse + validate ClassificationResult
                    retry once on invalid JSON with stricter repair prompt
                    if still invalid → status=error, category=Review
  7. planner      → safe_target_path(), collision check, write CSV/JSONL row
  8. cache        → persist result

  on any unhandled error → write error row, continue to next file
```

### apply command

```
1. read CSV rows where approved=true
2. verify source exists + hash still matches
3. print summary (file count, output root, undo path), confirm unless --yes
4. for each row:
   a. compute collision-safe target (append " (2)" / 6-char hash suffix)
   b. create parent directories
   c. os.rename or shutil.move (never overwrite)
   d. append entry to undo manifest
5. write undo-YYYY-MM-DD-HH.json + undo.sh
```

### undo command

```
1. read undo manifest
2. for each entry: move target → original
   skip (report conflict) if original already occupied
3. never overwrite, report all conflicts at end
```

---

## Key Components

### ollama.py — network boundary

- Only module that makes HTTP requests
- Default host: `http://127.0.0.1:11434`
- Non-localhost host requires `--allow-remote-ollama` flag + prints warning
- On server not running: clear error + `ollama serve` hint, exit non-zero
- Timeout configurable, retry only on transient network errors (not on bad JSON)
- Temperature: 0.1; JSON response format if model supports it

### prompts.py — excerpt selection

Sends: `first_n` chars + `last_n` chars + up to 20 lines matching patterns:
- Date patterns: `\d{1,2}[./]\d{1,2}[./]\d{2,4}`
- Sender/company patterns: known institution keywords
- Document type keywords: Rechnung, Kontoauszug, Vertrag, Bescheid, Invoice, etc.

`PROMPT_VERSION = "v1"` constant — changing it busts all caches automatically.

### schema.py — ClassificationResult

```python
class ClassificationResult(BaseModel):
    category: str
    subcategory: str | None
    document_date: str | None       # ISO date or null
    sender: str | None
    document_type: str | None
    suggested_filename: str
    confidence: int                  # 0–100
    reason: str
    needs_review: bool
```

Validation: confidence clamped 0–100; category must be in taxonomy or forced to "Review"; `needs_review` forced true if confidence < threshold.

### planner.py — safe_target_path

```
target = output_root / category / subcategory / sanitized_filename
assert target.resolve().is_relative_to(output_root.resolve())
```

Model never produces a path used directly. All path construction happens in code.

### utils.py — filename sanitization

- Strip forbidden macOS chars: `: / \ * ? " < > |`
- Normalize whitespace
- Cap at 200 chars (macOS safe)
- Format: `YYYY-MM-DD - Sender - DocumentType.ext`
- If no date: `undated - Sender - DocumentType.ext`
- If uncertain: preserve more of original filename

---

## Safety Guarantees

| Guarantee | Mechanism |
|---|---|
| No files moved in scan | `scan` has no move code |
| No accidental apply | `apply` requires explicit `--apply` flag |
| No overwrite | target existence checked before every move |
| No path escape | `resolve().is_relative_to()` enforced in planner |
| No data loss | original stays until move confirmed; undo manifest always written |
| No cloud calls | `ollama.py` is sole network module, localhost-only by default |
| No deletion | no `os.remove`, `shutil.rmtree`, or `unlink` anywhere in codebase |

---

## End-to-End Test Folder

`test_docs/generate_test_docs.py` generates a realistic fake document tree using `fpdf2` (PDFs) and `python-docx` (DOCX). Running it requires no Ollama — it just creates files. Once Ollama is available, a full end-to-end run looks like:

```bash
# Generate fake docs
python test_docs/generate_test_docs.py

# Dry-run scan
python -m doc_cleaner scan \
  --input ./test_docs \
  --output-root /tmp/sorted-test \
  --plan /tmp/test-plan.csv \
  --jsonl /tmp/test-plan.jsonl

# Review /tmp/test-plan.csv, set approved=true on some rows

# Apply
python -m doc_cleaner apply \
  --plan /tmp/test-plan-reviewed.csv \
  --undo /tmp/undo-test.json

# Undo
python -m doc_cleaner undo --undo-manifest /tmp/undo-test.json
```

**Edge cases covered by test_docs:**
- Ambiguous content → should land in Review
- No date → `undated` in filename
- Duplicate hashes → marked as duplicate in plan
- Empty file → error row, no crash
- Deeply nested subfolder → scanned correctly
- Image file → OCR attempted (or flagged if unavailable)

---

## Testing (Unit)

All unit tests use `pytest` + `tmp_path`. No real documents. No Ollama required. `mock_ollama` fixture returns canned JSON.

| Test file | Covers |
|---|---|
| `test_schema.py` | Bad JSON rejected; confidence clamped; needs_review forced below threshold |
| `test_filename_sanitize.py` | Forbidden chars, length cap, `undated`, whitespace normalization |
| `test_planner.py` | Dry-run writes no files; collision → ` (2)`; path traversal → Review |
| `test_apply_no_overwrite.py` | Existing target skipped; undo manifest written; `approved=false` skipped |
| `test_taxonomy.py` | Unknown category rejected; Review always valid; YAML loads |

---

## CLI Commands & Key Flags

```
scan   --input --output-root --model --ollama-host --plan --jsonl
       --dry-run --confidence-threshold (default 90) --max-files --max-depth
       --include-hidden --follow-symlinks (default false) --ocr/--no-ocr
       --ocr-language (default deu+eng) --workers --max-text-chars
       --cache-dir --taxonomy --verbose --quiet --limit

apply  --plan --undo --yes --apply-all-above-threshold --allow-remote-ollama

undo   --undo-manifest

doctor (no required flags)
```

---

## MVP Scope

**In MVP:**
- scan, apply, undo, doctor commands
- PDF + DOCX + TXT/MD extraction
- Ollama classification with retry
- CSV + JSONL plan output
- Undo manifest + shell script
- Hash-based cache
- Unit tests (5 files)
- End-to-end test_docs folder + generate script
- README
- taxonomy.yaml

**Deferred:**
- OCR / image OCR (soft dependency, degraded mode only)
- Duplicate detection
- HTML review UI
- SQLite history
- Finder tags / Hazel / AppleScript integration
- Parallel Ollama calls

---

## Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "typer[all]",
  "pydantic>=2",
  "rich",
  "httpx",
  "pypdf",
  "python-docx",
  "pillow",
  "python-magic",
]

[project.optional-dependencies]
ocr = ["pytesseract"]
dev = ["pytest", "fpdf2", "python-docx"]
```

---

## Privacy Model

All processing is local. The only outbound connection is to `http://127.0.0.1:11434` (Ollama). No API keys, no accounts, no telemetry. The tool can run fully offline once Ollama and models are installed. Document text is never written to logs by default.
