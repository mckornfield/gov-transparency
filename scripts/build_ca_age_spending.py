"""Build who receives California state dollars by age bracket for 2023-24 from the saved raw files.

Writes data/processed/ca_age_spending.csv and site/data/ca-age-spending.json. Needs pdftotext (poppler) for the budget PDFs.
"""
import csv
import json

from build_age_spending import CMS_GROUPS, SSI_ADULT, pdf_text, raw, zipped
from sd_spend.ageallocate import BANDS, KEYS, add, generation_labels, population_by_band, spread_ages, va_bands
from sd_spend.agespend import parse_cms_shares, parse_ssi
from sd_spend.caspend import (parse_calworks_persons, parse_dds_ages, parse_dds_spending_ages, parse_department_programs, parse_ihss_ages,
                              parse_medi_cal_eligibles, parse_medicaid_groups, parse_schedule9, parse_ssi_state_ages, parse_state_population,
                              state_funds, state_share_by_group)
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
# The fraction of each Medicaid group's cost the state pays: California's regular federal match is 50%; the federal
# government pays 90% for adults covered by the Affordable Care Act expansion. Children's CHIP match and temporary
# pandemic increases are ignored.
STATE_RATE = {"child": 0.5, "new adult": 0.1, "other adult": 0.5, "disabled": 0.5, "aged": 0.5}
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

    # Developmental services: dollars follow regional-center spending for three age groups, then the people served within each.
    pos = parse_dds_spending_ages(raw("ca/dds_pos_statewide_fy2023_24.xlsx"))
    part = lambda key: total("4300") * pos[key] / sum(pos.values())  # noqa: E731
    young = ("3-5", "6-9", "10-13", "14-17", "18-21")
    dds_split = add(spread_ages(part("0-2"), 0, 2, pop),
                    va_bands({k: dds[k] for k in young}, part("3-21"), pop, DDS_RANGES),
                    va_bands({k: v for k, v in dds.items() if k not in young and k != "0-2"}, part("22+"), pop, DDS_RANGES))

    # Medi-Cal: California's spending by eligibility group, weighted by the share the state pays, then placed by age.
    group = state_share_by_group(parse_medicaid_groups(raw("macpac/exhibit21_fy2023.xlsx"), "California"), STATE_RATE)
    eligibles = parse_medi_cal_eligibles(raw("ca/medi_cal_eligibles_age_sex.csv").decode("utf-8-sig"), MONTHS)
    disabled_adults = parse_ssi(raw("ssa/ssi_asr25.xlsx"), POPULATION_YEAR)["adult_counts"]
    health = total("4260")
    disabled_kids = ssp["0-17"] / (ssp["0-17"] + ssp["18-64"])
    older = cms["Medicaid"]["65-84"] + cms["Medicaid"]["85+"]
    medi_cal = add(
        spread_ages(health * group["child"], 0, 18, pop),
        va_bands({k: eligibles[k] for k in ("19-44", "45-64")}, health * (group["new adult"] + group["other adult"]), pop, {"19-44": (19, 44), "45-64": (45, 64)}),
        spread_ages(health * group["disabled"] * disabled_kids, 0, 17, pop),
        va_bands(disabled_adults, health * group["disabled"] * (1 - disabled_kids), pop, SSI_ADULT),
        {"65-84": health * group["aged"] * cms["Medicaid"]["65-84"] / older, "85+": health * group["aged"] * cms["Medicaid"]["85+"] / older})
    hhs, education, general = "TOTALS, HEALTH AND HUMAN SERVICES", "TOTALS, EDUCATION", "TOTALS, GENERAL GOVERNMENT"
    expected = {"4260": hhs, "4300": hhs, "5180": hhs, "5195": hhs, "5196": hhs, "6100": education, "6300": education, "6440": education,
                "6610": education, "6870": education, "6980": education, "9889": general, "9650": general, "7900": "TOTALS, GOVERNMENT OPERATIONS", "9350": general}
    wrong = [code for code, section in expected.items() if s9.get(code, {}).get("section") != section]
    if wrong:
        raise SystemExit(f"Schedule 9 departments are not in the expected sections: {wrong}")
    retirement = total("6300") + total("9650") + total("7900")
    realignment = total("5195") + total("5196")

    programs = [
        ("K-12 education", "Schools", "proxy", "Department of Education state funds (Schedule 9) spread over ages 4-18 by population; includes transitional kindergarten and state preschool. The local property-tax share of school funding is local money and is not here",
         spread_ages(total("6100"), 4, 18, pop)),
        ("UC, CSU and Cal Grants", "Higher education", "proxy", "University of California, California State University and Student Aid Commission state funds (Schedule 9) spread over ages 18-29 by population; no enrolment by age was used",
         spread_ages(total("6440") + total("6610") + total("6980"), 18, 29, pop)),
        ("Community colleges", "Higher education", "proxy", "Community colleges state funds (Schedule 9, including bond-funded construction) spread over ages 18-39 by population; no enrolment by age was used",
         spread_ages(total("6870"), 18, 39, pop)),
        ("Medi-Cal and other state health care (state share)", "Health", "proxy", "Department of Health Care Services state funds (Schedule 9; almost all Medi-Cal, and including provider fees and drug rebates the budget counts as special funds), split in three steps: California's Medicaid spending by eligibility group (MACPAC, federal fiscal year 2023: children, expansion adults, other adults, disabled, aged); the share the state pays for each (assumed 10% for expansion adults and 50% for the rest); then age (children at 0-18, adults by Medi-Cal eligibles aged 19-44 and 45-64, disabled people by SSI recipients' ages, aged people between 65-84 and 85 and over by CMS's national shape)",
         medi_cal),
        ("Developmental services", "Disability and care", "published", "Department of Developmental Services state funds (Schedule 9) split like regional-center spending for ages 0-2, 3-21 and 22 and over (DDS annual purchase-of-service report, 2023-24), then within each like the people served by finer age group",
         dds_split),
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
        ("Retirement contributions (teachers, state retirees' health, CalPERS)", retirement, "Pay for past work, not a benefit by age"),
        ("School reserve withdrawal (Public School System Stabilization Account)", total("9889"), "Paid to K-12 schools and community colleges, but the split between them is not in these files; counting it would raise the youngest brackets"),
        ("Realignment money passed to counties", realignment, "State special funds that counties spend on health, mental health and social services, including county shares of in-home care and CalWORKs; no age split found"),
        ("Shared revenues sent to local governments", total("9350"), "Spent by cities and counties, not by the state"),
        ("Rest of education", s9["TOTALS, EDUCATION"]["total"] - total("6100") - total("6440") - total("6610") - total("6870") - total("6980") - s9["6300"]["total"],
         "Bond debt service, school facilities, the state library and other colleges and commissions: no age split used"),
        ("Rest of the Department of Social Services", s9["5180"]["total"] - dss_used, "Child welfare, county administration and other assistance: no age split found"),
        ("Rest of health and human services", s9[hhs]["total"] - total("4260") - total("4300") - total("5180") - realignment, "Public health, state hospitals and other departments: no age split found"),
        ("Everything else", everything - people - s9["TOTALS, CORRECTIONS AND REHABILITATION"]["total"] - (retirement - total("6300")) - total("9889") - total("9350"),
         "Transportation, courts, natural resources and general government (mostly collective costs), plus housing, employment and veterans programs with no age split"),
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
