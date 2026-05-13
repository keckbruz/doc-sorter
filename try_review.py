"""Quick prototype test — run with: python3 try_review.py"""
from pathlib import Path
from doc_cleaner.review_table import ReviewRow, ReviewTableApp

rows = [
    ReviewRow(Path("test_input/Finance/allianz_beitragsrechnung.pdf"),
              "allianz_beitragsrechnung.pdf",
              Path("/tmp/out/Finance/Invoices/2024-03-12 - Allianz SE - Beitragsrechnung.pdf"),
              "2024-03-12 - Allianz SE - Beitragsrechnung.pdf", "Finance/Invoices", 95, False),
    ReviewRow(Path("test_input/Finance/amazon_quittung.txt"),
              "amazon_quittung.txt",
              Path("/tmp/out/Finance/Receipts/2024-02-15 - Amazon.de - Receipt.txt"),
              "2024-02-15 - Amazon.de - Receipt.txt", "Finance/Receipts", 95, False),
    ReviewRow(Path("test_input/Finance/finanzamt_steuerbescheid.pdf"),
              "finanzamt_steuerbescheid.pdf",
              Path("/tmp/out/Finance/Taxes/2024-01-20 - Finanzamt - Steuerbescheid.pdf"),
              "2024-01-20 - Finanzamt - Steuerbescheid.pdf", "Finance/Taxes", 95, False),
    ReviewRow(Path("test_input/Finance/sparkasse_kontoauszug.pdf"),
              "sparkasse_kontoauszug.pdf",
              Path("/tmp/out/Finance/Banking/2024-01-01 - Sparkasse - Kontoauszug.pdf"),
              "2024-01-01 - Sparkasse - Kontoauszug.pdf", "Finance/Banking", 95, False),
    ReviewRow(Path("test_docs/generated/edge_cases/deep_document.txt"),
              "deep_document.txt",
              Path("/tmp/out/Finance/Invoices/2024-01-01 - Unknown - Invoice.txt"),
              "2024-01-01 - Unknown - Invoice.txt", "Finance/Invoices", 60, True),
    ReviewRow(Path("test_docs/generated/edge_cases/ambiguous_letter.txt"),
              "ambiguous_letter.txt",
              Path("/tmp/out/Personal/Other/[no date] - Unknown - Other.txt"),
              "[no date] - Unknown - Other.txt", "Personal/Other", 60, True),
]

ReviewTableApp(rows, threshold=90, apply_callback=lambda r: print(f"\nWould apply: {[x.original_name for x in r]}")).run()
