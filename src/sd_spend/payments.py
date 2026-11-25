"""The City of San Diego's accounts-payable transaction detail (Public Records Act request 26-11538): one row per
payment line with vendor, date, amount, department, fund and spending type. Parsers fail loudly on a layout they do
not recognise."""
import csv
import io
import re
from datetime import date

import pandas as pd

HEADER = ["Vendor", "Vendor Name", "Payment Date", "Payment Document", "Payment Amount", "Purchase Order",
          "Department", "Department Name", "Fund", "Fund Name", "Commitment Item Group"]
NAMED_MINIMUM = 25_000  # the City publishes vendor names only for payees paid this much in a fiscal year
NO_TYPE = "Not given"


class PaymentsError(ValueError):
    pass


def fiscal_year(day: date) -> int:
    """City fiscal years run July to June and are named by the year they end."""
    return day.year + 1 if day.month >= 7 else day.year


def parse_payments(text: str) -> pd.DataFrame:
    """Tab-separated payment lines (header first, as stored in data/raw) -> one row per payment line."""
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = [h.strip() for h in next(reader, [])]
    if header != HEADER:
        raise PaymentsError(f"payments file has unexpected columns: {header}")
    out = []
    for n, r in enumerate(reader, start=2):
        if len(r) != len(HEADER):
            raise PaymentsError(f"payments line {n} has {len(r)} fields, not {len(HEADER)}")
        try:
            day = date.fromisoformat(r[2])
            amount = float(r[4])
        except ValueError as e:
            raise PaymentsError(f"payments line {n}: {e}") from None
        if not re.fullmatch(r"\d+", r[0]) or not r[7].strip() or not r[9].strip():
            raise PaymentsError(f"payments line {n} has no vendor id, department or fund")
        out.append((r[0], r[1].strip(), day, fiscal_year(day), amount, r[6], r[7].strip(), r[8], r[9].strip(), r[10].strip() or NO_TYPE))
    if not out:
        raise PaymentsError("payments file has no rows")
    named: dict[str, str] = {}
    for vendor, name, *_ in out:
        if name and named.setdefault(vendor, name) != name:
            raise PaymentsError(f"vendor id {vendor} has two names: {named[vendor]!r} and {name!r}")
    return pd.DataFrame(out, columns=["vendor_id", "vendor_name", "date", "fy", "amount", "dept_code", "dept", "fund_code", "fund", "type"])


def unnamed_years(rows: list[list[str]]) -> set[tuple[str, int]]:
    """(vendor id, fiscal year) pairs paid less than NAMED_MINIMUM that year (rows are raw lines: id, name, ISO date,
    document, amount, ...). Fails if one id carries two names: the City reuses ids, and money must not be misattributed."""
    totals: dict[tuple[str, int], float] = {}
    names: dict[str, str] = {}
    for r in rows:
        if names.setdefault(r[0], r[1]) != r[1]:
            raise PaymentsError(f"vendor id {r[0]} has two names: {names[r[0]]!r} and {r[1]!r}")
        key = (r[0], fiscal_year(date.fromisoformat(r[2])))
        totals[key] = totals.get(key, 0.0) + float(r[4])
    return {key for key, amount in totals.items() if amount < NAMED_MINIMUM}


# Rough grouping of the City's ~480 funds by name, for "which money paid": checked in this order.
FUND_CLASSES = [
    ("Borrowed money (bonds and loans)", re.compile(r"DEBT FUNDED|COMM PAPER|WIFIA|LOAN|\bSRF\b|BOND")),
    ("Grants", re.compile(r"GRANT|CDBG|COVID-19|STATE COPS")),
    ("Water and sewer", re.compile(r"WATER|SEWER")),
]
GENERAL_FUND = "General fund"
OTHER_FUNDS = "Other city funds"
FUNDS = [GENERAL_FUND, "Water and sewer", "Grants", "Borrowed money (bonds and loans)", OTHER_FUNDS]


def fund_class(code: str, name: str) -> str:
    """General fund (codes 1000xx), water and sewer, grants, borrowed money, or other city funds."""
    for label, pattern in FUND_CLASSES:
        if pattern.search(name.upper()):
            return label
    return GENERAL_FUND if code.startswith("1000") else OTHER_FUNDS
