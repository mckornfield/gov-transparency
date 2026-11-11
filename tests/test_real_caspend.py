"""The California parsers against the real 2023-24 files in data/raw, and the committed page data."""
import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from sd_spend.caspend import (parse_calworks_persons, parse_dds_ages, parse_department_programs, parse_ihss_ages, parse_schedule9,
                              parse_ssi_state_ages, parse_state_population, state_funds)
from sd_spend.io import RAW, ROOT

KEYS = ["0-18", "19-44", "45-64", "65-84", "85+"]
needs_poppler = pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext (poppler) is not installed")


def raw(rel: str) -> bytes:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes())


def pdf(rel: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.pdf"
        path.write_bytes(raw(rel))
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True).stdout


def committed() -> dict:
    return json.loads((ROOT / "site" / "data" / "ca-age-spending.json").read_text())


@needs_poppler
def test_real_schedule9_totals_for_2023_24():
    s9 = parse_schedule9(pdf("ca/schedule9_2025_26_gb.pdf"))
    assert round(s9["GRAND TOTAL"]["total"] / 1e9, 1) == 305.3
    assert round(s9["GRAND TOTAL"]["federal"] / 1e9, 1) == 150.9
    assert round(s9["6100"]["total"] / 1e9, 1) == 62.6
    assert sum(1 for k in s9 if k.isdigit()) > 150
    assert s9["4260"]["section"] == "TOTALS, HEALTH AND HUMAN SERVICES" and s9["9889"]["section"] == "TOTALS, GENERAL GOVERNMENT"


@needs_poppler
def test_real_social_services_programs_add_up_to_schedule9():
    s9 = parse_schedule9(pdf("ca/schedule9_2025_26_gb.pdf"))
    programs = parse_department_programs(pdf("ca/dss_5180_2025_26_gb.pdf"))
    assert {"CalWORKs", "IHSS", "SSI/SSP", "Child Care"} <= set(programs)
    assert sum(state_funds(f) for f in programs.values()) == pytest.approx(s9["5180"]["total"], rel=0.005)
    assert round(state_funds(programs["IHSS"]) / 1e9, 1) == 8.0


def test_real_california_population_and_recipient_counts():
    people = parse_state_population(raw("census/sc-est2024-agesex-civ.csv").decode(), "6", 2024)
    assert 38e6 < sum(people.values()) < 40e6
    months = [f"2023-{m:02d}" for m in range(7, 13)] + [f"2024-{m:02d}" for m in range(1, 7)]
    dds = parse_dds_ages(raw("ca/dds_consumers_by_age_gender.csv").decode("utf-8-sig"), months)
    assert 400_000 < sum(dds.values()) < 500_000 and len(dds) == 11
    ihss = parse_ihss_ages(raw("ca/ihss_program_data_jan2024.xlsx"))
    assert 700_000 < sum(ihss.values()) < 800_000
    calworks = parse_calworks_persons(raw("ca/ca237cw_fy2023_24.xlsx"), "Statewide")
    assert calworks["children"] > 2 * calworks["adults"] > 0
    ssp = parse_ssi_state_ages(raw("ssa/ssi_asr25.xlsx"), "California")
    assert ssp["65+"] > ssp["18-64"] > ssp["0-17"]


def test_committed_page_data_adds_up():
    d = committed()
    assert d["year_label"] == "2023-24" and [b["key"] for b in d["bands"]] == KEYS
    for p in d["programs"]:
        assert p["dollars"] == pytest.approx(sum(p["by_band"][k] for k in KEYS))
        assert all(p["by_band"][k] >= 0 for k in KEYS) and p["method"] in ("published", "proxy")
    assert d["allocated"] == pytest.approx(sum(p["dollars"] for p in d["programs"]))
    assert d["allocated"] < d["person_directed"] < d["total_outlays"]
    assert d["allocated"] + sum(n["dollars"] for n in d["not_allocated"]) == pytest.approx(d["total_outlays"], abs=1e6)
    assert all(n["dollars"] > 0 and n["reason"] for n in d["not_allocated"])


def test_committed_page_data_keeps_federal_money_out_and_children_highest():
    d = committed()
    assert d["federal_through"] > 100e9  # shown for information only
    assert d["total_outlays"] < 320e9  # state funds only: with federal funds it would be over $450B
    per = {b["key"]: sum(p["by_band"][b["key"]] for p in d["programs"]) / b["population"] for b in d["bands"]}
    assert min(per["0-18"], per["85+"]) > per["45-64"]  # which of the two ends is higher is within the estimate's error
    assert all(v < 100_000 for v in per.values())


def test_real_tightening_sources_for_developmental_services_and_medi_cal():
    from sd_spend.caspend import parse_dds_spending_ages, parse_medi_cal_eligibles, parse_medicaid_groups
    pos = parse_dds_spending_ages(raw("ca/dds_pos_statewide_fy2023_24.xlsx"))
    assert 0.7 < pos["22+"] / sum(pos.values()) < 0.8 and round(sum(pos.values()) / 1e9, 1) == 10.3
    groups = parse_medicaid_groups(raw("macpac/exhibit21_fy2023.xlsx"), "California")
    assert groups["new adult"] > groups["disabled"] > groups["aged"] > groups["other adult"] > groups["child"]
    months = [f"2023-{m:02d}" for m in range(7, 13)] + [f"2024-{m:02d}" for m in range(1, 7)]
    text = raw("ca/medi_cal_eligibles_age_sex.csv").decode("utf-8-sig")
    assert 14e6 < sum(parse_medi_cal_eligibles(text, months).values()) < 16e6
    assert 0.9e6 < sum(parse_medi_cal_eligibles(text, months, "San Diego").values()) < 1.2e6


def test_committed_developmental_services_dollars_go_mostly_to_adults():
    row = next(p for p in committed()["programs"] if p["program"] == "Developmental services")
    assert row["method"] == "proxy" and row["by_band"]["0-18"] < 0.3 * row["dollars"]
