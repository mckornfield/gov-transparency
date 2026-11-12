"""Build who receives local government dollars in San Diego by age bracket from the saved raw files.

School districts (2023-24 actual general-fund spending), the County of San Diego (2024-25 adopted budget) and the City of
San Diego (fiscal year 2025 adopted budget), each kept separate. Writes data/processed/sd_age_spending.csv and
site/data/sd-age-spending.json. Needs pdftotext (poppler) for the county behavioral health databook.
"""
import csv
import json

from build_age_spending import pdf_text, raw
from sd_spend.ageallocate import BANDS, KEYS, add, generation_labels, population_by_band, spread_ages, va_bands
from sd_spend.caspend import parse_calworks_persons, parse_ihss_ages, parse_medi_cal_eligibles
from sd_spend.io import ROOT
from sd_spend.sdage import (SOURCES, internal_by_group, city_departments, funded_shares, parse_bhs_ages, parse_county_budget, parse_county_population,
                            parse_county_revenue, school_totals)

SCHOOLS, COUNTY, CITY = "School districts", "County of San Diego", "City of San Diego"
POPULATION_YEAR = 2024
COUNTY_FISCAL_YEAR = "2025"  # the county's label for July 2024 to June 2025
CITY_FISCAL_YEAR = "2025"
TOP = 85
MONTHS = [f"2024-{m:02d}" for m in range(7, 13)] + [f"2025-{m:02d}" for m in range(1, 7)]
IHSS_RANGES = {"0-17": (0, 17), "18-44": (18, 44), "45-64": (45, 64), "65-74": (65, 74), "75-84": (75, 84), "85+": (TOP, TOP)}
CALWORKS_RANGES = {"children": (0, 17), "adults": (18, 49)}
ELIGIBLE_RANGES = {"0-18": (0, 18), "19-44": (19, 44), "45-64": (45, 64), "65+": (65, TOP)}
SUBSTANCE_RANGES = {"9-15": (9, 15), "16-17": (16, 17), "18-25": (18, 25), "26-59": (26, 59), "60+": (60, TOP)}
CHILD_RANGES = {"0-5": (0, 5), "6-11": (6, 11), "12-15": (12, 15), "16-17": (16, 17), "18+": (18, 20)}
ADULT_RANGES = {"<18-25": (16, 25), "26-59": (26, 59), "60+": (60, TOP)}  # the youngest group includes some clients under 18
COUNTY_REST = {
    "Health and Human Services Agency": ("Rest of county health and human services", "Public health, homelessness and housing programs, medical care services and administration: no age split found"),
    "Public Safety Group": ("Public safety: sheriff, jails, prosecutors, public defender, probation, fire, child support and other", "Ages of people in custody or on probation exist, but they are not recipients in this page's sense; the rest protects everyone"),
    "Land Use and Environment Group": ("Roads, planning, environmental health and other land use", "Serves everyone, mostly in the unincorporated area"),
    "Finance and General Government Group": ("County administration and finance", "Serves everyone"),
    "Finance Other": ("Countywide costs, debt and contributions to other funds", "Not tied to people of any age"),
    "Capital Program": ("Buildings and other capital projects", "Not tied to people of any age"),
}
CITY_REST = [("Police", ("Police",), "Protects everyone"), ("Fire-Rescue", ("Fire-Rescue",), "Protects everyone"),
             ("Water and sewer (Public Utilities)", ("Public Utilities",), "Paid for by customers' bills; serves every household")]


def local_merged(sources: dict) -> dict:
    """State, federal and local: the county's own general revenue, taxes, fees, fund balance and transfers count as local."""
    return {"state": sources["state"], "federal": sources["federal"], "local": sum(v for k, v in sources.items() if k not in ("state", "federal"))}


