"""Raw vendor-payment PDFs -> data/processed/vendor_payments.csv and site/data/vendors.json.

Needs poppler's `pdftotext` (brew install poppler / apt install poppler-utils). Fails
(ExtractionError) rather than writing numbers that do not look right; do not loosen the checks in
sd_spend.vendors to make it pass, investigate the PDFs and tell the user.
"""
import json

import pandas as pd

from sd_spend import export, vendors
from sd_spend.io import RAW, ROOT

YEARS = range(2022, 2027)
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def main() -> None:
    reports = {}
    for fy in YEARS:
        got_fy, df = vendors.parse_and_validate(
            vendors.pdf_to_text(RAW / "sandiego" / f"vendor_payments_fy{fy}.pdf.gz"))
        if got_fy != fy:
            raise vendors.ExtractionError(f"vendor_payments_fy{fy}.pdf.gz is a report for FY{got_fy}")
        reports[fy] = df
        print(f"FY{fy}: {len(df):>5} rows  ${df['amount'].sum() / 1e6:>8,.1f}M")
    table = vendors.combine(reports)
    spending = pd.read_csv(PROCESSED / "spending.csv")
    cov = vendors.coverage(table.groupby("fy")["amount"].sum(), spending)
    vendors.check_coverage(cov)
    table.to_csv(PROCESSED / "vendor_payments.csv", index=False)
    (SITE_DATA / "vendors.json").write_text(
        json.dumps(export.vendors_payload(table, cov), separators=(",", ":")) + "\n")
    for fy, c in cov.items():
        print(f"FY{fy}: vendor payments are {c['vendors_total'] / c['reference_total']:.0%} of {c['reference_basis']} spending")


if __name__ == "__main__":
    main()
