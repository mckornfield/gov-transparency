"""Build who receives California state dollars by age bracket for 2023-24 from the saved raw files.

Writes data/processed/ca_age_spending.csv and site/data/ca-age-spending.json. Needs pdftotext (poppler) for the budget PDFs.
"""
import csv
import json

from build_age_spending import CMS_GROUPS, pdf_text, raw, zipped
from sd_spend.ageallocate import BANDS, KEYS, from_shares, generation_labels, population_by_band, spread_ages, va_bands
from sd_spend.agespend import parse_cms_shares
from sd_spend.caspend import (parse_calworks_persons, parse_dds_ages, parse_department_programs, parse_ihss_ages, parse_schedule9,
                              parse_ssi_state_ages, parse_state_population, state_funds)
from sd_spend.io import ROOT

YEAR_LABEL = "2023-24"
POPULATION_YEAR = 2024
MONTHS = [f"2023-{m:02d}" for m in range(7, 13)] + [f"2024-{m:02d}" for m in range(1, 7)]
TOP = 85  # the state population file ends at "85 and over"
DDS_RANGES = {"0-2": (0, 2), "3-5": (3, 5), "6-9": (6, 9), "10-13": (10, 13), "14-17": (14, 17), "18-21": (18, 21), "22-31": (22, 31),
              "32-41": (32, 41), "42-51": (42, 51), "52-61": (52, 61), "62-99": (62, TOP)}
IHSS_RANGES = {"0-17": (0, 17), "18-44": (18, 44), "45-64": (45, 64), "65-74": (65, 74), "75-84": (75, 84), "85+": (TOP, TOP)}
SSI_RANGES = {"0-17": (0, 17), "18-64": (18, 64), "65+": (65, TOP)}
CALWORKS_RANGES = {"children": (0, 17), "adults": (18, 49)}
# Departments whose federal funds are shown for information (they are counted on the federal page, not here).
DEPARTMENTS = ("4260", "4300", "5180", "6100", "6440", "6610", "6870", "6980")


