"""California state spending by age: the Governor's Budget (Schedule 9 and department pages), Census state population by age,
and state agencies' counts of recipients by age."""
import csv
import io
import re


class CaSpendError(ValueError):
    pass


_AMOUNT = r"-\s*\$?[\d,]+|\$?[\d,]+|--"
FUNDS = ("general", "special", "bond", "total", "federal")


def _thousands(token: str) -> float:
    token = token.replace(" ", "")
    if token == "--":
        return 0.0
    return float(token.replace("$", "").replace(",", "")) * 1000.0


def _first_year(line: str) -> dict | None:
    """The first five amounts on a Schedule 9 line: General Fund, special funds, bond funds, budget total, federal funds."""
    tokens = re.findall(rf"(?<![\w-])(?:{_AMOUNT})(?![\w])", line)
    if len(tokens) < 5:
        return None
    return dict(zip(FUNDS, (_thousands(t) for t in tokens[:5])))


def parse_schedule9(text: str) -> dict[str, dict]:
    """Department totals (keyed by four-digit code) and section totals (keyed by their heading) for the first, actual year.

    Dollars, not thousands. Every total must equal General Fund + special funds + bond funds."""
    lines = text.splitlines()
    out: dict[str, dict] = {}
    for i, line in enumerate(lines):
        dept = re.match(r"^\s*Totals,\s*(\d{4})-(.+?)\s{2,}(.*)$", line)
        if dept:
            amounts = _first_year(dept.group(3))
            if amounts is None:
                raise CaSpendError(f"Schedule 9 total for {dept.group(1)} has too few amounts")
            out[dept.group(1)] = {"name": dept.group(2).strip(), **amounts}
            continue
        section = re.match(r"^\s*(TOTALS, [A-Z ,]+?|GRAND TOTAL)(\s{2,}.*)?$", line)
        if not section:
            continue
        name, amounts = section.group(1).strip(), _first_year(section.group(2) or "")
        if amounts is None:  # the heading wraps: amounts are on the next line and the rest of the name on the one after
            amounts = _first_year(lines[i + 1]) if i + 1 < len(lines) else None
            tail = lines[i + 2].strip() if i + 2 < len(lines) else ""
            if amounts is None:
                raise CaSpendError(f"Schedule 9 '{name}' has no amounts")
            if re.fullmatch(r"[A-Z ,]+", tail):
                name = f"{name} {tail}"
        out[name] = amounts
    if "GRAND TOTAL" not in out:
        raise CaSpendError("Schedule 9 has no GRAND TOTAL line")
    for key, row in out.items():
        if abs(row["general"] + row["special"] + row["bond"] - row["total"]) > 2000:
            raise CaSpendError(f"Schedule 9 funds for {key} do not add up to its total")
    return out


# Fund codes that are not the state's own money: federal funds and reimbursements from other departments.
NOT_STATE_FUNDS = ("0890", "0995")


def state_funds(by_fund: dict[str, float]) -> float:
    return sum(v for code, v in by_fund.items() if code not in NOT_STATE_FUNDS)


