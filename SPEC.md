Build a local-first document cleanup CLI for macOS.

Goal
Create a privacy-preserving command-line tool that helps me clean up years of messy local files. The tool should scan an input folder, extract document metadata/text locally, classify each file using a local Ollama model, generate a reviewable CSV/JSON move plan, and only move/rename files when explicitly approved.

The tool must never send document contents, filenames, extracted text, or metadata to any cloud service. It may only call a local Ollama server at http://127.0.0.1:11434.

Context
I am on macOS, Apple Silicon, using Ollama locally. I will probably use models such as:
- qwen3.5:9b
- gemma4:e4b
- qwen2.5-coder:7b

Primary use case
I have folders such as Downloads, Desktop, Documents, iCloud Drive, and old archive folders that contain mixed PDFs, scans, receipts, bank documents, insurance letters, legal documents, manuals, screenshots, images, and random files. I want a safe way to classify, rename, and move them into a clean folder structure.

Hard privacy requirements
- Do not use OpenAI, Anthropic, Google Gemini, cloud OCR, cloud embeddings, telemetry, analytics, or any external AI API.
- Do not make external network requests except to http://127.0.0.1:11434 for Ollama.
- The tool must be usable offline after dependencies and models are installed.
- Do not send real document content anywhere except local Ollama.
- Do not require a login.
- Do not upload logs.
- Do not silently collect usage data.

Hard safety requirements
- Never delete files.
- Never overwrite files.
- Default mode must be dry-run.
- Moving/renaming requires an explicit --apply flag.
- Before applying changes, generate a human-reviewable move plan.
- Every apply run must create an undo script or undo manifest.
- Low-confidence or ambiguous files must go to a Review category.
- The tool must preserve original files until moves are explicitly applied.
- Use collision-safe filenames, e.g. append " (2)" or a short hash if a target already exists.
- Symlinks should not be followed by default.
- Hidden/system folders should be skipped by default.
- Package/library folders such as node_modules, .git, Library, Applications, System, virtualenvs, and caches should be skipped unless explicitly included.

Core features
1. Scan a folder recursively.
2. Collect basic file metadata:
   - original absolute path
   - relative path
   - filename
   - extension
   - file size
   - created date if available
   - modified date
   - MIME/type guess
   - file hash, preferably SHA-256 or fast hash option
3. Extract text locally from supported files:
   - PDF text extraction
   - OCR fallback for scanned PDFs/images
   - plain text
   - markdown
   - docx
   - optional: xlsx/csv summary
   - optional: email files if simple support is feasible
4. For images/screenshots:
   - OCR text if possible
   - basic metadata
   - no cloud image processing
5. Classify each file using Ollama.
6. Generate suggested:
   - category
   - subcategory
   - document date
   - sender/company/person
   - document type
   - target folder
   - target filename
   - confidence score
   - reason
7. Write a review plan:
   - CSV
   - JSONL
   - optionally Markdown summary
8. Apply approved moves:
   - read reviewed CSV/JSONL
   - only move rows with approved=true or confidence above configured threshold
   - create folders
   - use safe move semantics
   - never overwrite
   - create undo manifest/script
9. Support iterative workflow:
   - scan/classify dry-run
   - review CSV
   - apply reviewed plan
   - undo if needed

Desired folder taxonomy
Use a configurable taxonomy. Start with this default:

Documents/
  Finance/
    Banking/
    Taxes/
    Insurance/
    Investments/
    Invoices/
    Receipts/
  Legal/
    Contracts/
    Government/
    Court/
    Other/
  Work/
    Employment/
    Projects/
    Applications/
    Other/
  Education/
    University/
    Certificates/
    Courses/
    Other/
  Health/
    Bills/
    Reports/
    Insurance/
    Other/
  Household/
    Rent/
    Utilities/
    Internet/
    Manuals/
    Other/
  Vehicles/
    Insurance/
    Maintenance/
    Registration/
    Other/
  Personal/
    Letters/
    Travel/
    Identity/
    Other/
  Media/
    Photos/
    Screenshots/
    Videos/
  Software/
    Licenses/
    Manuals/
  Archive/
  Review/
  Duplicates/

Important: the model may only choose from configured categories/subcategories. If unsure, use Review.

Filename convention
Default suggested filename:

YYYY-MM-DD - Sender - Document Type.ext

Examples:
2024-03-12 - Allianz - Beitragsrechnung.pdf
2023-11-04 - Sparkasse - Kontoauszug.pdf
2022-08-19 - Finanzamt München - Steuerbescheid.pdf
2021-06-02 - Vermieter - Mietvertrag.pdf

Rules:
- Use ISO date if a reliable date is found.
- If no reliable date is found, use "undated".
- Keep original extension.
- Keep filenames under macOS-safe length.
- Remove forbidden/problematic characters.
- Normalize whitespace.
- Do not invent sender/date/document type if not present.
- If uncertain, preserve more of the original filename.

Classification output schema
The Ollama model must return strict JSON only:

