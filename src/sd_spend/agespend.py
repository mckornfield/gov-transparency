"""Federal spending by age: parsers for the Treasury outlays, Census population, CMS age shapes and VA age bands.

Every parser fails loudly on a layout it does not recognise rather than returning a partial table.
"""
import csv
import io
import re


class AgeSpendError(ValueError):
    pass


def _money(text: str) -> float:
    return float(str(text).replace("[$$]", "").replace("$", "").replace(",", ""))


def parse_mts_outlays(payload: dict) -> dict[str, float]:
    """Outlay lines of Monthly Treasury Statement table 9 for one month's fiscal-year-to-date, by function."""
    rows = payload["data"]
    parents = [r["classification_id"] for r in rows if r["classification_desc"] == "Net Outlays"]
    if len(parents) != 1:
        raise AgeSpendError("Monthly Treasury Statement table 9 has no Net Outlays line")
    lines = {r["classification_desc"]: _money(r["current_fytd_rcpt_outly_amt"]) for r in rows if r["parent_id"] == parents[0]}
    if "Total" not in lines:
        raise AgeSpendError("Net Outlays has no Total line")
    parts = sum(v for k, v in lines.items() if k != "Total")
    if abs(parts - lines["Total"]) > 0.005 * lines["Total"]:
        raise AgeSpendError(f"outlay lines do not add up to the total ({parts:,.0f} against {lines['Total']:,.0f})")
    return lines


def parse_population(text: str, year: int, max_age: int = 100) -> dict[int, int]:
    """Both-sexes resident population by single year of age (the last age is 'and over')."""
    column = f"POPESTIMATE{year}"
    reader = csv.DictReader(io.StringIO(text))
    if column not in (reader.fieldnames or []):
        raise AgeSpendError(f"population file has no {year} column")
    people = {int(r["AGE"]): int(r[column]) for r in reader if r["SEX"] == "0"}
    for age in range(max_age + 1):
        if age not in people:
            raise AgeSpendError(f"population file has no age {age}")
    return {age: people[age] for age in range(max_age + 1)}