def build() -> dict:
    pop = parse_county_population(raw("census/cc-est2024-syasex-06.csv").decode("utf-8-sig"), "073", "6", TOP)
    population = population_by_band(pop)
    county_people = sum(pop.values())
    even = lambda dollars: {k: dollars * population[k] / county_people for k in KEYS}  # noqa: E731
    programs, not_allocated, governments = [], [], []

    def program(government, name, method, note, by_band, sources=None, per_person=None):
        dollars = sum(by_band.values())
        if dollars <= 0 or any(v < 0 for v in by_band.values()):
            raise SystemExit(f"{name} has an impossible split")
        row = {"program": name, "group": government, "method": method, "kind": "outlay", "note": note, "dollars": dollars, "by_band": by_band,
               "funded": funded_shares(local_merged(sources)) if sources else None}
        if per_person is not None:
            row["per_person"] = dict.fromkeys(KEYS, per_person)
        programs.append(row)

    def government(name, basis, total, people, rest):
        allocated = sum(p["dollars"] for p in programs if p["group"] == name)
        for label, dollars, why in rest:
            if dollars < 0:
                raise SystemExit(f"{name}: {label} is negative")
            not_allocated.append({"government": name, "name": label, "dollars": dollars, "reason": why})
        if abs(allocated + sum(d for _, d, _ in rest) - total) > 1 or not 0 < allocated <= total:
            raise SystemExit(f"{name}: allocated and not-allocated dollars do not add up to its total")
        governments.append({"name": name, "basis": basis, "total": total, "allocated": allocated, "residents": people})

    # School districts: the general fund of every district and the County Office of Education, as on the schools page.
    schools = json.loads((ROOT / "site" / "data" / "schools.json").read_text())
    if schools["year_label"] != "2023-24":
        raise SystemExit("schools.json is not the 2023-24 year this page describes")
    school_dollars, school_sources = school_totals(schools)
    program(SCHOOLS, "K-12 schools (general fund)", "proxy",
            "General-fund spending of the county's 42 school districts and the County Office of Education, 2023-24 actuals, spread over ages 4-18 by population (includes transitional kindergarten; a little adult education is not separated). Independent charter schools, cafeteria funds and bond-funded construction are not in this figure",
            spread_ages(school_dollars, 4, 18, pop), school_sources)
    government(SCHOOLS, "2023-24 actual spending, general funds", school_dollars, county_people, [])

    # County of San Diego: adopted budget by program, with each program's revenue by source.
    budget = parse_county_budget(raw("sdcounty/open_budget_exp_fy2025.csv").decode("utf-8-sig"), COUNTY_FISCAL_YEAR)
    revenue = parse_county_revenue(raw("sdcounty/open_budget_rev_fy2025.csv").decode("utf-8-sig"), COUNTY_FISCAL_YEAR)
    unknown = {k[0] for k in budget} - set(COUNTY_REST)
    if unknown:
        raise SystemExit(f"county budget has groups this build does not know: {sorted(unknown)}")
    used = set()

    def take(department, names=None):
        keys = [k for k in budget if k[1] == department and (names is None or k[2] in names)]
        if not keys or (names is not None and {k[2] for k in keys} != set(names)) or used & set(keys):
            raise SystemExit(f"county budget programs not found (or used twice): {department} {names}")
        used.update(keys)
        dollars = sum(budget[k] for k in keys)
        # A program's own budgeted revenue, unless it holds offsetting (negative) entries: the county lets one program's
        # state and federal money cover another's costs. Then the whole department's revenue is used instead.
        sources = {s: sum(revenue.get((k[1], k[2]), {}).get(s, 0.0) for k in keys) for s in SOURCES}
        spent = dollars
        if any(v < 0 for v in sources.values()):
            sources = {s: sum(v[s] for k, v in revenue.items() if k[0] == department) for s in SOURCES}
            spent = sum(v for k, v in budget.items() if k[1] == department)
        if abs(sum(sources.values()) - spent) > 0.01 * spent:
            raise SystemExit(f"county revenue does not match spending for {department}")
        return dollars, sources

    bhs = parse_bhs_ages(pdf_text("sdcounty/bhs_databook_fy2024_25.pdf"))
    ihss = parse_ihss_ages(raw("ca/ihss_program_data_jan2024.xlsx"))
    calworks = parse_calworks_persons(raw("ca/ca237cw_fy2023_24.xlsx"), "San Diego")
    eligibles = parse_medi_cal_eligibles(raw("ca/medi_cal_eligibles_age_sex.csv").decode("utf-8-sig"), MONTHS, "San Diego")

    dollars, sources = take("Child and Family Well-Being")
    program(COUNTY, "Child welfare, foster care and adoptions", "proxy",
            "Child and Family Well-Being department, all placed at ages 0-17 by population. Extended foster care to age 21 and services to parents are not separated",
            spread_ages(dollars, 0, 17, pop), sources)
    dollars, sources = take("Aging & Independence Services", ("In-Home Supportive Services",))
    program(COUNTY, "In-Home Supportive Services (county budget)", "proxy",
            "Spread like statewide recipients in six age groups (January 2024), assuming equal hours per person; recipients by age are not published for the county. Most of what caregivers are paid is state and federal money that does not pass through the county budget",
            va_bands(ihss, dollars, pop, IHSS_RANGES), sources)
    dollars, sources = take("Aging & Independence Services", ("Protective Services", "Senior Health and Social Services"))
    program(COUNTY, "Adult protective and senior services", "proxy",
            "Spread over ages 60 and over by population. Adult protective services also serve dependent adults under 60, who are not separated",
            spread_ages(dollars, 60, TOP, pop), sources)
    dollars, sources = take("Self-Sufficiency Services", ("Assistance Payments",))
    program(COUNTY, "Cash aid and related services (mostly CalWORKs)", "proxy",
            "Spread by children and adults in San Diego County CalWORKs cash-grant cases (2023-24), assuming equal dollars per person; children over ages 0-17 and adults over 18-49 by population. The line also holds general relief for adults and contracted employment services, which are not separated",
            va_bands(calworks, dollars, pop, CALWORKS_RANGES), sources)
    dollars, sources = take("Self-Sufficiency Services", ("Regional Self-Sufficiency",))
    program(COUNTY, "Benefits eligibility offices (Medi-Cal, CalFresh, CalWORKs)", "proxy",
            "Staff who enrol people in benefits, spread like San Diego County's Medi-Cal eligibles in four age groups (July 2024 to June 2025), then by population. The benefits themselves are state and federal spending and are not in the county budget",
            va_bands(eligibles, dollars, pop, ELIGIBLE_RANGES), sources)
    dollars, sources = take("Behavioral Health Services", ("Mental Health Services",))
    clients = sum(bhs["children"].values()) + sum(bhs["adults"].values())
    program(COUNTY, "Mental health services", "proxy",
            "Spread like the county's unique mental health clients by age in 2024-25 (children's and adult systems), assuming equal cost per client, then by population within each age group. Cost per client is not published by age",
            add(va_bands(bhs["children"], dollars * sum(bhs["children"].values()) / clients, pop, CHILD_RANGES),
                va_bands(bhs["adults"], dollars * sum(bhs["adults"].values()) / clients, pop, ADULT_RANGES)), sources)
    dollars, sources = take("Behavioral Health Services", ("Inpatient Health Services",))
    program(COUNTY, "County psychiatric hospital and Edgemoor nursing facility", "proxy",
            "Two adult facilities, spread like clients of the adult mental health system by age in 2024-25, then by population. Edgemoor's residents are probably older than that mix. Billing to Medi-Cal, Medicare and other insurers counts as local money here",
            va_bands(bhs["adults"], dollars, pop, ADULT_RANGES), sources)
    dollars, sources = take("Behavioral Health Services", ("Alcohol and Other Drug Services",))
    program(COUNTY, "Alcohol and drug services", "proxy",
            "Spread like the county's unique substance-use clients by age in 2024-25, assuming equal cost per client, then by population within each age group",
            va_bands(bhs["substance"], dollars, pop, SUBSTANCE_RANGES), sources)
    dollars, sources = take("Public Health Services", ("California Childrens Services",))
    program(COUNTY, "California Children's Services", "proxy", "Medical care for children with serious conditions, spread over ages 0-20 by population",
            spread_ages(dollars, 0, 20, pop), sources)
    library, library_sources = take("County Library")
    parks, parks_sources = take("Parks and Recreation")
    program(COUNTY, "County library and parks", "proxy",
            "Spread evenly across county residents: no figures by age. County branches and parks mostly serve the unincorporated area and smaller cities, so a City of San Diego resident receives less than this average",
            even(library + parks), {s: library_sources[s] + parks_sources[s] for s in SOURCES})
    # Payments between county funds and departments are budgeted by both sides; take them out of the receiving group's remainder.
    internal = internal_by_group(raw("sdcounty/open_budget_rev_fy2025.csv").decode("utf-8-sig"), COUNTY_FISCAL_YEAR)
    if set(internal) - set(COUNTY_REST) or not 1e9 < sum(internal.values()) < 2e9:
        raise SystemExit("county internal charges and transfers are not what this build expects")
    county_total = sum(budget.values()) - sum(internal.values())
    rest = [(label, sum(v for k, v in budget.items() if k[0] == group and k not in used) - internal.get(group, 0.0), why) for group, (label, why) in COUNTY_REST.items()]
    government(COUNTY, f"2024-25 adopted budget, less ${sum(internal.values()) / 1e9:.1f}B of payments between county funds and departments", county_total, county_people, rest)

    # City of San Diego: adopted budget by department.
    city = city_departments((ROOT / "data" / "processed" / "spending.csv").read_text(), "adopted", CITY_FISCAL_YEAR)
    with (ROOT / "data" / "processed" / "population.csv").open(newline="") as f:
        city_people = next((int(r["population"]) for r in csv.DictReader(f) if r["fy"] == CITY_FISCAL_YEAR), None)
    if not city_people or not 1_000_000 < city_people < county_people:
        raise SystemExit("no plausible City of San Diego population for the budget year")
    for name, department in (("City libraries", "Library"), ("City parks and recreation", "Parks & Recreation")):
        program(CITY, name, "proxy",
                "Spread evenly across City of San Diego residents: no figures by age. Shown per city resident; funding sources are not separated in the city's data",
                even(city[department]), per_person=city[department] / city_people)
    named = [(label, sum(city[d] for d in departments), why) for label, departments, why in CITY_REST]
    city_total = sum(city.values())
    everything_else = city_total - city["Library"] - city["Parks & Recreation"] - sum(d for _, d, _ in named)
    government(CITY, "Fiscal year 2025 (2024-25) adopted budget", city_total, city_people,
               named + [("Everything else the city does", everything_else, "Streets, trash, planning, homelessness programs, administration and debt: no age split found")])

    if any((p.get("per_person", {}).get(k) or p["by_band"][k] / population[k]) > 100_000 for p in programs for k in KEYS):
        raise SystemExit("implausible per-person amount")
    return {
        "fiscal_year": POPULATION_YEAR, "year_label": "2023-24 (schools) and the 2024-25 budgets (county and city)", "population_year": POPULATION_YEAR,
        "bands": [{"key": k, "lo": lo, "hi": min(hi, 100), "population": population[k], "generations": generation_labels((k, lo, hi), pop, POPULATION_YEAR)}
                  for k, lo, hi in BANDS],
        "programs": programs, "governments": governments, "not_allocated": not_allocated,
        "total_outlays": sum(g["total"] for g in governments), "allocated": sum(g["allocated"] for g in governments), "tax_credits": 0,
        "behavioral_health_clients": bhs,
    }


