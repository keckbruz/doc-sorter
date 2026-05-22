# DocSorter

A native macOS app that automatically classifies and organises your document folders using a local AI model. No cloud, no subscription, no data leaves your machine.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue) ![Xcode 15+](https://img.shields.io/badge/Xcode-15%2B-blue) ![Local AI](https://img.shields.io/badge/AI-local%20only-green)

---

## How it works

1. You pick an input folder and an output folder
2. DocSorter peeks at your documents and suggests a folder taxonomy tailored to your files
3. You confirm or adjust the taxonomy
4. It scans and classifies every file using a local AI model
5. You review the proposed moves in a table — edit categories, filenames, or exclude files
6. Apply moves the files. Undo brings them back.

All processing runs on your Mac. The AI model runs locally via [Ollama](https://ollama.com). Nothing is sent to any server.

---

## Requirements

- macOS 14 or later
- Xcode 15 or later
- [Homebrew](https://brew.sh)
- ~4 GB free disk space for the AI model

---

## Setup

### 1. Install Xcode

Download from the Mac App Store or [developer.apple.com](https://developer.apple.com/xcode/).

### 2. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/homebrew/install/HEAD/install.sh)"
```

### 3. Install Python and dependencies

```bash
brew install python
pip3 install pytesseract pillow pillow-heif ocrmypdf
```

### 4. Install Tesseract (OCR engine)

```bash
brew install tesseract tesseract-lang
```

`tesseract-lang` includes German, English, and many other languages. If you only need English:

```bash
brew install tesseract
```

### 5. Install Ollama and pull the AI model

```bash
brew install ollama
ollama serve &
ollama pull qwen3.5:9b
```

The model download is ~6 GB. Once pulled it stays on your machine and works offline.

### 6. Install the Python backend

```bash
git clone <repo-url>
cd doc-sorter
pip3 install -e .
```

### 7. Build the app

```bash
cd DocSorter
brew install xcodegen
xcodegen generate
open DocSorter.xcodeproj
```

In Xcode: press **Cmd+R** to build and run.

To use the app outside Xcode: go to **Products** folder in Xcode (right-click DocSorter.app → Show in Finder) and copy the app to `/Applications`.

---

## First run

1. Launch **DocSorter.app**
2. Click **Choose…** next to Input Folder and select the folder you want to sort
3. Click **Choose…** next to Output Folder and select where sorted files should go
4. Click **Start Scan**

The app will walk through three preparation steps:

| Step | What happens |
|------|-------------|
| **COUNTED** | Counts files instantly |
| **EMBEDDING** | Embeds searchable text into scanned PDFs (first run only — subsequent runs skip files already processed) |
| **PEEKING** | Reads document content to prepare taxonomy suggestions |

After peeking, it may suggest new folder categories based on your specific documents. Review and confirm, then the full classification scan begins.

---

## Review screen

Each file gets a row showing:
- Original filename → suggested new filename
- Category / Subcategory
- Confidence score (green ≥ 90%, amber 50–89%, red < 50%)

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate rows |
| `Enter` | Expand detail panel (edit category, subcategory, filename) |
| `Space` | Quick Look the file |
| `X` | Exclude from apply |

Check the rows you want to move, then click **Apply selected**.

---

## Apply & Undo

Clicking **Apply** moves the checked files to the output folder with their new names. An undo manifest is saved automatically.

If anything looks wrong, click **Undo** on the Done screen to restore all files to their original locations.

---

## OCR and scanned documents

DocSorter reads text from:

| File type | How |
|-----------|-----|
| Text-based PDF | Direct extraction — instant |
| Scanned PDF (image only) | OCR via Tesseract, then text is embedded permanently into the PDF |
| JPG / HEIC / PNG / TIFF | Tesseract OCR with automatic rotation correction |
| DOCX | Direct extraction |
| TXT / MD / CSV | Read directly |

**Automatic rotation correction:** If OCR produces sparse output (e.g. a photo taken sideways), the app detects the rotation angle and retries. Works for 90°, 180°, and 270° rotations.

**iPhone photos (HEIC):** EXIF orientation is applied automatically before OCR so portrait photos are read correctly.

**Scanned PDF embedding:** The first time DocSorter processes a folder of scanned PDFs, it embeds a searchable text layer into each one using [ocrmypdf](https://ocrmypdf.readthedocs.io). This is a one-time step — on all future scans those files are read instantly. It also makes them searchable in Spotlight and Preview.

**OCR timeout:** Each Tesseract call has a 30-second timeout. Files that cause Tesseract to hang are skipped gracefully and flagged in the debug log.

---

## Taxonomy

DocSorter uses a German-language taxonomy by default. Categories include:

| Category | Subcategories |
|----------|--------------|
| Finanzen | Bankwesen, Steuern, Versicherung, Geldanlage, Rechnungen, Quittungen |
| Verträge | Arbeitsvertrag, Mietvertrag, Dienstleistungsvertrag, Sonstiges |
| Behörden | Ausweise, Meldewesen, Bescheide, Sonstiges |
| Gesundheit | Arztberichte, Rechnungen, Versicherung, Rezepte |
| Arbeit | Gehaltsabrechnungen, Verträge, Zeugnisse, Bewerbungen |
| Bildung | Zertifikate, Hochschule, Kurse, Sonstiges |
| Wohnen | Miete, Nebenkosten, Internet, Anleitungen |
| Fahrzeuge | Versicherung, Wartung, Zulassung, Sonstiges |
| Persönliches | Briefe, Reise, Ausweise, Sonstiges |
| Medien | Fotos, Screenshots, Videos |
| Software | Lizenzen, Anleitungen |
| Archiv | — |
| Review | — (low-confidence files land here) |

Before each scan, the AI looks at your document set and suggests additional categories specific to your files.

---

## Filename convention

Sorted files are renamed to: `YYYY-MM_documenttype_sender.ext`

Examples:
- `2024-03_rechnung_vodafone.pdf`
- `2023-11_steuerbescheid_finanzamt-muenchen.pdf`
- `2017-03_führerschein_stadt-regensburg.heic`
- `gehaltsabrechnung_firma-gmbh.pdf` *(no date if unknown)*

---

## Troubleshooting

**Confidence is 0% for all image files**

Tesseract is probably not in the app's PATH. Make sure it's installed:
```bash
brew install tesseract tesseract-lang
which tesseract   # should print /opt/homebrew/bin/tesseract
```

**"Ollama is not running" error**

Start Ollama before scanning:
```bash
ollama serve
```
Or open the Ollama menu bar app if you installed it.

**Scan is very slow on a folder of old scanned PDFs**

Run the OCR embedding step first — this is a one-time cost that makes all future scans fast:
```bash
python3 ~/path/to/doc-sorter/embed_ocr.py ~/path/to/folder --output ~/path/to/folder-searchable
```
Verify a few output files in Preview (Cmd+F to search), then replace your originals.

**A file hangs during scanning**

The app has a 30-second timeout per file. If a specific file always hangs, check the debug log next to your plan file (`.debug.jsonl`) — it will show `"error": "ocr_timeout"` for that file.

**App shows "python3 not found"**

Make sure Python is installed via Homebrew and the backend is installed:
```bash
brew install python
pip3 install -e ~/path/to/doc-sorter
```

---

## Privacy

- No internet connection required after initial setup
- Document contents never leave your Mac
- The only network traffic is to `127.0.0.1:11434` (your local Ollama instance)
- No telemetry, no analytics, no accounts

---

## CLI usage

The Python backend also works standalone from the terminal. Run `doc-sorter --help` for all commands. Key commands:

```bash
doc-sorter scan --input ~/Downloads --output-root ~/Documents/Sorted --ocr
doc-sorter apply --plan plans/plan.csv --undo plans/undo.json
doc-sorter undo --undo-manifest plans/undo.json
doc-sorter embed-ocr --input ~/Downloads/Scans --output ~/Downloads/Scans-searchable
doc-sorter doctor
```
