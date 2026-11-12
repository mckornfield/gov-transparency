"""Parsers for the San Diego local age page: county population by age, the County of San Diego's open-budget
program tables, and the county behavioral health databook's client counts by age. All fail loudly on a layout
they do not recognise."""
import csv
import io
import re


class SdAgeError(ValueError):
    pass


def parse_county_population(text: str, county: str, year_code: str, top_age: int = 85) -> dict[int, int]:
    """Population of one California county by single year of age (Census cc-est syasex file; the last age is '85 and over').
    year_code is the file's YEAR column: 6 is the July 2024 estimate in the 2020-2024 vintage."""
    people = {int(r["AGE"]): int(r["TOT_POP"]) for r in csv.DictReader(io.StringIO(text))
              if r["SUMLEV"] == "050" and r["COUNTY"] == county and r["YEAR"] == year_code}
    for age in range(top_age + 1):
        if age not in people:
            raise SdAgeError(f"county population file has no age {age} for county {county}, year code {year_code}")
    return {age: people[age] for age in range(top_age + 1)}


def parse_county_budget(text: str, fiscal_year: str) -> dict[tuple[str, str, str], float]:
    """County of San Diego open-budget expenditure rows -> dollars by (group, department, program) for one fiscal year."""
    reader = csv.DictReader(io.StringIO(text))
    needed = {"fiscal_year", "group", "department", "program", "amount2"}
    if not needed <= set(reader.fieldnames or []):
        raise SdAgeError("county budget file is missing expected columns")
    out: dict[tuple[str, str, str], float] = {}
    for r in reader:
        if r["fiscal_year"] != fiscal_year:
            continue
        key = (r["group"], r["department"], r["program"])
        out[key] = out.get(key, 0.0) + float(r["amount2"])
    if not out:
        raise SdAgeError(f"county budget file has no rows for fiscal year {fiscal_year}")
    return out


SOURCES = ("state", "federal", "county", "other")


def source_of(revenue_object: str, name: str) -> str:
    """Who paid: the state, the federal government, the county's own general revenue, or anything else
    (fees, fund balance, transfers, other agencies)."""
    if revenue_object == "Intergovernmental Revenues":
        if name.startswith(("State ", "St Aid", "Other State")):
            return "state"
        if name.startswith("Federal"):
            return "federal"
        return "other"
    return "county" if revenue_object == "General Purpose Revenue Allocation" else "other"


def parse_county_revenue(text: str, fiscal_year: str) -> dict[tuple[str, str], dict[str, float]]:
    """County open-budget revenue rows -> dollars by source for each (department, program)."""
    reader = csv.DictReader(io.StringIO(text))
    needed = {"fiscal_year", "department", "program", "expense_type", "revenue_object", "amount2"}
    if not needed <= set(reader.fieldnames or []):
        raise SdAgeError("county revenue file is missing expected columns")
    out: dict[tuple[str, str], dict[str, float]] = {}
    for r in reader:
        if r["fiscal_year"] != fiscal_year:
            continue
        sources = out.setdefault((r["department"], r["program"]), dict.fromkeys(SOURCES, 0.0))
        sources[source_of(r["revenue_object"], r["expense_type"])] += float(r["amount2"])
    if not out:
        raise SdAgeError(f"county revenue file has no rows for fiscal year {fiscal_year}")
    return out


def _number(text: str) -> int:
    return int(text.replace(",", ""))


# Each block of the databook: the heading that starts it, the line that carries its total of unique clients, the age
# labels as printed, and which number on an age line is the count of unique clients (the first block prints episodes first).
BHS_BLOCKS = {
    "substance": ("Substance Use Disorder Services, FY", r"Total Unique Clients\s+([\d,]+)",
                  {"9-15": "Age 9 to 15", "16-17": "Age 16 to 17", "18-25": "Age 18 to 25", "26-59": "Age 26 to 59", "60+": "Age 60+"}, 1),
    "children": ("Mental Health Services for Children & Youth, FY", r"Mental Health Services\s+([\d,]+)",
                 {"0-5": "Age 0 to 5", "6-11": "Age 6 to 11", "12-15": "Age 12 to 15", "16-17": "Age 16 to 17", "18+": "Age 18+"}, 0),
    "adults": ("Adult Behavioral Health Services Fiscal Year", r"Clients Receiving Services\s+([\d,]+)",
               {"<18-25": "Age <18-25", "26-59": "Age 26-59", "60+": "Age 60+"}, 0),
}


def parse_bhs_ages(text: str) -> dict[str, dict[str, int]]:
    """Unique clients by age from the county Behavioral Health Services databook (pdftotext -layout): substance-use
    clients, the children's mental health system and the adult mental health system. Each block must add up to its printed total."""
    out = {}
    for name, (heading, total_pattern, labels, position) in BHS_BLOCKS.items():
        start = text.find(heading)
        if start < 0:
            raise SdAgeError(f"behavioral health databook has no section {heading!r}")
        block = text[start:start + 6000]
        total = re.search(total_pattern, block)
        if not total:
            raise SdAgeError(f"behavioral health databook has no client total for {name}")
        counts = {}
        for key, label in labels.items():
            line = re.search(rf"^\s*{re.escape(label)}\s+(.*)$", block, re.M)
            numbers = [t for t in line.group(1).split() if re.fullmatch(r"[\d,]+", t)] if line else []
            if len(numbers) <= position:
                raise SdAgeError(f"behavioral health databook has no count for {label} in {name}")
            counts[key] = _number(numbers[position])
        if sum(counts.values()) != _number(total.group(1)):
            raise SdAgeError(f"behavioral health {name} ages add up to {sum(counts.values())}, not the printed {total.group(1)}")
        out[name] = counts
    return out


def funded_shares(sources: dict[str, float]) -> dict[str, float]:
    """Dollars by source -> shares that add up to one."""
    total = sum(sources.values())
    if total <= 0 or any(v < -0.02 * total for v in sources.values()):
        raise SdAgeError("funding sources do not make a sensible total")
    return {k: v / total for k, v in sources.items()}


SCHOOL_STATE = ("State aid (funding formula and Education Protection Account)", "Other state",
                "Passed on by other school agencies (mostly state special-education money)")
SCHOOL_FEDERAL = ("Federal",)


def school_totals(schools: dict) -> tuple[float, dict[str, float]]:
    """General-fund spending of every school agency in schools.json, and its revenue by source."""
    dollars = sum(sum(d["spending"].values()) for d in schools["districts"])
    sources = dict.fromkeys(("state", "federal", "local"), 0.0)
    for d in schools["districts"]:
        for name, value in d["revenue"].items():
            if name not in schools["revenues"]:
                raise SdAgeError(f"schools file has an unknown revenue group {name!r}")
            sources["state" if name in SCHOOL_STATE else "federal" if name in SCHOOL_FEDERAL else "local"] += value
    for name in SCHOOL_STATE + SCHOOL_FEDERAL:
        if name not in schools["revenues"]:
            raise SdAgeError(f"schools file no longer has the revenue group {name!r}")
    return dollars, sources


def city_departments(text: str, basis: str, fiscal_year: str) -> dict[str, float]:
    """City of San Diego processed spending rows -> dollars by department for one basis ('adopted' or 'actual') and year."""
    out: dict[str, float] = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["basis"] == basis and r["fy"] == fiscal_year:
            out[r["dept_name"]] = out.get(r["dept_name"], 0.0) + float(r["amount"])
    if not out:
        raise SdAgeError(f"city spending file has no {basis} rows for fiscal year {fiscal_year}")
    return out
