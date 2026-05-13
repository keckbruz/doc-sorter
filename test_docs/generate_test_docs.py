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