def parse_cms_shares(text: str, year: str, payers: tuple[str, ...], groups: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Each age group's share of a payer's total personal health care spending, both sexes."""
    rows = [r for r in csv.DictReader(io.StringIO(text)) if r["Service"] == "Total Personal Health Care" and r["Sex"] == "Total"]
    shares = {}
    for payer in payers:
        by_group = {r["Age Group"]: float(r[year]) for r in rows if r["Payer"] == payer}
        missing = [g for g in (*groups, "Total") if g not in by_group]
        if missing:
            raise AgeSpendError(f"CMS file has no {payer} rows for {missing}")
        total = by_group["Total"]
        if abs(sum(by_group[g] for g in groups) - total) > 0.005 * total:
            raise AgeSpendError(f"CMS {payer} age groups do not add up to the total")
        shares[payer] = {g: by_group[g] / total for g in groups}
    return shares


# VA publishes compensation and pension with different age bands and column names.
VA_LAYOUTS = {
    "Compensation": {"recipients": "Compensation Recipients", "dollars": "Estimated Annual Compensation Costs",
                     "unknown": "Compensation Veterans Age Unknown",
                     "bands": {"34 and under": "Compensation Veterans Age 34 and under", "35-54": "Compensation Veterans Age 35 - 54",
                               "55-74": "Compensation Veterans Age 55-74", "75 and over": "Compensation Veterans Age 75 and over"}},
    "Pension": {"recipients": "Veterans Pension Recipients", "dollars": "Estimated Annual Veteran's Pension Cost",
                "unknown": "Veterans Pension Age Unknown",
                "bands": {"34 and under": "Veterans Pension Age 34 and under", "35-64": "Veterans Pension Age 35 through 64",
                          "65-74": "Veterans Pension Age 65 through 74", "75 and over": "Veterans Pension Age 75 and over"}},
}


def parse_va_ages(text: str, kind: str) -> dict:
    """National recipients, annual dollars and age-band counts from a VA 'by state and age group' file."""
    layout = VA_LAYOUTS[kind]
    reader = csv.DictReader(io.StringIO(text))
    total = next((r for r in reader if r["State & Foreign"] == "Grand Total"), None)
    if total is None:
        raise AgeSpendError(f"VA {kind} file has no Grand Total row")
    recipients = int(total[layout["recipients"]])
    bands = {name: int(total[col]) for name, col in layout["bands"].items()}
    unknown = int(total[layout["unknown"]])
    if sum(bands.values()) + unknown != recipients:
        raise AgeSpendError(f"VA {kind} age bands do not add up to the recipients")
    return {"recipients": recipients, "dollars": _money(total[layout["dollars"]]), "bands": bands, "unknown": unknown}


ROW = re.compile(r"^\s*(Under \d+|\d+ or older|\d+–\d+|\d+)\s+([\d,]+)\s+([\d,]+\.\d\d)\b")


def parse_ssa_ages(text: str, title: str) -> list[dict]:
    """Age rows (first number column and its average monthly benefit) of one table of the SSA statistical supplement."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(rf"^\s*{re.escape(title)}(?!\d)", line)), None)
    if start is None:
        raise AgeSpendError(f"SSA supplement has no {title}")
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("SOURCE:"):
            break
        m = ROW.match(line)
        if not m:
            continue
        label = m.group(1)
        if label.startswith("Under"):
            lo = hi = int(label.split()[1]) - 1
        elif "or older" in label:
            lo = hi = int(label.split()[0])
        elif "–" in label:
            lo, hi = (int(x) for x in label.split("–"))
        else:
            lo = hi = int(label)
        rows.append({"lo": lo, "hi": hi, "number": int(m.group(2).replace(",", "")), "avg": float(m.group(3).replace(",", ""))})
    if not rows:
        raise AgeSpendError(f"SSA {title} has no age rows")
    return rows


def ssa_annual_dollars(rows: list[dict]) -> list[tuple[int, float]]:
    """(age, annual dollars) from monthly benefits times 12; a range row counts only if no single-year row lies in it."""
    singles = {r["lo"] for r in rows if r["lo"] == r["hi"]}
    out = []
    for r in rows:
        if r["lo"] != r["hi"] and any(r["lo"] <= a <= r["hi"] for a in singles):
            continue
        out.append((r["lo"], r["number"] * r["avg"] * 12))
    return out


def parse_omb_line(xlsx: bytes, prefix: str, year: int) -> float:
    """Dollars (the table is in millions) on the line of OMB table 3.2 starting with prefix, in the given year."""
    import openpyxl
    sheet = openpyxl.load_workbook(io.BytesIO(xlsx), data_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    header = next((r for r in rows if r and r[0] == "Function and Subfunction"), None)
    if header is None or str(year) not in [str(c) for c in header]:
        raise AgeSpendError(f"OMB table has no {year} column")
    col = [str(c) for c in header].index(str(year))
    for r in rows:
        if r and isinstance(r[0], str) and r[0].strip().startswith(prefix):
            if not isinstance(r[col], (int, float)):
                raise AgeSpendError(f"OMB line {prefix!r} has no number for {year}")
            return float(r[col]) * 1e6
    raise AgeSpendError(f"OMB table has no line starting {prefix!r}")


OTHER_ADULT_TYPES = ("Wives and husbands of retired workers", "Wives and husbands of disabled workers", "Nondisabled widow(er)s",
                     "Disabled widow(er)s", "Widowed mothers and fathers", "Parents of deceased workers")


def parse_ssa_other_adults(text: str) -> dict[str, float]:
    """Annual dollars (December monthly benefit times 12) of the adult types other than workers, by under 62, 62-64, 65 or older."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"^\s*Table 5\.A16", line)), None)
    if start is None:
        raise AgeSpendError("SSA supplement has no Table 5.A16")
    found = {}
    for line in lines[start + 1:]:
        if line.strip() == "Men":
            break
        cells = re.split(r"\s{2,}", line.strip())
        if cells[0] in OTHER_ADULT_TYPES and len(cells) == 9:
            number = [0 if c in ("...", "(X)") else int(c.replace(",", "")) for c in cells[2:5]]
            average = [0.0 if c in ("...", "(X)") else float(c.replace(",", "")) for c in cells[6:9]]
            found[cells[0]] = [n * a * 12 for n, a in zip(number, average)]
    if set(found) != set(OTHER_ADULT_TYPES):
        raise AgeSpendError(f"SSA Table 5.A16 is missing {sorted(set(OTHER_ADULT_TYPES) - set(found))}")
    return {k: sum(v[i] for v in found.values()) for i, k in enumerate(("under 62", "62-64", "65 or older"))}


def parse_nhe_federal_medicaid(xlsx: bytes, year: int) -> float:
    """Federal portion of Medicaid payments (dollars) for a calendar year, from CMS national health expenditure table 5-3."""
    import openpyxl
    sheet = openpyxl.load_workbook(io.BytesIO(xlsx), data_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    header = next((r for r in rows if r and year in r), None)
    if header is None:
        raise AgeSpendError(f"NHE table 5-3 has no {year} column")
    col = list(header).index(year)
    for r in rows:
        if r and isinstance(r[0], str) and r[0].strip() == "Federal Portion of Medicaid Payments" and isinstance(r[col], (int, float)):
            return float(r[col]) * 1e9
    raise AgeSpendError("NHE table 5-3 has no federal Medicaid line")
