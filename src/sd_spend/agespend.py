"""Federal spending by age: parsers for the Treasury outlays, Census population, CMS age shapes and VA age bands.

Every parser fails loudly on a layout it does not recognise rather than returning a partial table.
"""
import csv
import io


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