def main() -> None:
    data = build()
    (ROOT / "site" / "data" / "sd-age-spending.json").write_text(json.dumps(data, indent=1) + "\n")
    with (ROOT / "data" / "processed" / "sd_age_spending.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["government", "program", "method", "band", "dollars"])
        for r in data["programs"]:
            for k in KEYS:
                writer.writerow([r["group"], r["program"], r["method"], k, round(r["by_band"][k])])
    people = {b["key"]: b["population"] for b in data["bands"]}
    per = lambda r: [round(r.get("per_person", {}).get(k) or r["by_band"][k] / people[k]) for k in KEYS]  # noqa: E731
    for g in data["governments"]:
        print(f"{g['name']}: {g['total'] / 1e9:,.2f}B, allocated {g['allocated'] / 1e9:,.2f}B ({g['allocated'] / g['total']:.0%}), residents {g['residents']:,}")
    for r in data["programs"]:
        funded = " ".join(f"{k} {v:.0%}" for k, v in r["funded"].items()) if r["funded"] else "-"
        print(r["program"].ljust(58), f"{r['dollars'] / 1e6:8,.0f}M", per(r), funded)
    print("per person, all programs", [sum(per(r)[i] for r in data["programs"]) for i in range(len(KEYS))])
    for n in data["not_allocated"]:
        print("not allocated:", n["government"].ljust(22), n["name"].ljust(64), f"{n['dollars'] / 1e6:8,.0f}M")


if __name__ == "__main__":
    main()