{
  "category": "Finance",
  "subcategory": "Insurance",
  "document_date": "2024-03-12",
  "sender": "Allianz",
  "document_type": "Beitragsrechnung",
  "suggested_filename": "2024-03-12 - Allianz - Beitragsrechnung.pdf",
  "confidence": 92,
  "reason": "The text contains Allianz and states it is a premium invoice dated 12.03.2024.",
  "needs_review": false
}

Required behavior:
- confidence must be integer 0-100
- needs_review must be true if confidence < threshold
- if no category is reliable, category must be "Review"
- if date is unknown, document_date must be null
- if sender is unknown, sender must be null
- no markdown in model response
- no commentary outside JSON

Prompting strategy
Create a robust prompt template for Ollama. It should provide:
- the fixed allowed categories
- filename
- path hint, but warn that path may be unreliable
- extracted text excerpt
- metadata
- strict JSON schema
- instruction to prefer Review when unsure
- instruction not to hallucinate missing details

The prompt should explicitly say:
"Return valid JSON only. Do not include markdown. Do not include explanations outside the JSON object."

For long documents:
- Do not send entire very long documents by default.
- Send a controlled excerpt:
  - first N characters
  - maybe last N characters
  - selected lines containing date-like patterns, sender-like patterns, invoice/account/policy/contract keywords
- Make N configurable.
- Default should be conservative to fit local context and keep performance reasonable.

Ollama API
Use Ollama local API:
- host default: http://127.0.0.1:11434
- model default: qwen3.5:9b
- allow --model override
- use JSON/structured output if supported
- handle server not running with a clear error:
  "Ollama is not running. Start it with: ollama serve"
- allow timeout config
- retry only safe transient failures
- cache results by file hash + model + prompt version so reruns do not reclassify unchanged files

CLI design
Use Python.

Command examples:

1. Scan and classify dry-run:
python -m doc_cleaner scan \
  --input ~/Downloads \
  --output-root ~/Documents/Sorted \
  --model qwen3.5:9b \
  --plan ./plans/downloads-plan.csv \
  --jsonl ./plans/downloads-plan.jsonl

2. Apply reviewed plan:
python -m doc_cleaner apply \
  --plan ./plans/downloads-plan-reviewed.csv \
  --undo ./plans/undo-2026-05-13.sh

3. Undo:
python -m doc_cleaner undo \
  --undo-manifest ./plans/undo-2026-05-13.json

4. Test Ollama:
python -m doc_cleaner doctor

5. Classify only first 50 files:
python -m doc_cleaner scan \
  --input ~/Downloads \
  --limit 50 \
  --dry-run

Important flags:
--input
--output-root
--model
--ollama-host
--plan
--jsonl
--dry-run
--apply
--confidence-threshold, default 90
--max-files
--max-depth
--include-hidden
--follow-symlinks, default false
--ocr / --no-ocr
--ocr-language, default deu+eng if available
--workers
--max-text-chars
--cache-dir
--taxonomy config path
--verbose
--quiet

Implementation language and libraries
Use Python 3.11+.

Suggested libraries:
- typer or click for CLI
- pydantic for schemas/validation
- rich for console output
- httpx or requests for Ollama API
- pypdf or pymupdf for PDF text extraction
- python-docx for docx
- pillow for images
- pytesseract or OCRmyPDF/Tesseract integration for OCR
- python-magic or mimetypes for type detection
- pandas optional for CSV handling, but plain csv module is fine
- pytest for tests

Prefer simple and robust dependencies. If OCR dependencies are hard, make OCR optional and provide clear install instructions.

Architecture
Use a clean modular structure:

doc_cleaner/
  __init__.py
  cli.py
  config.py
  scanner.py
  extractors/
    __init__.py
    pdf.py
    docx.py
    text.py
    image_ocr.py
  classifier/
    __init__.py
    ollama.py
    prompts.py
    schema.py
  planner.py
  applier.py
  undo.py
  taxonomy.py
  cache.py
  logging.py
  utils.py
tests/
  test_schema.py
  test_filename_sanitize.py
  test_planner.py
  test_apply_no_overwrite.py
  test_taxonomy.py
README.md
pyproject.toml

Scan phase behavior
For every candidate file:
1. Skip unsupported/system/ignored files.
2. Compute metadata and hash.
3. Check cache.
4. Extract text.
5. Build classification prompt.
6. Call Ollama.
7. Validate JSON with Pydantic.
8. If invalid JSON, retry once with stricter repair prompt.
9. If still invalid, mark as Review.
10. Generate target folder and filename.
11. Check for collisions.
12. Write row to plan.

Plan CSV columns
Required CSV columns:

approved
status
original_path
target_path
category
subcategory
document_date
sender
document_type
suggested_filename
confidence
needs_review
reason
file_size
file_hash
modified_time
extractor
model
error

Defaults:
- approved=false for all rows, or approved=true only for confidence >= threshold if configured
- status=planned, review, error, duplicate, skipped

