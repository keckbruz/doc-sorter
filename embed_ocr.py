#!/usr/bin/env python3
"""Embed searchable OCR text into scanned PDFs in a folder.

Usage:
    python3 embed_ocr.py /path/to/folder
    python3 embed_ocr.py /path/to/folder --output /path/to/output
    python3 embed_ocr.py /path/to/folder --language eng
"""
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Add OCR text layer to scanned PDFs.")
    parser.add_argument("input", type=Path, help="Folder containing PDFs")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output folder (default: overwrite in place)")
    parser.add_argument("--language", "-l", default="deu+eng",
                        help="Tesseract language(s) (default: deu+eng)")
    parser.add_argument("--workers", "-w", type=int, default=4,
                        help="Parallel workers (default: 4)")
    args = parser.parse_args()

    try:
        import ocrmypdf
    except ImportError:
        print("ocrmypdf not installed. Run: pip install ocrmypdf")
        sys.exit(1)

    input_dir = args.input.expanduser().resolve()
    if not input_dir.is_dir():
        print(f"Not a directory: {input_dir}")
        sys.exit(1)

    output_dir = args.output.expanduser().resolve() if args.output else None
    if output_dir and output_dir != input_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in input_dir.rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        print("No PDF files found.")
        sys.exit(0)

    print(f"Found {len(pdfs)} PDF(s) in {input_dir}")
    print(f"Language: {args.language}")
    print(f"Output: {output_dir or 'in place'}")
    print()

    done = skipped = errors = 0
    for i, pdf in enumerate(pdfs, 1):
        dest = (output_dir / pdf.relative_to(input_dir)) if output_dir else pdf
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{i}/{len(pdfs)}] {pdf.name} ... ", end="", flush=True)
        try:
            result = ocrmypdf.ocr(
                pdf, dest,
                language=args.language,
                skip_text=True,
                progress_bar=False,
                jobs=args.workers,
            )
            if result == ocrmypdf.ExitCode.already_done_ocr:
                print("skipped (already has text)")
                skipped += 1
            else:
                print("done")
                done += 1
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1

    print()
    print(f"Embedded: {done}  |  Skipped: {skipped}  |  Errors: {errors}")


if __name__ == "__main__":
    main()
