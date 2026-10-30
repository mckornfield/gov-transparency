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


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))


def combine(reports: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """One row per (fiscal year, vendor). Vendors are the same when their names match ignoring case,
    punctuation and '&' vs 'and' (the City sometimes lists one company under several vendor ids)."""
    rows = pd.concat([df.assign(fy=fy) for fy, df in reports.items()], ignore_index=True)
    key = rows["vendor_name"].map(name_key)
    rows["vendor_key"] = key.where(key != "", "id" + rows["vendor_id"])
    latest_name = (rows.sort_values(["fy", "amount"]).groupby("vendor_key").tail(1)
                   .set_index("vendor_key")["vendor_name"])
    grouped = rows.groupby(["fy", "vendor_key"], as_index=False).agg(
        vendor_ids=("vendor_id", lambda s: "; ".join(sorted(set(s)))), amount=("amount", "sum"))
    grouped["vendor_name"] = grouped["vendor_key"].map(latest_name)
    return (grouped[["fy", "vendor_key", "vendor_name", "vendor_ids", "amount"]]
            .sort_values(["fy", "amount"], ascending=[True, False]).reset_index(drop=True))


def coverage(vendor_totals: pd.Series, spending: pd.DataFrame) -> dict[int, dict]:
    totals = spending.groupby(["basis", "fy"])["amount"].sum()
    out = {}
    for fy, paid in vendor_totals.items():
        basis = next((b for b in ("actual", "adopted") if (b, fy) in totals.index), None)
        if basis is None:
            raise ExtractionError(f"no City spending total for FY{fy} to compare vendor payments against")
        out[int(fy)] = {"vendors_total": float(paid), "reference_total": float(totals[(basis, fy)]),
                        "reference_basis": basis}
    return out


def check_coverage(cov: dict, low: float = 0.4, high: float = 1.1) -> None:
    """Vendor payments cannot be reconciled to a printed total (the PDFs have none), so require that
    they land in a plausible share of the City's own spending. A dropped page or a double count falls
    outside the band."""
    bad = {fy: round(c["vendors_total"] / c["reference_total"], 2) for fy, c in cov.items()
           if not low <= c["vendors_total"] / c["reference_total"] <= high}
    if bad:
        raise ExtractionError(f"vendor payments are outside {low:.0%}-{high:.0%} of City spending: {bad}")
