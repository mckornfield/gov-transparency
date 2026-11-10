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
