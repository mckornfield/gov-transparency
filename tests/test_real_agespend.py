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
