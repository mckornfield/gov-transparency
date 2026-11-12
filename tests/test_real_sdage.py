"""The San Diego local age page: stored raw files parse, and the committed page data adds up."""
import gzip
import json

import pytest

from sd_spend.ageallocate import KEYS
from sd_spend.io import RAW, ROOT
from sd_spend.sdage import SOURCES, parse_county_budget, parse_county_population, parse_county_revenue


def raw(rel: str) -> str:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes()).decode("utf-8-sig")


def committed() -> dict:
    return json.loads((ROOT / "site" / "data" / "sd-age-spending.json").read_text())


def test_real_county_population_is_san_diego():
    people = parse_county_population(raw("census/cc-est2024-syasex-06.csv"), "073", "6")
    assert 3.2e6 < sum(people.values()) < 3.4e6


def test_real_county_budget_and_revenue_balance_by_department():
    budget = parse_county_budget(raw("sdcounty/open_budget_exp_fy2025.csv"), "2025")
    revenue = parse_county_revenue(raw("sdcounty/open_budget_rev_fy2025.csv"), "2025")
    assert 8.3e9 < sum(budget.values()) < 8.7e9
    spent = sum(v for k, v in budget.items() if k[1] == "Behavioral Health Services")
    paid = sum(sum(v.values()) for k, v in revenue.items() if k[0] == "Behavioral Health Services")
    assert paid == pytest.approx(spent, rel=0.001)
    assert sum(v["state"] for v in revenue.values()) > sum(v["federal"] for v in revenue.values()) > 1e9
    assert all(set(v) == set(SOURCES) for v in revenue.values())


def test_committed_page_data_adds_up_for_each_government():
    d = committed()
    assert [b["key"] for b in d["bands"]] == KEYS
    assert [g["name"] for g in d["governments"]] == ["School districts", "County of San Diego", "City of San Diego"]
    for p in d["programs"]:
        assert p["dollars"] == pytest.approx(sum(p["by_band"][k] for k in KEYS))
        assert all(p["by_band"][k] >= 0 for k in KEYS) and p["method"] in ("published", "proxy") and p["note"]
        if p["funded"] is not None:
            assert sum(p["funded"].values()) == pytest.approx(1) and all(v >= -0.02 for v in p["funded"].values())
    for g in d["governments"]:
        placed = sum(p["dollars"] for p in d["programs"] if p["group"] == g["name"])
        rest = sum(n["dollars"] for n in d["not_allocated"] if n["government"] == g["name"])
        assert placed == pytest.approx(g["allocated"]) and placed + rest == pytest.approx(g["total"], abs=1)
    assert d["allocated"] == pytest.approx(sum(p["dollars"] for p in d["programs"]))
    assert all(n["dollars"] >= 0 and n["reason"] for n in d["not_allocated"])


def test_committed_page_data_has_the_expected_shape():
    d = committed()
    by_name = {g["name"]: g for g in d["governments"]}
    assert 7.5e9 < by_name["School districts"]["total"] < 8e9
    assert by_name["City of San Diego"]["residents"] < by_name["County of San Diego"]["residents"]
    people = {b["key"]: b["population"] for b in d["bands"]}
    per = {k: sum(p.get("per_person", {}).get(k) or p["by_band"][k] / people[k] for p in d["programs"]) for k in KEYS}
    assert per["0-18"] > 5 * per["85+"] > 0  # schools dominate local spending on people
    city = [p for p in d["programs"] if p["group"] == "City of San Diego"]
    assert city and all(len(set(p["per_person"].values())) == 1 and p["funded"] is None for p in city)
    schools = next(p for p in d["programs"] if p["group"] == "School districts")
    assert 0.35 < schools["funded"]["local"] < 0.5 and schools["by_band"]["19-44"] == 0
    assert not any("prison" in p["program"].lower() or "jail" in p["program"].lower() for p in d["programs"])
