"""School district ledgers (California SACS unaudited actuals): what each general-fund dollar is spent on, for what
purpose, and where the money comes from."""
import csv
import io


class SchoolsError(ValueError):
    pass


GENERAL_FUND = "01"
PASS_THROUGH_FUNDS = ("10",)  # money a county office only hands on to districts, which count it as their own revenue
DISTRICT_LEVEL = "0000000"  # school code of a district's own rows; charter schools filing their own accounts carry a school code
ON_BEHALF = "7690"  # resource: the state's pension contributions on a district's behalf
# (group, label, first object, last object); the first match wins, so narrow ranges come before the catch-alls.
CATEGORIES = (
    ("Salaries", "Teacher salaries", "1100", "1199"),
    ("Salaries", "Counselors, nurses and other pupil support", "1200", "1299"),
    ("Salaries", "Principals and certificated administrators", "1300", "1399"),
    ("Salaries", "Other certificated staff", "1000", "1999"),
    ("Salaries", "Classroom aides", "2100", "2199"),
    ("Salaries", "Maintenance, food, transport and other support staff", "2200", "2299"),
    ("Salaries", "Classified supervisors and administrators", "2300", "2399"),
    ("Salaries", "Office and technical staff", "2400", "2499"),
    ("Salaries", "Other classified staff", "2000", "2999"),
    ("Benefits", "Teacher pensions (CalSTRS), paid by the district", "3100", "3199"),
    ("Benefits", "Staff pensions (CalPERS)", "3200", "3299"),
    ("Benefits", "Social Security and Medicare", "3300", "3399"),
    ("Benefits", "Health and welfare benefits", "3400", "3499"),
    ("Benefits", "Unemployment and workers' compensation insurance", "3500", "3699"),
    ("Benefits", "Retiree health benefits", "3700", "3799"),
    ("Benefits", "Other benefits", "3800", "3999"),
    ("Everything else", "Books and supplies", "4000", "4999"),
    ("Everything else", "Services subcontracted to other agencies", "5100", "5199"),
    ("Everything else", "Professional services, utilities, rents and other operating costs", "5000", "5999"),
    ("Everything else", "Capital outlay", "6000", "6999"),
    ("Everything else", "Tuition, payments to other agencies and debt service", "7000", "7499"),
)
STATE_PAID_PENSION = ("Benefits", "Teacher pensions (CalSTRS), paid by the state on the district's behalf")
CATEGORY_ORDER = [(g, label) for g, label, _, _ in CATEGORIES]
CATEGORY_ORDER.insert(CATEGORY_ORDER.index(("Benefits", "Teacher pensions (CalSTRS), paid by the district")) + 1, STATE_PAID_PENSION)

PURPOSES = (
    ("Classroom instruction", "1000", "1099"),
    ("Special education instruction", "1100", "1199"),
    ("School administration", "2700", "2799"),
    ("Instructional support (supervision, library, training)", "2000", "2999"),
    ("Pupil transportation", "3600", "3699"),
    ("Pupil services (counseling, health, psychology, food)", "3000", "3999"),
    ("District administration", "7000", "7999"),
    ("Buildings, maintenance and operations", "8000", "8999"),
    ("Other (athletics and activities, community, enterprise, debt, transfers to agencies)", "4000", "9999"),
)
REVENUES = (
    ("State aid (funding formula and Education Protection Account)", "8010", "8019"),
    ("Local property taxes", "8020", "8089"),
    ("Property taxes passed to charter schools", "8096", "8096"),
    ("Other property-tax and funding-formula transfers", "8090", "8099"),
    ("Federal", "8100", "8299"),
    ("Other state", "8300", "8599"),
    ("Other local", "8600", "8699"),
    ("Passed on by other school agencies (mostly state special-education money)", "8700", "8799"),
)


def _in(code: str, lo: str, hi: str) -> bool:
    return lo <= code <= hi


def category_of(obj: str, resource: str, strict: bool = False) -> str | None:
    """The spending category of an object code, or None when the row is not an expenditure (revenue, balance sheet,
    transfers between a district's own funds)."""
    if _in(obj, "3100", "3199") and resource == ON_BEHALF:
        return STATE_PAID_PENSION[1]
    for _, label, lo, hi in CATEGORIES:
        if _in(obj, lo, hi):
            return label
    if strict and obj < "7500":
        raise SchoolsError(f"object code {obj} is not in any spending category")
    return None


def purpose_of(function: str) -> str:
    for label, lo, hi in PURPOSES:
        if _in(function, lo, hi):
            return label
    raise SchoolsError(f"function code {function} is not in any purpose")


def revenue_group_of(obj: str) -> str | None:
    return next((label for label, lo, hi in REVENUES if _in(obj, lo, hi)), None)


def parse_ledger(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    need = ("Dcode", "SchoolCode", "Fund", "Resource", "Function", "Object", "Value")
    missing = [c for c in need if c not in (reader.fieldnames or [])]
    if missing:
        raise SchoolsError(f"ledger has no {', '.join(missing)} column")
    rows = []
    for r in reader:
        try:
            value = float(r["Value"])
        except ValueError as err:
            raise SchoolsError(f"ledger has an unreadable amount {r['Value']!r}") from err
        rows.append({"district": r["Dcode"].strip(), "school": r["SchoolCode"].strip(), "fund": r["Fund"].strip(), "resource": r["Resource"].strip(),
                     "function": r["Function"].strip(), "object": r["Object"].strip(), "value": value})
    return rows


def parse_districts(text: str) -> dict[str, dict]:
    return {r["Dcode"].strip(): {"name": r["Dname"].strip(), "type": r["Dtype"].strip(), "ada": float(r["K12ADA"])}
            for r in csv.DictReader(io.StringIO(text))}


def parse_titles(text: str) -> dict[str, str]:
    return {r["Code"].strip(): r["Title"].strip() for r in csv.DictReader(io.StringIO(text))}


def summarize(rows: list[dict], fund_titles: dict[str, str]) -> dict[str, dict]:
    """Per district: general-fund spending by category and by purpose, general-fund revenue by source, and spending in
    every other fund by fund name. Charter schools that file their own accounts (rows with a school code) and
    pass-through funds are kept out of the district's figures and only totalled."""
    out: dict[str, dict] = {}

    def bump(table: dict, key: str, value: float) -> None:
        table[key] = table.get(key, 0.0) + value

    for r in rows:
        d = out.setdefault(r["district"], {"spending": {}, "purpose": {}, "revenue": {}, "other_funds": {}, "charter_schools": 0.0, "passed_through": 0.0})
        category = category_of(r["object"], r["resource"], strict=r["object"] < "8000")
        if r["school"] != DISTRICT_LEVEL:
            d["charter_schools"] += r["value"] if category is not None else 0.0
        elif r["fund"] in PASS_THROUGH_FUNDS:
            d["passed_through"] += r["value"] if category is not None else 0.0
        elif r["fund"] == GENERAL_FUND:
            if category is not None:
                bump(d["spending"], category, r["value"])
                bump(d["purpose"], purpose_of(r["function"]), r["value"])
            elif (group := revenue_group_of(r["object"])) is not None:
                bump(d["revenue"], group, r["value"])
        elif category is not None:
            if r["fund"] not in fund_titles:
                raise SchoolsError(f"fund {r['fund']} has no title")
            bump(d["other_funds"], fund_titles[r["fund"]], r["value"])
    return out
