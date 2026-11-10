"""Build who receives federal dollars by age bracket for FY2024 from the saved raw files.

Writes data/processed/age_spending.csv and site/data/age-spending.json. Needs pdftotext (poppler) for the SSA tables.
"""
import csv
import gzip
import io
import json
import shutil
import subprocess
import tempfile
import zipfile

import xlrd
from pathlib import Path

from sd_spend.ageallocate import BANDS, KEYS, add, band_of, by_parent_age, from_shares, generation_labels, population_by_band, scale, spread_ages, ssa_other_adults, ssa_workers_and_children, va_bands
from sd_spend.agespend import (parse_cms_shares, parse_mts_outlays, parse_nhe_federal_medicaid, parse_omb_line, parse_population,
                               parse_ssa_ages, parse_ssa_other_adults, parse_va_ages, ssa_annual_dollars, parse_fns_costs, parse_hud_housing, parse_snap_ages, parse_births_by_mother, parse_irs_credits, parse_ssi, parse_ui_ages, person_directed_total)
from sd_spend.io import RAW, ROOT

YEAR = 2024
CMS_GROUPS = ("0-18", "19-44", "45-64", "65-84", "85+")
VA_COMP = {"34 and under": (19, 34), "35-54": (35, 54), "55-74": (55, 74), "75 and over": (75, 100)}
VA_PENSION = {"34 and under": (19, 34), "35-64": (35, 64), "65-74": (65, 74), "75 and over": (75, 100)}
HOUSING_RANGES = {"24 and under": (18, 24), "25-50": (25, 50), "51-61": (51, 61), "62-84": (62, 84), "85 and over": (85, 100)}
SNAP_RANGES = {"0-17": (0, 17), "18-35": (18, 35), "36-59": (36, 59), "60+": (60, 100)}
UI_RANGES = {"under 22": (16, 21), "22-24": (22, 24), "25-34": (25, 34), "35-44": (35, 44), "45-54": (45, 54), "55-59": (55, 59), "60-64": (60, 64), "65+": (65, 74)}
SSI_UNDER18 = {"0-4": (0, 4), "5-12": (5, 12), "13-17": (13, 17)}
SSI_ADULT = {"18-21": (18, 21), "22-25": (22, 25), "26-29": (26, 29), "30-39": (30, 39), "40-49": (40, 49), "50-59": (50, 59), "60-64": (60, 64)}
# Urban Institute Kids' Share FY2024 as reported in news coverage (Peter G. Peterson Foundation summary and others), not read at the source; a rough range check only.
KIDS_SHARE = {"per_child": 6860, "per_person_65_plus": 40050}


def raw(rel: str) -> bytes:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes())


def zipped(rel: str, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(raw(rel))) as z:
        return z.read(name)


def pdf_text(rel: str) -> str:
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext (poppler) is needed to read the SSA and FNS tables: brew install poppler")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "source.pdf"
        pdf.write_bytes(raw(rel))
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True).stdout


