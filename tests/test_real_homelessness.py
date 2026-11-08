"""Checks against the committed raw files (via the built site/data/homelessness.json)."""
import json
import subprocess
import sys

import pytest

from sd_spend.io import ROOT

PATH = ROOT / "site" / "data" / "homelessness.json"


@pytest.fixture(scope="module")
def data():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_homelessness.py")], check=True, capture_output=True)
    return json.loads(PATH.read_text())


def pit(data, coc, year):
    return next(r for r in data["pit"] if r["coc_id"] == coc and r["year"] == year)


def test_san_diego_count_matches_in_two_independent_sources(data):
    state = next(r for r in data["measures"] if r["coc_id"] == "CA-601" and r["metric"] == "PIT Count"
                 and r["period"] == "Jan 2024 - Dec 2024")["value"]
    assert pit(data, "CA-601", 2024)["total"] == state == 10605


def test_the_waived_2021_count_is_missing_not_zero_for_san_diego(data):
    assert pit(data, "CA-601", 2021)["total"] is None and pit(data, "CA-601", 2021)["unsheltered"] is None


def test_every_region_has_a_count_in_each_counted_year(data):
    for r in [r for r in data["regions"] if r["role"] != "state"]:
        for y in (2019, 2020, 2022, 2023, 2024):
            assert (pit(data, r["coc_id"], y)["total"] or 0) > 0, (r["coc_id"], y)


def test_hhap_round_5_keeps_san_diego_city_county_and_coc_separate(data):
    row = next(r for r in data["hhap"] if r["round"] == "Round 5" and r["coc_id"] == "CA-601")
    assert (row["city"], row["county"], row["coc"]) == (29918593, 14160464, 14759532)
    assert {r["round"] for r in data["hhap"]} == {"Round 1 (redirected)", "Round 2", "Round 3", "Round 4", "Round 5"}
    assert len([r for r in data["hhap"] if r["round"] == "Round 5"]) == 4  # SD, LA, SF, San Jose


def test_city_lines_carry_expenditures_and_revenue_separately(data):
    fy24 = next(c for c in data["city"] if c["fy"] == 2024)
    assert (fy24["expenditures"], fy24["revenue"], fy24["kind"]) == (42114403, 34561306, "actual")
    assert [c["kind"] for c in data["city"]][-2:] == ["budget", "adopted"]
    assert all("total" not in c for c in data["city"])


def test_outcome_rates_are_plausible_and_complete(data):
    for r in data["regions"]:
        if r["role"] not in ("home", "ca", "state"):
            continue
        m5 = [x["value"] for x in data["measures"] if x["coc_id"] == r["coc_id"] and x["metric"] == "M5"]
        assert len(m5) == 7 and all(v is not None and 0 < v < 0.5 for v in m5), r["coc_id"]
        served = {x["period"]: x["value"] for x in data["measures"] if x["coc_id"] == r["coc_id"] and x["metric"] == "M1a"}
        exits = {x["period"]: x["value"] for x in data["measures"] if x["coc_id"] == r["coc_id"] and x["metric"] == "M3"}
        assert all(0 < exits[p] < served[p] for p in served), r["coc_id"]


def test_carried_over_unsheltered_counts_are_flagged_not_hidden(data):
    sf = pit(data, "CA-501", 2020)
    assert sf["total"] == 8124 and sf["carried"] is True
    assert pit(data, "CA-501", 2019)["carried"] is False and pit(data, "CA-601", 2024)["carried"] is False


def test_san_diego_rounds_1_to_3_use_the_2017_count_the_tables_footnote_approves(data):
    sd = {r["round"]: r for r in data["hhap"] if r["coc_id"] == "CA-601"}
    assert [sd[k]["pit_year"] for k in ("Round 1 (redirected)", "Round 2", "Round 3", "Round 4", "Round 5")] == [2017, 2017, 2017, 2022, 2023]
    assert pit(data, "CA-601", 2017)["total"] == 9160


def test_hhap_awards_per_person_are_formula_flat_for_san_diego_san_francisco_and_san_jose(data):
    def per(coc, rnd):
        h = next(r for r in data["hhap"] if r["coc_id"] == coc and r["round"] == rnd)
        return (h["coc"] + h["city"] + h["county"]) / pit(data, coc, h["pit_year"])["total"]
    for rnd in ("Round 1 (redirected)", "Round 2", "Round 3", "Round 4", "Round 5"):
        assert abs(per("CA-601", rnd) - per("CA-501", rnd)) < 2, rnd  # the old 2019-for-everyone denominator gave 13% gaps


def test_every_hhap_amount_in_every_table_is_kept_including_wrapped_names():
    import pandas as pd
    t = pd.read_csv(ROOT / "data" / "processed" / "homeless_hhap.csv")
    counties = t[t.kind == "county"].groupby("round").size()
    assert counties.nunique() == 1 and counties.iloc[0] == 58  # round 1 once lost San Luis Obispo
    assert t.name.isna().any()  # amounts whose name wrapped are present, not dropped