def build() -> dict:
    s9 = parse_schedule9(pdf_text("ca/schedule9_2025_26_gb.pdf"))
    dss = {name: state_funds(funds) for name, funds in parse_department_programs(pdf_text("ca/dss_5180_2025_26_gb.pdf")).items()}
    if abs(sum(dss.values()) - s9["5180"]["total"]) > 0.005 * s9["5180"]["total"]:
        raise SystemExit("Department of Social Services programs do not add up to its Schedule 9 state funds")
    pop = parse_state_population(raw("census/sc-est2024-agesex-civ.csv").decode(), "6", POPULATION_YEAR, TOP)
    cms = parse_cms_shares(zipped("cms/age_and_sex_csv_files.zip", "age and Sex.csv").decode(), "2020", ("Medicaid",), CMS_GROUPS)
    dds = parse_dds_ages(raw("ca/dds_consumers_by_age_gender.csv").decode("utf-8-sig"), MONTHS)
    ihss = parse_ihss_ages(raw("ca/ihss_program_data_jan2024.xlsx"))
    calworks = parse_calworks_persons(raw("ca/ca237cw_fy2023_24.xlsx"), "Statewide")
    ssp = parse_ssi_state_ages(raw("ssa/ssi_asr25.xlsx"), "California")
    total = lambda code: s9[code]["total"]  # noqa: E731

    programs = [
        ("K-12 education", "Schools", "proxy", "Department of Education state funds (Schedule 9) spread over ages 4-18 by population; includes transitional kindergarten and state preschool. The local property-tax share of school funding is local money and is not here",
         spread_ages(total("6100"), 4, 18, pop)),
        ("UC, CSU and Cal Grants", "Higher education", "proxy", "University of California, California State University and Student Aid Commission state funds (Schedule 9) spread over ages 18-29 by population; no enrolment by age was used",
         spread_ages(total("6440") + total("6610") + total("6980"), 18, 29, pop)),
        ("Community colleges", "Higher education", "proxy", "Community colleges state funds (Schedule 9, including bond-funded construction) spread over ages 18-39 by population; no enrolment by age was used",
         spread_ages(total("6870"), 18, 39, pop)),
        ("Medi-Cal and other state health care (state share)", "Health", "proxy", "Department of Health Care Services state funds (Schedule 9; almost all Medi-Cal, and including provider fees and drug rebates the budget counts as special funds), split by CMS's national age shape of Medicaid spending (2020). The state's share differs by eligibility group, which this does not capture",
         from_shares(total("4260"), cms["Medicaid"])),
        ("Developmental services", "Disability and care", "published", "Department of Developmental Services state funds (Schedule 9) spread like the people it serves by age group (monthly average, July 2023 to June 2024), assuming equal cost per person; within each group by population",
         va_bands(dds, total("4300"), pop, DDS_RANGES)),
        ("In-Home Supportive Services (state share)", "Disability and care", "published", "State funds for IHSS (Department of Social Services budget page) spread like recipients in six age groups (January 2024), assuming equal hours per person",
         va_bands(ihss, dss["IHSS"], pop, IHSS_RANGES)),
        ("SSI state supplement (SSP)", "Income support", "published", "State funds for SSI/SSP spread like California's SSI recipients under 18, 18-64 and 65 and over (SSA, December 2025), within each by population",
         va_bands(ssp, dss["SSI/SSP"], pop, SSI_RANGES)),
        ("CalWORKs (state share)", "Income support", "published", "State funds for CalWORKs spread by children and adults in cash-grant cases (2023-24), assuming equal dollars per person; children over ages 0-17 and adults over 18-49 by population",
         va_bands(calworks, dss["CalWORKs"], pop, CALWORKS_RANGES)),
        ("Child care (state share)", "Children", "proxy", "State funds for subsidised child care (Department of Social Services) spread over ages 0-12 by population",
         spread_ages(dss["Child Care"], 0, 12, pop)),
    ]
    population = population_by_band(pop)
    rows = []
    for name, group, method, note, by_band in programs:
        dollars = sum(by_band.values())
        if dollars <= 0 or any(v < 0 for v in by_band.values()):
            raise SystemExit(f"{name} has an impossible split")
        rows.append({"program": name, "group": group, "method": method, "kind": "outlay", "note": note, "dollars": dollars, "by_band": by_band})
    allocated = sum(r["dollars"] for r in rows)
    people = s9["TOTALS, HEALTH AND HUMAN SERVICES"]["total"] + s9["TOTALS, EDUCATION"]["total"]
    everything = s9["GRAND TOTAL"]["total"]
    if not 0 < allocated < people < everything:
        raise SystemExit("allocated dollars must be a share of spending on people, which is a share of all state funds")
    if any(r["by_band"][k] / population[k] > 100_000 for r in rows for k in KEYS):
        raise SystemExit("implausible per-person amount")
    dss_used = dss["IHSS"] + dss["SSI/SSP"] + dss["CalWORKs"] + dss["Child Care"]
    not_allocated = [
        ("Prisons and rehabilitation", s9["TOTALS, CORRECTIONS AND REHABILITATION"]["total"], "Ages of people in prison exist, but they are not recipients in this page's sense"),
        ("Teachers' retirement contributions", s9["6300"]["total"], "Pay for past work, not a benefit by age"),
        ("Rest of education", s9["TOTALS, EDUCATION"]["total"] - total("6100") - total("6440") - total("6610") - total("6870") - total("6980") - s9["6300"]["total"],
         "School facilities, the state library, other colleges and commissions: no age split used"),
        ("Rest of the Department of Social Services", s9["5180"]["total"] - dss_used, "Child welfare, county administration and other assistance: no age split found"),
        ("Rest of health and human services", s9["TOTALS, HEALTH AND HUMAN SERVICES"]["total"] - total("4260") - total("4300") - total("5180"), "Public health, state hospitals and other departments: no age split found"),
        ("Everything else", everything - people - s9["TOTALS, CORRECTIONS AND REHABILITATION"]["total"], "Transportation, courts, natural resources, general government and the like: collective costs, mostly not payments to individuals"),
    ]
    if abs(allocated + sum(d for _, d, _ in not_allocated) - everything) > 1e6:
        raise SystemExit("allocated and not-allocated dollars do not add up to all state funds")
    return {
        "fiscal_year": POPULATION_YEAR, "year_label": YEAR_LABEL, "population_year": POPULATION_YEAR,
        "bands": [{"key": k, "lo": lo, "hi": min(hi, 100), "population": population[k], "generations": generation_labels((k, lo, hi), pop, POPULATION_YEAR)}
                  for k, lo, hi in BANDS],
        "programs": rows, "total_outlays": everything, "person_directed": people, "allocated": allocated, "tax_credits": 0,
        "federal_through": sum(s9[code]["federal"] for code in DEPARTMENTS),
        "not_allocated": [{"name": n, "dollars": d, "reason": why} for n, d, why in not_allocated],
    }


def main() -> None:
    data = build()
    (ROOT / "site" / "data" / "ca-age-spending.json").write_text(json.dumps(data, indent=1) + "\n")
    with (ROOT / "data" / "processed" / "ca_age_spending.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fiscal_year", "program", "group", "method", "band", "dollars"])
        for r in data["programs"]:
            for k in KEYS:
                writer.writerow([YEAR_LABEL, r["program"], r["group"], r["method"], k, round(r["by_band"][k])])
    print(f"state funds {data['total_outlays'] / 1e9:,.1f}B, on people {data['person_directed'] / 1e9:,.1f}B, allocated {data['allocated'] / 1e9:,.1f}B "
          f"({data['allocated'] / data['total_outlays']:.0%} of all, {data['allocated'] / data['person_directed']:.0%} of people); federal through {data['federal_through'] / 1e9:,.1f}B")
    for r in data["programs"]:
        print(r["program"].ljust(52), f"{r['dollars'] / 1e9:6,.1f}B", [round(r["by_band"][k] / data["bands"][KEYS.index(k)]["population"]) for k in KEYS])
    print("per person, all programs", [round(sum(r["by_band"][k] for r in data["programs"]) / data["bands"][KEYS.index(k)]["population"]) for k in KEYS])
    for n in data["not_allocated"]:
        print("not allocated:", n["name"].ljust(44), f"{n['dollars'] / 1e9:6,.1f}B")


if __name__ == "__main__":
    main()
