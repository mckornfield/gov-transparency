"""Store the City's accounts-payable transaction detail from Public Records Act request 26-11538.

The City sent it to the requester as an Excel workbook; it is not downloadable from a public link. This turns the
workbook into a gzipped tab-separated file in data/raw/sandiego and records it in MANIFEST.csv. Names of payees that
were never paid $25,000 or more in a fiscal year are blanked (their vendor ids and amounts are kept): the City itself
publishes vendor names only above that line, and many small payees are private people.

    uv run python scripts/import_pra_payments.py "~/Downloads/PRA 26-11538 Accounts Payable Transaction Detail.xlsx"
"""
import csv
import io
import sys
from pathlib import Path

import openpyxl

from sd_spend.io import save_raw
from sd_spend.payments import HEADER, never_named

REL = "sandiego/pra_26_11538_ap_detail.tsv"
SOURCE = ("Public Records Act request 26-11538 to the City of San Diego: Department of Finance, Accounts Payable Transaction "
          "Detail 7/01/2021 to 9/30/2026, report dated 2026-11-20 (provided by the requester; names of payees never paid "
          "$25,000 or more in a fiscal year blanked)")


def cell(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)


def main(path: str) -> None:
    sheet = openpyxl.load_workbook(Path(path).expanduser(), read_only=True, data_only=True).worksheets[0]
    lines = sheet.iter_rows(values_only=True)
    title = [next(lines) for _ in range(6)]
    if "Accounts Payable Transaction Detail" not in str(title[1][0]) or "26-11538" not in str(title[2][0]):
        raise SystemExit("this is not the PRA 26-11538 accounts-payable workbook")
    header = [str(h).strip() for h in next(lines)]
    if header != HEADER:
        raise SystemExit(f"unexpected columns: {header}")
    rows = [[cell(v) for v in r] for r in lines if any(v is not None for v in r)]
    hidden = never_named(rows)
    for r in rows:
        if r[0] in hidden:
            r[1] = ""
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    save_raw(out.getvalue().encode(), REL, SOURCE)
    print(f"{len(rows):,} payment lines stored; {len(hidden):,} of {len({r[0] for r in rows}):,} payees' names blanked")


if __name__ == "__main__":
    main(sys.argv[1])