def parse_department_programs(text: str) -> dict[str, dict[str, float]]:
    """A department's 'Detailed expenditures by program': dollars by fund code for each subprogram (seven-digit code),
    state operations plus local assistance, first (actual) year."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith("DETAILED EXPENDITURES BY PROGRAM")), None)
    if start is None:
        raise CaSpendError("department page has no DETAILED EXPENDITURES BY PROGRAM table")
    out: dict[str, dict[str, float]] = {}
    current = None
    for line in lines[start + 1:]:
        if line.strip().startswith("TOTALS, EXPENDITURES"):
            break
        fund = re.match(rf"^\s*(\d{{4}})\s+\S.*?\s{{2,}}({_AMOUNT}|-)\s+({_AMOUNT}|-)\s+({_AMOUNT}|-)\s*$", line)
        if fund:
            if current is not None and fund.group(2).strip() != "-":
                out[current][fund.group(1)] = out[current].get(fund.group(1), 0.0) + _thousands(fund.group(2))
            continue
        header = re.match(r"^\s*(\d{4}|\d{7})\s+(\S.*?)\s*$", line)
        if header and not re.search(r"\d{4}-\d{2}\*", line):
            if len(header.group(1)) == 7:
                current = header.group(2)
                out.setdefault(current, {})
            elif header.group(2).isupper():  # a program heading; its fund lines repeat the subprograms below it
                current = None
    if not out:
        raise CaSpendError("department page has no subprograms")
    return out


def parse_state_population(text: str, state: str, year: int, top_age: int = 85) -> dict[int, int]:
    """Both-sexes civilian population of one state by single year of age; the last age (85) is '85 and over'."""
    column = f"POPEST{year}_CIV"
    reader = csv.DictReader(io.StringIO(text))
    if column not in (reader.fieldnames or []):
        raise CaSpendError(f"state population file has no {year} column")
    people = {int(r["AGE"]): int(r[column]) for r in reader if r["SUMLEV"] == "040" and r["STATE"].lstrip("0") == state.lstrip("0") and r["SEX"] == "0"}
    for age in range(top_age + 1):
        if age not in people:
            raise CaSpendError(f"state population file has no age {age}")
    return {age: people[age] for age in range(top_age + 1)}


def parse_dds_ages(text: str, months: list[str]) -> dict[str, float]:
    """Developmental services consumers by age group, both sexes, averaged over the given months ('*' is a suppressed small cell)."""
    sums: dict[str, float] = {}
    seen = set()
    for row in csv.DictReader(io.StringIO(text)):
        if row["Period"] not in months:
            continue
        seen.add(row["Period"])
        group = re.fullmatch(r"Ages (\d\d)-(\d\d)", row["Age"])
        if not group:
            raise CaSpendError(f"DDS file has an unexpected age group {row['Age']!r}")
        key = f"{int(group.group(1))}-{int(group.group(2))}"
        sums[key] = sums.get(key, 0.0) + (0 if row["Population"].strip() == "*" else int(row["Population"]))
    missing = [m for m in months if m not in seen]
    if missing:
        raise CaSpendError(f"DDS file has no rows for {', '.join(missing)}")
    return {k: v / len(months) for k, v in sums.items()}


def _sheet_rows(xlsx: bytes, sheet: str, source: str) -> list[tuple]:
    import openpyxl
    book = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    if sheet not in book.sheetnames:
        raise CaSpendError(f"{source} has no '{sheet}' sheet")
    return list(book[sheet].iter_rows(values_only=True))


IHSS_GROUPS = (("0-17", "0-17 yrs"), ("18-44", "18-44 yrs"), ("45-64", "45 to 64 yrs"), ("65-74", "65 to 74 yrs"),
               ("75-84", "75 to 84 yrs"), ("85+", "85+ yrs"))


def parse_ihss_ages(xlsx: bytes) -> dict[str, int]:
    """In-Home Supportive Services recipients statewide in six age groups (CDSS monthly program data, 'Age Gender' sheet)."""
    rows = _sheet_rows(xlsx, "Age Gender", "IHSS workbook")
    head = next((i for i, r in enumerate(rows) if any(isinstance(c, str) and c.startswith("0-17 yrs") for c in r)), None)
    state = next((r for r in rows[head + 1:] if "Statewide" in r), None) if head is not None else None
    if state is None:
        raise CaSpendError("IHSS workbook has no Statewide row of recipients by age")
    out = {}
    for key, label in IHSS_GROUPS:
        col = next((j for j, c in enumerate(rows[head]) if isinstance(c, str) and c.startswith(label)), None)
        if col is None or not isinstance(state[col], (int, float)):
            raise CaSpendError(f"IHSS workbook has no {label} count")
        out[key] = int(state[col])
    return out


# CA 237 CW cell numbers for cases receiving a cash grant: children (8a1) in family types A to E, and adults (8a2) in the
# three types that have aided adults (two-parent, all other, timed-out). The total-persons cells are suppressed in places.
CALWORKS_CHILDREN = range(69, 74)
CALWORKS_ADULTS = range(74, 77)


def parse_calworks_persons(xlsx: bytes, county: str) -> dict[str, int]:
    """Children and adults in CalWORKs cash-grant cases, summed over the fully reported months of the fiscal-year file."""
    rows = _sheet_rows(xlsx, "Data_External", "CA 237 CW workbook")
    head = next((r for r in rows if r and r[0] == "Date" and r[1] == "County Name"), None)
    if head is None:
        raise CaSpendError("CA 237 CW workbook has no header row")
    col = {str(c): j for j, c in enumerate(head) if c is not None}
    months = [r for r in rows if r and r[1] == county]
    if len(months) != 12:
        raise CaSpendError(f"CA 237 CW workbook has {len(months)} rows for {county}, not 12 months")
    children = adults = used = 0
    for r in months:
        try:
            kids = [r[col[str(n)]] for n in CALWORKS_CHILDREN]
            grown = [r[col[str(n)]] for n in CALWORKS_ADULTS]
        except KeyError as err:
            raise CaSpendError(f"CA 237 CW workbook has no cell {err}") from err
        if all(isinstance(v, (int, float)) for v in kids + grown):  # a month with a suppressed ('*') cell is skipped whole
            children, adults, used = children + sum(kids), adults + sum(grown), used + 1
    if used < 9:
        raise CaSpendError(f"CA 237 CW workbook has only {used} fully reported months for {county}")
    if not 0 < adults < children:
        raise CaSpendError("CA 237 CW workbook should have fewer adults than children, and some of each")
    return {"children": children, "adults": adults}


def parse_ssi_state_ages(xlsx: bytes, state: str) -> dict[str, int]:
    """Recipients of federally administered SSI payments in one state: under 18, 18-64, 65 and over (SSA SSI report, table 10)."""
    rows = _sheet_rows(xlsx, "Table 10", "SSI report")
    row = next(([c for c in r if c is not None] for r in rows if r and r[0] == state), None)
    if row is None or len(row) != 8 or sum(row[5:8]) != row[1]:
        raise CaSpendError(f"SSI table 10 has no usable row for {state}")
    return dict(zip(("0-17", "18-64", "65+"), row[5:8]))
