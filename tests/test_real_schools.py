"""The school ledger extract in data/raw and the committed page data."""
import gzip
import json

import pytest

from sd_spend.io import RAW, ROOT
from sd_spend.schools import CATEGORY_ORDER, parse_districts, parse_ledger, parse_titles, summarize


def raw(rel: str) -> str:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes()).decode()


def committed() -> dict:
    return json.loads((ROOT / "site" / "data" / "schools.json").read_text())


def test_real_ledger_covers_san_diego_county_districts():
    districts = parse_districts(raw("cde/sacs2324_san_diego_districts.csv"))
    assert districts["68338"]["name"] == "San Diego Unified" and 80_000 < districts["68338"]["ada"] < 95_000
    summary = summarize(parse_ledger(raw("cde/sacs2324_san_diego_ledger.csv")), parse_titles(raw("cde/sacs2324_funds.csv")))
    assert set(summary) <= set(districts)
    unified = summary["68338"]
    assert 1.5e9 < sum(unified["spending"].values()) < 2.5e9
    assert sum(unified["spending"].values()) == pytest.approx(sum(unified["purpose"].values()))
    assert unified["other_funds"]["Building Fund"] > 0
    assert "Special Education Pass-Through Fund" not in summary["10371"]["other_funds"] and summary["10371"]["passed_through"] > 200e6
    assert summary["67983"]["charter_schools"] > 40e6 and "Charter Schools Enterprise Fund" not in summary["67983"]["other_funds"]


def test_committed_school_data_adds_up_and_is_plausible():
    d = committed()
    labels = [c["label"] for c in d["categories"]]
    assert labels == [label for _, label in CATEGORY_ORDER]
    assert len(d["districts"]) >= 42
    total = payroll = 0.0
    for district in d["districts"]:
        assert set(district["spending"]) <= set(labels) and set(district["purpose"]) <= set(d["purposes"]) and set(district["revenue"]) <= set(d["revenues"])
        assert sum(district["spending"].values()) == pytest.approx(sum(district["purpose"].values()), abs=1)
        total += sum(district["spending"].values())
        payroll += sum(v for c in d["categories"] if c["group"] != "Everything else" for v in [district["spending"].get(c["label"], 0)])
    assert 7e9 < total < 8.5e9
    assert 0.75 < payroll / total < 0.88
    teachers = sum(x["spending"].get("Teacher salaries", 0) for x in d["districts"]) / total
    assert 0.25 < teachers < 0.40


def test_committed_school_data_separates_state_paid_pensions_and_local_taxes():
    d = committed()
    on_behalf = sum(x["spending"].get("Teacher pensions (CalSTRS), paid by the state on the district's behalf", 0) for x in d["districts"])
    district_paid = sum(x["spending"].get("Teacher pensions (CalSTRS), paid by the district", 0) for x in d["districts"])
    assert 0 < on_behalf < district_paid
    taxes = sum(x["revenue"].get("Local property taxes", 0) for x in d["districts"])
    passed_on = sum(x["revenue"].get("Property taxes passed to charter schools", 0) for x in d["districts"])
    assert taxes > 2e9 and passed_on < 0
    assert all(x["revenue"].get("Property taxes passed to charter schools", 0) <= 0 for x in d["districts"])
    via_agencies = sum(x["revenue"].get("Passed on by other school agencies (mostly state special-education money)", 0) for x in d["districts"])
    assert 150e6 < via_agencies < 350e6
