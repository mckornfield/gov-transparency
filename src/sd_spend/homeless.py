"""Parsers for the homelessness sources. Strict: surprises raise HomelessError instead of being skipped.

- Cal ICH system performance measures CSV (people served, exits, days homeless, returns, point-in-time count)
- HCD HHAP allocation tables (pdftotext -layout text, three columns: CoC / city / county)
- City budget volumes (department expenditure and revenue totals)
- HUD point-in-time counts by CoC (.xlsb, one sheet per year)
"""
import csv
import io
import re

import pandas as pd

METRICS = {"M1a", "M1b", "M2", "M3", "M4", "M5", "M6", "PIT Count"}
FULL_COUNT = "Sheltered and Unsheltered Count"  # other 2021 types are sheltered-only or partial counts


class HomelessError(AssertionError):
    pass


def parse_spm(text: str) -> pd.DataFrame:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    periods = next(reader)[2:]
    rows = []
    for line in reader:
        if not line:
            continue
        location, metric, values = line[0], line[1], line[2:]
        if metric not in METRICS:
            raise HomelessError(f"unknown metric {metric!r} for {location}")
        if len(values) != len(periods):
            raise HomelessError(f"{location} {metric}: {len(values)} values for {len(periods)} periods")
        coc = re.match(r"CA-\d{3}", location)
        for period, raw in zip(periods, values):
            if raw.strip() in ("N/A", ""):  # not collected (waived 2021 count, small CoCs)
                value = float("nan")
            else:
                try:
                    value = float(raw)
                except ValueError:
                    raise HomelessError(f"{location} {metric} {period}: not a number: {raw!r}") from None
            rows.append((location, coc.group(0) if coc else None, metric, period, value))
    return pd.DataFrame(rows, columns=["location", "coc_id", "metric", "period", "value"])


AMOUNT = r"\$\s*(\d{1,3}(?:,\d{3})*\.\d{2}|-)"
MONEY = re.compile(r"(?:(\S.*?)\s+)?" + AMOUNT)
OLDER_COUNTS = re.compile(r"\*\s*Indicates jurisdictions approved to use (\d{4}) PIT counts")


def parse_hhap(text: str, round_label: str, default_year: int) -> pd.DataFrame:
    """Rows of kind 'coc' | 'city' | 'county', by the column each amount sits in under the header.

    `basis_year` is the point-in-time count the award was based on: `default_year`, except that where the table
    says a single * marks areas approved to use older counts, starred rows get that year. An amount whose name
    wrapped onto neighbouring lines is kept with an empty name rather than dropped.
    """
    header = next((l for l in text.splitlines() if "CONTINUUM OF CARE" in l and "CITY" in l and "COUNTY" in l), None)
    if header is None:
        raise HomelessError(f"{round_label}: no CONTINUUM OF CARE / CITY / COUNTY header line")
    older = OLDER_COUNTS.search(text)
    city_at, county_at = header.index("CITY") - 4, header.index("COUNTY") - 4
    rows = []
    for line in text.splitlines():
        if line is header:
            continue
        for match in MONEY.finditer(line):
            name = match.group(1) or ""
            if name:
                name = re.split(r"\s{2,}", name)[-1]  # a wrapped name's tail can precede this column's name
                start = match.end(1) - len(name)
            else:
                start = match.start(2) - 1
            kind = "county" if start >= county_at else "city" if start >= city_at else "coc"
            trimmed = name.rstrip()
            single = len(trimmed) - len(trimmed.rstrip("*")) == 1  # '**' and '***' mean other things
            basis = int(older.group(1)) if older and single else default_year
            raw = match.group(2)
            rows.append((round_label, kind, name.strip().rstrip("*").strip(),
                         0.0 if raw == "-" else float(raw.replace(",", "")), basis))
    out = pd.DataFrame(rows, columns=["round", "kind", "name", "amount", "basis_year"])
    for kind in ("coc", "city", "county"):
        if not out[(out.kind == kind) & out.name.str.startswith("San Diego")].shape[0]:
            raise HomelessError(f"{round_label}: no San Diego row in the {kind} column")
    return out


YEARS = re.compile(r"^\s*FY(\d{4})\s+FY(\d{4})\s+FY(\d{4})\s+FY\d{4}-\d{4}\s*$")
TOTAL = re.compile(r"^\s*Total Department (Expenditures|Revenue)\s+(.*)$")
NUMBER = re.compile(r"\(?\$?\s*[\d,]+\)?|(?<![\w,])-(?![\w,])")


