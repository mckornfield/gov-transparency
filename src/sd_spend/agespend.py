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


def parse_snap_ages(text: str) -> dict[str, int]:
    """SNAP participants (people) by age group from Table A.23 of the FNS characteristics report; the table is in thousands."""
    labels = {"Child": "0-17", "18–35 years": "18-35", "36–59 years": "36-59", "Elderly individual": "60+"}
    found, total = {}, None
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("Table A.23.") and "...." not in line), None)
    if start is None:
        raise AgeSpendError("SNAP report has no Table A.23")
    for line in lines[start + 1:]:
        if line.startswith("Source:"):
            break
        m = re.match(r"^\s*(Total|Child|18–35 years|36–59 years|Elderly individual)\s+([\d,]+)\s+\d+\.\d", line)
        if not m:
            continue
        if m.group(1) == "Total":
            total = total or int(m.group(2).replace(",", "")) * 1000
        else:
            found.setdefault(labels[m.group(1)], int(m.group(2).replace(",", "")) * 1000)
    if set(found) != set(labels.values()) or total is None:
        raise AgeSpendError("SNAP Table A.23 is missing an age row")
    if abs(sum(found.values()) - total) > 0.005 * total:
        raise AgeSpendError("SNAP participants by age do not add up to the total")
    return found


def parse_fns_costs(text: str, fiscal_year: str) -> dict[str, float]:
    """SNAP, child nutrition and WIC costs for a fiscal year from the FNS Keydata 'Total FNS Cost' table."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if "Total FNS Cost -- All Programs" in line), None)
    if start is None:
        raise AgeSpendError("FNS Keydata has no Total FNS Cost table")
    year = next((i for i in range(start, len(lines)) if lines[i].strip() == fiscal_year), None)
    row = next((lines[i] for i in range(year or len(lines), len(lines)) if re.match(r"^Total\s+[\d,]{5,}", lines[i])), None) if year is not None else None
    if row is None:
        raise AgeSpendError(f"FNS Keydata has no total row for {fiscal_year}")
    cells = [c for c in row.split()[1:] if c != "--"]
    values = [float(c.replace(",", "")) for c in cells]
    if len(values) < 9:
        raise AgeSpendError("FNS Keydata total row has too few columns")
    parts, total = values[:-1], values[-1]
    if abs(sum(parts) - total) > 0.005 * total:
        raise AgeSpendError("FNS cost columns do not add up to the total")
    return {"SNAP": values[0], "Child nutrition": values[1], "WIC": values[3], "Total": total}


def parse_hud_housing(xlsx: bytes) -> dict:
    """HUD-assisted housing, all programs: annual federal dollars (units x average monthly spending x 12) and the percent of
    households by age of the household head (the file gives household heads, not residents)."""
    import openpyxl
    rows = list(openpyxl.load_workbook(io.BytesIO(xlsx), data_only=True).active.iter_rows(values_only=True))
    header = list(rows[0])
    row = next((dict(zip(header, r)) for r in rows[1:] if r[header.index("program")] == 1), None)
    if row is None or row["program_label"] != "Summary of All HUD Programs":
        raise AgeSpendError("HUD file has no all-programs summary row")
    heads = {"24 and under": row["pct_lt24_head"], "25-50": row["pct_age25_50"], "51-61": row["pct_age51_61"],
             "62-84": row["pct_age62plus"] - row["pct_age85plus"], "85 and over": row["pct_age85plus"]}
    if not 98 <= sum(heads.values()) <= 102:
        raise AgeSpendError(f"HUD head ages add up to {sum(heads.values())} percent")
    return {"dollars": float(row["total_units"]) * float(row["spending_per_month"]) * 12, "heads": heads}


MOTHER_GROUPS = ((10, 14), (15, 19), (20, 24), (25, 29), (30, 34), (35, 39), (40, 44), (45, 49), (50, 54))


def parse_births_by_mother(text: str) -> list[tuple[int, int, int]]:
    """Births by age of mother (age group, count) from table 3 of the CDC final births report, all races and origins."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("Table 3. Births, by age of mother")), None)
    if start is None:
        raise AgeSpendError("CDC births report has no Table 3")
    row = next((line for line in lines[start:] if re.match(r"^Total[ .]+[\d,]+", line)), None)
    if row is None:
        raise AgeSpendError("CDC Table 3 has no Total row")
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", row.split(". .")[-1] if ". ." in row else row)]
    # all ages, younger than 15, 15-19 total, ages 15 to 19 singly (5), 20-24 ... 50-54
    if len(nums) != 1 + 1 + 1 + 5 + 7:
        raise AgeSpendError(f"CDC Table 3 total row has {len(nums)} numbers")
    all_ages, young, teens, rest = nums[0], nums[1], nums[2], nums[8:]
    counts = [young, teens, *rest]
    if sum(counts) != all_ages:
        raise AgeSpendError("CDC births by age of mother do not add up to all births")
    return [(lo, hi, n) for (lo, hi), n in zip(MOTHER_GROUPS, counts)]


def _money_thousands(sheet, row: int, col: int) -> float:
    value = sheet.cell_value(row, col)
    if not isinstance(value, (int, float)):
        raise AgeSpendError(f"IRS table has no number at row {row} column {col}")
    return float(value) * 1000


