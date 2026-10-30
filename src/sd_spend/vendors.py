"""Turn the City's yearly 'Cumulative Amounts Paid to Vendors' PDFs into tidy rows.

The PDFs print no totals, so correctness rests on strictness: any line that is not a header, a page
footer or a payment row raises ExtractionError instead of being skipped.
"""
import gzip
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

MIN_AMOUNT = 25000


class ExtractionError(AssertionError):
    pass


ROW = re.compile(r"^\s*(\d{8,10})\s+(.+?)\s+(-?\$?\s?[\d,]+(?:\.\d{1,2})?)\s*$")
HEADER = re.compile(r"^(City of San Diego|Cumulative Amounts Paid|Fiscal Year \d{4}|Vendor\s+Vendor Name)")
FISCAL_YEAR = re.compile(r"Fiscal Year (\d{4})")
PAGE = re.compile(r"^Page \d+ of (\d+)$")


def parse_report(text: str) -> tuple[int, pd.DataFrame, dict]:
    match = FISCAL_YEAR.search(text)
    if match is None:
        raise ExtractionError("no 'Fiscal Year' line found")
    rows, unmatched, page_totals = [], [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or HEADER.match(stripped):
            continue
        page = PAGE.match(stripped)
        if page:
            page_totals.append(int(page.group(1)))
            continue
        row = ROW.match(line)
        if row:
            rows.append((row.group(1).lstrip("0"), " ".join(row.group(2).split()),
                         float(re.sub(r"[^\d.\-]", "", row.group(3)))))
        else:
            unmatched.append(stripped)
    frame = pd.DataFrame(rows, columns=["vendor_id", "vendor_name", "amount"])
    info = {"unmatched": unmatched, "pages_declared": max(page_totals, default=0),
            "pages_seen": len(page_totals)}
    return int(match.group(1)), frame, info


def parse_and_validate(text: str) -> tuple[int, pd.DataFrame]:
    fy, df, info = parse_report(text)
    if info["unmatched"]:
        raise ExtractionError(f"FY{fy}: {len(info['unmatched'])} unrecognised lines, first: {info['unmatched'][:3]}")
    if info["pages_seen"] == 0 or info["pages_seen"] != info["pages_declared"]:
        raise ExtractionError(f"FY{fy}: saw {info['pages_seen']} page footers but the report declares "
                              f"{info['pages_declared']} pages")
    if df.empty:
        raise ExtractionError(f"FY{fy}: no rows parsed")
    dup = df.loc[df["vendor_id"].duplicated(), "vendor_id"].tolist()
    if dup:
        raise ExtractionError(f"FY{fy}: duplicate vendor ids {dup[:5]}")
    small = df[df["amount"] < MIN_AMOUNT]
    if len(small):
        raise ExtractionError(f"FY{fy}: {len(small)} amounts below $25,000 (the report's threshold), "
                              f"first: {small.iloc[0].to_dict()}")
    return fy, df


def pdf_to_text(gz_path) -> str:
    """Text of a gzipped PDF via `pdftotext -layout` (poppler). The PDF is untrusted input: it is only
    ever passed to pdftotext as a file argument."""
    if shutil.which("pdftotext") is None:
        raise ExtractionError("pdftotext is required: `brew install poppler` or `apt install poppler-utils`")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "report.pdf"
        pdf.write_bytes(gzip.decompress(Path(gz_path).read_bytes()))
        result = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                                capture_output=True, text=True)
    return result.stdout
