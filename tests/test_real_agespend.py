"""The parsers against the real FY2024 files saved in data/raw."""
import gzip
import io
import json
import zipfile

import pytest

from sd_spend.agespend import parse_cms_shares, parse_mts_outlays, parse_population, parse_va_ages
from sd_spend.io import RAW

CMS_GROUPS = ("0-18", "19-44", "45-64", "65-84", "85+")


def raw(rel: str) -> bytes:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes())


def test_treasury_outlays_for_fy2024():
    lines = parse_mts_outlays(json.loads(raw("treasury/mts_table9_fy2024_sep.json")))
    assert round(lines["Social Security"] / 1e9) == 1461
    assert round(lines["Medicare"] / 1e9) == 874
    assert round(lines["Total"] / 1e12, 2) == 6.75


def test_census_population_for_2024():
    people = parse_population(raw("census/nc-est2024-agesex-res.csv").decode(), 2024)
    assert 330e6 < sum(people.values()) < 350e6
    assert people[0] > 3_000_000


def test_cms_age_shapes_for_2020():
    with zipfile.ZipFile(io.BytesIO(raw("cms/age_and_sex_csv_files.zip"))) as z:
        text = z.read("age and Sex.csv").decode()
    shares = parse_cms_shares(text, "2020", ("Medicare", "Medicaid"), CMS_GROUPS)
    assert shares["Medicare"]["65-84"] > 0.6 and shares["Medicare"]["0-18"] < 0.001
    assert shares["Medicaid"]["0-18"] > 0.15


@pytest.mark.parametrize("kind,file", [("Compensation", "va_compensation_by_age_fy2024.csv"), ("Pension", "va_pension_by_age_fy2024.csv")])
def test_va_age_bands_for_fy2024(kind, file):
    got = parse_va_ages(raw(f"va/{file}").decode(), kind)
    assert got["recipients"] > 100_000
    assert got["dollars"] > 1e9


def committed():
    from sd_spend.io import ROOT
    return json.loads((ROOT / "site" / "data" / "age-spending.json").read_text())


def test_every_program_split_adds_to_its_total_and_stays_positive():
    for r in committed()["programs"]:
        assert sum(r["by_band"].values()) == pytest.approx(r["dollars"], rel=1e-9), r["program"]
        assert all(v >= 0 for v in r["by_band"].values()), r["program"]


def test_pinned_federal_totals_for_fy2024():
    by = {r["program"]: r["dollars"] for r in committed()["programs"]}
    assert round(by["Social Security"] / 1e9) == 1461
    assert round(by["Medicare"] / 1e9) == 874
    assert round(by["Medicaid (federal share)"] / 1e9) == 597


def test_coverage_is_between_zero_and_all_outlays():
    d = committed()
    assert 0 < d["allocated"] < d["total_outlays"]
    assert 0.3 < d["allocated"] / d["total_outlays"] < 0.8


def test_brackets_have_population_and_generations_but_dollars_are_not_cut_by_generation():
    d = committed()
    assert [b["key"] for b in d["bands"]] == ["0-18", "19-44", "45-64", "65-84", "85+"]
    assert all(b["population"] > 1_000_000 and b["generations"] for b in d["bands"])
    assert "Baby Boomers" in next(b for b in d["bands"] if b["key"] == "65-84")["generations"]


def test_older_people_get_far_more_per_person_than_children():
    d = committed()
    pop = {b["key"]: b["population"] for b in d["bands"]}
    child = sum(r["by_band"]["0-18"] for r in d["programs"]) / pop["0-18"]
    old = sum(r["by_band"]["65-84"] for r in d["programs"]) / pop["65-84"]
    assert old > 3 * child


def test_food_aid_programs_are_in_the_build_and_children_get_school_meals_only():
    by = {r["program"]: r for r in committed()["programs"]}
    assert round(by["SNAP"]["dollars"] / 1e9) == 100
    meals = by["School meals, child nutrition and WIC"]["by_band"]
    assert meals["0-18"] > 0 and all(meals[k] == 0 for k in ("19-44", "45-64", "65-84", "85+"))


def test_tax_credits_are_in_the_chart_but_not_in_the_share_of_outlays():
    d = committed()
    credits = [r for r in d["programs"] if r["kind"] == "tax credit"]
    assert {r["program"] for r in credits} == {"Earned income tax credit (claimed)", "Child tax credit (claimed)"}
    assert d["tax_credits"] == pytest.approx(sum(r["dollars"] for r in credits))
    assert d["allocated"] == pytest.approx(sum(r["dollars"] for r in d["programs"] if r["kind"] == "outlay"))
    for r in credits:  # a parent is almost never a child: nearly everything lands in the working-age brackets
        assert r["by_band"]["0-18"] < 0.01 * r["dollars"] and r["by_band"]["85+"] == 0


@pytest.mark.skipif(not __import__("shutil").which("pdftotext"), reason="needs poppler")
def test_real_births_by_mother_age_for_2024():
    import subprocess, tempfile, pathlib
    from sd_spend.agespend import parse_births_by_mother
    with tempfile.TemporaryDirectory() as tmp:
        pdf = pathlib.Path(tmp) / "b.pdf"
        pdf.write_bytes(raw("cdc/nvsr75_02_births_final_2024.pdf"))
        text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True).stdout
    got = parse_births_by_mother(text)
    assert sum(n for _, _, n in got) == 3_628_934 and got[3] == (25, 29, 990_817)


def test_real_unemployment_claims_by_age_for_fy2024():
    from sd_spend.agespend import parse_ui_ages
    got = parse_ui_ages(raw("dol/ar203_eta203.csv").decode("latin-1"), "2023-10-01", "2024-09-30")
    assert 20e6 < sum(got.values()) < 23e6
    assert got["25-34"] > got["65+"] > got["under 22"] > 0


def test_real_ssi_for_2024():
    from sd_spend.agespend import parse_ssi
    got = parse_ssi(raw("ssa/ssi_asr25.xlsx"), 2024)
    assert round(got["federal_dollars"] / 1e9) == 60
    assert got["group_shares"]["18-64"] > got["group_shares"]["65+"] > got["group_shares"]["0-17"]


def test_second_coverage_figure_counts_only_spending_on_people():
    d = committed()
    assert d["allocated"] < d["person_directed"] < d["total_outlays"]
    assert 0.6 < d["allocated"] / d["person_directed"] < 1.0
    names = {r["program"] for r in d["programs"]}
    assert {"Supplemental Security Income (federal)", "Unemployment insurance"} <= names