def parse_irs_credits(table25, table33) -> dict[str, float]:
    """Tax year credits (dollars) from IRS SOI table 2.5 (EITC) and 3.3 (child credits); both tables are in thousands."""
    for sheet in (table25, table33):
        if "thousands" not in str(sheet.cell_value(0, 0)) + str(sheet.cell_value(1, 0)):
            raise AgeSpendError("IRS table is not stated in thousands of dollars")
    if sheet_label(table25, 8) != "Total" or sheet_label(table33, 9) != "All returns, total":
        raise AgeSpendError("IRS table rows moved")
    return {"EITC": _money_thousands(table25, 8, 10), "EITC childless": _money_thousands(table25, 8, 26),
            "Child credit nonrefundable": _money_thousands(table33, 9, 13), "Child credit refundable": _money_thousands(table33, 9, 39)}


def sheet_label(sheet, row: int) -> str:
    return str(sheet.cell_value(row, 0)).strip()


# Treasury functions that pay for or serve people (health, retirement, income support, veterans, education and social services).
# Defense, interest, justice, transport, science, energy, farm, commerce and the like are collective costs and are left out.
PERSON_FUNCTIONS = ("Social Security", "Medicare", "Health", "Income Security", "Veterans Benefits and Services",
                    "Education, Training, Employment, and Social Services")


def person_directed_total(lines: dict[str, float]) -> float:
    missing = [name for name in PERSON_FUNCTIONS if name not in lines]
    if missing:
        raise AgeSpendError(f"Treasury outlays have no line for {', '.join(missing)}")
    return sum(lines[name] for name in PERSON_FUNCTIONS)


UI_AGE_COLUMNS = ("c12", "c13", "c14", "c15", "c16", "c17", "c18", "c19")
UI_AGE_BANDS = ("under 22", "22-24", "25-34", "35-44", "45-54", "55-59", "60-64", "65+")


def parse_ui_ages(text: str, start: str, end: str) -> dict[str, int]:
    """Weeks of unemployment insurance claimed by age (DOL ETA 203, insured unemployed), summed over report dates in
    [start, end]. Columns c12 to c19 are the eight age groups, c20 is age not available (DOL's ar203 data map)."""
    reader = csv.DictReader(io.StringIO(text))
    totals = dict.fromkeys(UI_AGE_COLUMNS, 0)
    unknown = sexes = 0
    months: dict[str, int] = {}
    try:
        for row in reader:
            if not start <= row["rptdate"] <= end:
                continue
            months[row["st"]] = months.get(row["st"], 0) + 1
            for col in UI_AGE_COLUMNS:
                totals[col] += int(row[col])
            unknown += int(row["c20"])
            sexes += int(row["c2"]) + int(row["c3"]) + int(row["c4"])
    except (KeyError, ValueError) as err:
        raise AgeSpendError(f"ETA 203 file has an unexpected layout: {err}") from err
    expected = (int(end[:4]) - int(start[:4])) * 12 + int(end[5:7]) - int(start[5:7]) + 1
    if not months or set(months.values()) != {expected}:
        raise AgeSpendError(f"ETA 203 file does not have {expected} months for every state in the window")
    aged = sum(totals.values())
    if sexes <= 0 or unknown > 0.02 * sexes:
        raise AgeSpendError(f"ETA 203 ages unknown for {unknown} of {sexes} claims")
    if aged + unknown != sexes:
        raise AgeSpendError(f"ETA 203 ages ({aged} + {unknown} unknown) do not match the sex totals ({sexes})")
    return dict(zip(UI_AGE_BANDS, (totals[c] for c in UI_AGE_COLUMNS)))


SSI_UNDER18 = ("Under 5", "5–12", "13–17")
SSI_ADULT = ("18–21", "22–25", "26–29", "30–39", "40–49", "50–59", "60–64")


def parse_ssi(xlsx: bytes, year: int) -> dict:
    """SSI annual statistical report: federal SSI dollars for the year (table 2), the split of federal SSI payments across
    under 18, 18-64 and 65+ (table 5, December of the report year) and recipients under 65 by fine age (table 35)."""
    import openpyxl
    book = openpyxl.load_workbook(io.BytesIO(xlsx), data_only=True)

    def rows(name):
        if name not in book.sheetnames:
            raise AgeSpendError(f"SSI report has no {name}")
        return [[c for c in r if c is not None] for r in book[name].iter_rows(values_only=True)]

    t2 = rows("Table 2")
    first = next((i for i, r in enumerate(t2) if r == ["All recipients"]), None)
    row = next((r for r in t2[first:] if r and r[0] == year and len(r) == 4), None) if first is not None else None
    if row is None or abs(row[1] - row[2] - row[3]) > 2:
        raise AgeSpendError(f"SSI table 2 has no usable row for {year}")
    t5 = rows("Table 5")
    start = next((i for i, r in enumerate(t5) if r and str(r[0]).startswith("Total payments")), None)
    pay = next((r for r in t5[start:] if r and r[0] == "Federal SSI"), None) if start is not None else None
    if pay is None or len(pay) != 8:
        raise AgeSpendError("SSI table 5 has no federal SSI payments row")
    groups = pay[5:8]
    if abs(sum(groups) - pay[1]) > 2:
        raise AgeSpendError("SSI payments by age do not add up to the total")
    t35 = next((r for r in rows("Table 35") if r and r[0] == "Total"), None)
    if t35 is None or len(t35) != 12:
        raise AgeSpendError("SSI table 35 has no Total row")
    counts = t35[2:]
    if sum(counts) != t35[1]:
        raise AgeSpendError("SSI recipients by fine age do not add up to the total")
    return {"federal_dollars": row[2] * 1000.0,
            "group_shares": {k: g / pay[1] for k, g in zip(("0-17", "18-64", "65+"), groups)},
            "under18_counts": dict(zip(("0-4", "5-12", "13-17"), counts[:3])),
            "adult_counts": dict(zip(("18-21", "22-25", "26-29", "30-39", "40-49", "50-59", "60-64"), counts[3:]))}