def build() -> dict:
    mts = parse_mts_outlays(json.loads(raw("treasury/mts_table9_fy2024_sep.json")))
    pop = parse_population(raw("census/nc-est2024-agesex-res.csv").decode(), YEAR)
    cms = parse_cms_shares(zipped("cms/age_and_sex_csv_files.zip", "age and Sex.csv").decode(), "2020", ("Medicare", "Medicaid"), CMS_GROUPS)
    omb = zipped("omb/hist_fy2027.zip", "hist03z2.xlsx")
    omb_line = lambda prefix: parse_omb_line(omb, prefix, YEAR)  # noqa: E731
    medicaid = parse_nhe_federal_medicaid(zipped("cms/nhe_tables.zip", "Table 05-3 Federal Government Sponsor Expenditures.xlsx"), YEAR)
    births = parse_births_by_mother(pdf_text("cdc/nvsr75_02_births_final_2024.pdf"))
    credits = parse_irs_credits(xlrd.open_workbook(file_contents=raw("irs/22in25ic.xls")).sheet_by_index(0), xlrd.open_workbook(file_contents=raw("irs/22in33ar.xls")).sheet_by_index(0))
    housing = parse_hud_housing(raw("hud/US_2024_2020census.xlsx"))
    ui = parse_ui_ages(raw("dol/ar203_eta203.csv").decode("latin-1"), "2023-10-01", "2024-09-30")
    ssi = parse_ssi(raw("ssa/ssi_asr25.xlsx"), YEAR)
    text = pdf_text("ssa/statcomps_2025_5a.pdf")
    snap = parse_snap_ages(pdf_text("fns/snap_characteristics_fy2023.pdf"))
    fns = parse_fns_costs(pdf_text("fns/keydata_jan2025_fy2024.pdf"), "FY 2024")
    comp = parse_va_ages(raw("va/va_compensation_by_age_fy2024.csv").decode(), "Compensation")
    pension = parse_va_ages(raw("va/va_pension_by_age_fy2024.csv").decode(), "Pension")

    workers = [ssa_annual_dollars(parse_ssa_ages(text, t)) for t in ("Table 5.A1.1", "Table 5.A1.2", "Table 5.A1.4")]
    ssa_shape = add(ssa_workers_and_children([p for part in workers for p in part]), ssa_other_adults(parse_ssa_other_adults(text), pop))
    va_money = add(va_bands(comp["bands"], comp["dollars"], pop, VA_COMP), va_bands(pension["bands"], pension["dollars"], pop, VA_PENSION))
    va_health = va_bands(comp["bands"], 1.0, pop, VA_COMP)

    programs = [
        ("Social Security", "Retirement", "published", f"SSA beneficiaries by age (Dec 2024), scaled to Treasury outlays; spouse and survivor benefits only come in three age groups and are spread by population",
         scale(ssa_shape, mts["Social Security"])),
        ("Medicare", "Health", "published", "CMS age shape of Medicare spending (2020, the latest) applied to FY2024 Treasury outlays",
         from_shares(mts["Medicare"], cms["Medicare"])),
        ("Medicaid (federal share)", "Health", "published", "CMS age shape of Medicaid spending (2020) applied to the federal portion of Medicaid payments (CMS, calendar 2024). The shape covers federal plus state spending; the federal match differs by group (higher for expansion adults, lower for older people), which this does not capture",
         from_shares(medicaid, cms["Medicaid"])),
        ("VA compensation and pension", "Veterans", "proxy", "VA recipients by age band (FY2024), spread within each band by population, scaled to OMB subfunction 701",
         scale(va_money, omb_line("701 Income security for veterans"))),
        ("VA health care", "Veterans", "proxy", "OMB subfunction 703 spread like VA compensation recipients by age (no VA health spending by age found)",
         scale(va_health, omb_line("703 Hospital and medical care"))),
        ("Elementary and secondary education", "Kids and education", "proxy", "OMB subfunction 501 spread over ages 5-18 by population",
         spread_ages(omb_line("501 Elementary"), 5, 18, pop)),
        ("Higher education and student aid", "Kids and education", "proxy", "OMB subfunction 502 spread over ages 18-29 by population. It may include student-loan accounting costs (estimates that move with policy), not only cash grants, and no age split of Pell grants or loans was used; treat it as the least certain row",
         spread_ages(omb_line("502 Higher education"), 18, 29, pop)),
        ("SNAP", "Food aid", "proxy", "FNS FY2024 SNAP cost spread by SNAP participants by age (FY2023 quality-control sample), assuming equal benefits per person; the 60+ group is spread over ages 60-100 by population",
         va_bands(snap, fns["SNAP"], pop, SNAP_RANGES)),
        ("School meals, child nutrition and WIC", "Food aid", "proxy", "FNS FY2024 child nutrition and WIC costs counted at ages 0-17 (mothers' share of WIC is counted with children)",
         spread_ages(fns["Child nutrition"] + fns["WIC"], 0, 17, pop)),
        ("HUD-assisted housing", "Housing aid", "proxy", "HUD units times average monthly federal spending (2024), counted at the age of the household head because the file gives no ages for other residents; children in assisted households are not counted as recipients",
         va_bands(housing["heads"], housing["dollars"], pop, HOUSING_RANGES)),
        ("Supplemental Security Income (federal)", "Income support", "proxy", "SSA federal SSI payments for 2024 (calendar year; state supplements are state money and left out), split across under 18, 18-64 and 65+ by SSA's December 2025 payments by age, then within the first two by recipients by finer age (under 65) and population; 65+ spread over 65-100 by population. Part of OMB subfunction 609",
         add(va_bands(ssi["under18_counts"], ssi["federal_dollars"] * ssi["group_shares"]["0-17"], pop, SSI_UNDER18),
             va_bands(ssi["adult_counts"], ssi["federal_dollars"] * ssi["group_shares"]["18-64"], pop, SSI_ADULT),
             spread_ages(ssi["federal_dollars"] * ssi["group_shares"]["65+"], 65, 100, pop))),
        ("Unemployment insurance", "Income support", "proxy", "OMB subfunction 603 spread like weeks of unemployment insurance claimed by age (Labor Department ETA 203, October 2023 to September 2024), assuming equal benefits per week; the 65+ group is spread over 65-74 by population and ages are within each group by population",
         va_bands(ui, omb_line("603 Unemployment compensation"), pop, UI_RANGES)),
        ("Earned income tax credit (claimed)", "Tax credits", "proxy", "IRS tax year 2022 credits claimed, put at the likely age of the parent (child age plus mother's age at birth, CDC 2024 births); the childless credit ($2.6B) is spread over ages 25-64 by population. Tax-year dollars, not FY2024 outlays",
         add(by_parent_age(credits["EITC"] - credits["EITC childless"], 0, 18, pop, births), spread_ages(credits["EITC childless"], 25, 64, pop))),
        ("Child tax credit (claimed)", "Tax credits", "proxy", "IRS tax year 2022 nonrefundable child and other dependent credit plus the refundable additional child tax credit, put at the likely age of the parent for children aged 0-16 (child age plus mother's age at birth). Fathers and other claimants are typically a few years older and are not modelled. Tax-year dollars, not FY2024 outlays",
         by_parent_age(credits["Child credit nonrefundable"] + credits["Child credit refundable"], 0, 16, pop, births)),
    ]
    population = population_by_band(pop)
    rows = []
    for name, group, method, note, by_band in programs:
        total = sum(by_band.values())
        if total <= 0 or any(v < 0 for v in by_band.values()):
            raise SystemExit(f"{name} has an impossible split")
        rows.append({"program": name, "group": group, "method": method, "kind": "tax credit" if group == "Tax credits" else "outlay", "note": note, "dollars": total, "by_band": by_band})
    allocated = sum(r["dollars"] for r in rows if r["kind"] == "outlay")
    tax_credits = sum(r["dollars"] for r in rows if r["kind"] == "tax credit")
    person_directed = person_directed_total(mts)
    if not 0 < allocated < person_directed < mts["Total"]:
        raise SystemExit("allocated dollars must be a share of person-directed outlays, which are a share of total outlays")
    per_person = {r["program"]: {k: r["by_band"][k] / population[k] for k in KEYS} for r in rows}
    if any(v > 100_000 for p in per_person.values() for v in p.values()):
        raise SystemExit("implausible per-person amount")
    older = sum(sum(r["by_band"][k] for k in ("65-84", "85+")) for r in rows) / (population["65-84"] + population["85+"])
    return {
        "fiscal_year": YEAR, "population_year": YEAR,
        "bands": [{"key": k, "lo": lo, "hi": min(hi, 100), "population": population[k], "generations": generation_labels((k, lo, hi), pop, YEAR)}
                  for k, lo, hi in BANDS],
        "programs": rows, "total_outlays": mts["Total"], "person_directed": person_directed, "allocated": allocated, "tax_credits": tax_credits,
        "own_check": {"per_child": sum(r["by_band"]["0-18"] for r in rows) / population["0-18"], "per_person_65_plus": older},
        "kids_share": KIDS_SHARE,
    }


def main() -> None:
    data = build()
    out = ROOT / "site" / "data" / "age-spending.json"
    out.write_text(json.dumps(data, indent=1) + "\n")
    with (ROOT / "data" / "processed" / "age_spending.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fiscal_year", "program", "group", "method", "band", "dollars"])
        for r in data["programs"]:
            for k in KEYS:
                writer.writerow([YEAR, r["program"], r["group"], r["method"], k, round(r["by_band"][k])])
    print(f"person-directed {data['person_directed'] / 1e9:,.0f}B, allocated {data['allocated'] / data['person_directed']:.0%} of it")
    print(f"allocated {data['allocated'] / 1e9:,.0f}B of {data['total_outlays'] / 1e9:,.0f}B ({data['allocated'] / data['total_outlays']:.0%})")
    print("own check", {k: round(v) for k, v in data["own_check"].items()}, "kids share", data["kids_share"])
    for r in data["programs"]:
        print(r["program"].ljust(40), f"{r['dollars'] / 1e9:8,.0f}B", [round(r["by_band"][k] / data["bands"][KEYS.index(k)]["population"]) for k in KEYS])


if __name__ == "__main__":
    main()