Apply phase behavior
The apply command must:
1. Read plan.
2. Only apply rows with approved=true unless --apply-all-above-threshold is specified.
3. Confirm summary unless --yes is passed.
4. Create target directories.
5. Move using safe collision handling.
6. Never overwrite.
7. Log every move.
8. Write undo manifest.
9. Write undo shell script.
10. Leave errors in place and continue safely.

Undo behavior
Undo should:
- move files back to original paths if possible
- never overwrite current files
- report conflicts clearly
- not delete directories unless empty and explicitly safe
- be idempotent where possible

Duplicate detection
Implement optional duplicate detection:
- same SHA-256 hash = duplicate candidate
- do not delete duplicates
- move duplicate candidates to Duplicates or mark in plan
- keep original paths visible
- let user decide later

OCR behavior
OCR is optional but useful.
If Tesseract/OCRmyPDF is not installed:
- do not crash
- mark scanned image/PDF as "needs OCR"
- classify based on filename/path only with lower confidence
- provide install hint in doctor command

Doctor command
Implement:
python -m doc_cleaner doctor

It should check:
- Python version
- Ollama reachable at localhost
- selected model installed or available
- Tesseract availability
- OCR languages available
- PDF extractor import
- write permission for plan/output directories
- macOS platform info

Logging
Create local logs only.
Log:
- scanned files count
- skipped files count
- errors
- model used
- execution time
- apply operations
Do not log full document text by default.
Allow --debug-text-dumps only for development, default false.

Security / privacy guardrails in code
- Centralize network calls in one module.
- That module must only allow localhost / 127.0.0.1 Ollama hosts by default.
- If a non-localhost host is provided, require explicit --allow-remote-ollama and show a warning.
- Do not include cloud API SDKs.
- Add README section explaining privacy model.

Performance
- Must handle thousands of files.
- Use incremental caching.
- Avoid loading huge files fully into memory.
- Allow --limit and --max-files for testing.
- Process sequentially by default for model stability; optional limited parallelism for extraction.
- Avoid parallel Ollama requests by default on 16 GB Mac.

Quality controls
- Use deterministic-ish model settings where possible:
  - low temperature, e.g. 0.1 or 0.2
  - JSON response format if supported
- Validate every model response.
- Do not trust model-suggested paths blindly.
- Sanitize category and filename.
- Force target path to remain inside output-root.
- Prevent path traversal.

Target path generation
The model should suggest category/subcategory and filename, but code should generate final target path.

Example:
output_root / category / subcategory / suggested_filename

Never let the model return arbitrary absolute paths that get used directly.

MVP scope
Build the MVP first:
- CLI
- scan command
- PDF/text/docx extraction
- Ollama classification
- CSV/JSONL plan
- apply command with undo manifest
- doctor command
- basic tests
- README

Nice-to-have later:
- OCR fallback
- image OCR
- duplicate detection
- small local HTML review UI
- Finder tags
- Hazel integration
- AppleScript/Shortcuts integration
- SQLite database for scan history
- automatic model comparison
- batch benchmark mode

Test data
Create fake sample documents only. Do not require real private documents.
Use text fixtures such as:
- fake Allianz insurance invoice
- fake bank statement
- fake tax assessment
- fake rental contract
- fake university certificate
- fake receipt
- ambiguous unknown letter

Include tests to verify:
- default dry-run does not move files
- apply does not overwrite existing files
- low confidence goes to Review
- invalid model JSON becomes Review
- target paths cannot escape output-root
- undo manifest is generated
- filename sanitization works
- duplicate hashes are detected if implemented

README requirements
The README should explain:
1. What the tool does.
2. Privacy model.
3. Installation.
4. Ollama setup:
   - ollama serve
   - ollama pull qwen3.5:9b
5. OCR setup if optional.
6. Example dry-run.
7. How to review CSV.
8. How to apply.
9. How to undo.
10. Limitations.
11. Recommended workflow:
   - start with copied test folder
   - dry-run first
   - review plan
   - apply small batches
   - keep backups

User experience
The CLI should print a clear summary:

Scanned: 428 files
Classified: 391
Needs review: 52
Errors: 7
Duplicates: 13
Plan written to: ./plans/downloads-plan.csv
No files were moved. Run apply after reviewing the plan.

During apply:
About to move 123 files.
Output root: ~/Documents/Sorted
Undo manifest: ./plans/undo-2026-05-13.json
Proceed? [y/N]

Do not proceed without confirmation unless --yes is passed.

Important coding instructions
- Keep code readable and maintainable.
- Prefer explicit safety checks over cleverness.
- Use type hints.
- Use Pydantic schemas for model output and plan rows.
- Add tests for dangerous operations.
- Do not implement deletion.
- Do not implement cloud integrations.
- Make dry-run the default everywhere.
- Make the first version small but working.

Deliverables
Please create:
- working Python package
- CLI commands
- tests
- README
- sample taxonomy config
- sample fake documents/fixtures
- example CSV plan
- implementation notes

Start by creating a minimal working version, then run tests, then improve.