def _numbers(cells: str) -> list[float]:
    out = []
    for token in NUMBER.findall(cells.replace("$", " ")):
        token = token.strip()
        out.append(0.0 if token == "-" else float(token.replace(",", "").replace("(", "-").replace(")", "")))
    return out


def parse_budget(text: str, require_title: bool = False) -> dict:
    """Totals for the department from the first 'FYxxxx Actual | Budget | Adopted' table in a budget volume.

    Every total line must carry exactly four cells (zero cells printed as '-' count) and the last, the change
    from budget to adopted, must equal the difference of the two before it. With `require_title` the table must
    sit under a 'Department Summary' heading.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = YEARS.match(line)
        if not (m and i + 1 < len(lines) and "Actual" in lines[i + 1]):
            continue
        if require_title and not any("Department Summary" in l for l in lines[max(0, i - 4):i]):
            raise HomelessError("the first Actual/Budget/Adopted table is not under a 'Department Summary' heading")
        years = [int(y) for y in m.groups()]
        found = {}
        for l in lines[i + 2:i + 14]:
            t = TOTAL.match(l)
            if t:
                nums = _numbers(t.group(2))
                if len(nums) != 4 or abs((nums[2] - nums[1]) - nums[3]) > 1:
                    raise HomelessError(f"department total line does not parse into four cells whose change adds up: {l.strip()!r}")
                found["expenditures" if t.group(1) == "Expenditures" else "revenue"] = dict(zip(years, nums[:3]))
        if set(found) == {"expenditures", "revenue"}:
            return {**found, "actual_year": years[0]}
    raise HomelessError("no department expenditure/revenue totals under an Actual/Budget/Adopted header")


def pit_rows(rows_by_year: dict[int, list[tuple]], coc_ids: list[str]) -> pd.DataFrame:
    """rows_by_year[year] = [(coc_id, count_type, total, sheltered, unsheltered)].

    A full sheltered+unsheltered count is a total. In years a CoC counted only its shelters, HUD fills the
    unsheltered figure with the CoC's last unsheltered count: that total is kept but flagged `carried`.
    With no unsheltered figure at all (the waived 2021 count) or only a partial count, the total is missing.
    Pre-2015 style sheets have no count type (None) and are treated as full counts.
    """
    out = []
    for year in sorted(rows_by_year):
        by_coc = {r[0]: r for r in rows_by_year[year]}
        for coc in coc_ids:
            if coc not in by_coc:
                if year >= 2019:
                    raise HomelessError(f"{coc} is missing from the {year} sheet")
                out.append((coc, year, None, None, None, False))
                continue
            _, count_type, total, sheltered, unsheltered = by_coc[coc]
            if count_type in (None, "", FULL_COUNT):
                out.append((coc, year, total, sheltered, unsheltered, False))
            elif count_type == "Sheltered-Only Count" and (unsheltered or 0) > 0:
                out.append((coc, year, total, sheltered, unsheltered, True))  # unsheltered count carried over
            else:
                out.append((coc, year, None, sheltered, None, False))
    df = pd.DataFrame(out, columns=["coc_id", "year", "total", "sheltered", "unsheltered", "carried"])
    return df.astype({c: "float64" for c in ("total", "sheltered", "unsheltered")})


def parse_hud_pit(xlsb_bytes: bytes, coc_ids: list[str]) -> pd.DataFrame:
    from pyxlsb import open_workbook

    rows_by_year = {}
    with open_workbook(io.BytesIO(xlsb_bytes)) as wb:
        for sheet in wb.sheets:
            if not re.fullmatch(r"20\d\d", sheet):
                continue
            with wb.get_sheet(sheet) as sh:
                rows = [[c.v for c in r] for r in sh.rows()]
            header = rows[0]
            need = ["CoC Number", "Overall Homeless", "Sheltered Total Homeless", "Unsheltered Homeless"]
            missing = [h for h in need if h not in header]
            if missing:
                raise HomelessError(f"sheet {sheet} lacks columns {missing}")
            idx = {h: header.index(h) for h in need}
            ct = header.index("Count Types") if "Count Types" in header else None
            rows_by_year[int(sheet)] = [
                (r[idx["CoC Number"]], r[ct] if ct is not None else None, r[idx["Overall Homeless"]],
                 r[idx["Sheltered Total Homeless"]], r[idx["Unsheltered Homeless"]])
                for r in rows[1:] if r and r[0] in coc_ids]
    return pit_rows(rows_by_year, coc_ids)
