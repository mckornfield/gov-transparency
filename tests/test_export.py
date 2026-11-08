import pandas as pd
import pytest

from sd_spend import export
from sd_spend.spending import KEYS


def test_spending_payload_collapses_to_class_level_and_rounds():
    tidy = pd.DataFrame([
        ("actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Wages", 100.4),
        ("actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Overtime", 50.4),
        ("actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", "Books", "Books", -3.0),
    ], columns=KEYS + ["amount"])
    payload = export.spending_payload(tidy)
    assert payload["columns"] == ["basis", "fy", "dept_group", "dept_name", "account_type",
                                  "account_class", "amount"]
    assert sorted(payload["rows"]) == [
        ["actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", -3],
        ["actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", 151],
    ]


def test_population_payload():
    pop = pd.DataFrame({"fy": [2011, 2012], "population": [10, 20], "source": ["reported", "interpolated"]})
    assert export.population_payload(pop) == {"rows": [
        {"fy": 2011, "population": 10, "source": "reported"},
        {"fy": 2012, "population": 20, "source": "interpolated"},
    ]}


def test_meta_payload_reports_latest_years_and_retrieval_date():
    tidy = pd.DataFrame([
        ("actual", 2022, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Wages", 1.0),
        ("actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Wages", 1.0),
        ("adopted", 2026, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Wages", 1.0),
    ], columns=KEYS + ["amount"])
    assert export.meta_payload(tidy, "2026-10-29") == {
        "retrieved": "2026-10-29", "latest_actual_fy": 2023, "latest_budget_fy": 2026}


def test_vendors_payload_shapes_years_coverage_and_sorted_vendors():
    vendors = pd.DataFrame([
        (2024, "a", "Alpha Inc", "1; 2", 100.4),
        (2025, "a", "Alpha Inc", "1; 3", 50.4),
        (2024, "b", "Beta LLC", "9", 500.0),
    ], columns=["fy", "vendor_key", "vendor_name", "vendor_ids", "amount"])
    cov = {2024: {"vendors_total": 600.4, "reference_total": 1000.0, "reference_basis": "actual"},
           2025: {"vendors_total": 50.4, "reference_total": 90.0, "reference_basis": "adopted"}}
    payload = export.vendors_payload(vendors, cov)
    assert payload["years"] == [2024, 2025]
    assert payload["coverage"]["2025"] == {"vendors_total": 50, "reference_total": 90, "reference_basis": "adopted"}
    assert [v["name"] for v in payload["vendors"]] == ["Beta LLC", "Alpha Inc"]  # 500 > 150.8
    assert payload["vendors"][1] == {"name": "Alpha Inc", "ids": "1; 2; 3", "amounts": {"2024": 100, "2025": 50}}


def test_peers_payload_has_one_snapshot_per_survey_year_with_price_levels():
    import pandas as pd
    from sd_spend.export import peers_payload

    def row(fy, city, home, pop, fy_end, amount, per, rpp):
        return {"fiscal_year": fy, "city": city, "state": "CA", "region": "West", "is_home": home, "reference": city == "Dallas", "population": pop,
                "fy_end": fy_end, "group": "police", "label": "Police", "kind": "core", "amount_usd": amount,
                "per_resident": per, "rpp": rpp}
    tidy = pd.DataFrame([
        row(2024, "San Diego", True, 100, "0630", 5000, 50.0, 112.34567),
        row(2024, "Dallas", False, 200, "0930", 6000, 30.0, 101.0),
        row(2023, "San Diego", True, 90, "0630", 4000, 44.444444, 111.0),
        row(2023, "Dallas", False, 190, "0930", 5000, 26.0, 100.0),
    ])
    p = peers_payload(tidy)
    assert p["home"] == "San Diego"
    assert p["groups"] == [{"key": "police", "label": "Police", "kind": "core"}]
    assert [y["fiscal_year"] for y in p["years"]] == [2023, 2024]  # oldest first
    latest = p["years"][-1]
    assert [c["city"] for c in latest["cities"]] == ["San Diego", "Dallas"]
    assert latest["cities"][1]["reference"] is True and latest["cities"][0]["reference"] is False
    assert latest["cities"][0]["rpp"] == 112.35 and latest["cities"][0]["population"] == 100
    assert latest["rows"][0] == {"city": "San Diego", "group": "police", "amount": 5000, "per_resident": 50.0}
    assert p["years"][0]["rows"][0]["per_resident"] == 44.44


def test_homelessness_payload_keeps_missing_as_null_and_limits_hhap_to_configured_regions():
    import math
    from sd_spend.export import homelessness_payload

    cfg = {"home": "CA-1", "regions": [
        {"coc_id": "CA-1", "name": "Home", "role": "home", "hhap": {"coc": "Home CoC", "city": "Home", "county": "Home County"}},
        {"coc_id": "TX-1", "name": "Peer", "role": "peer"}],
        "hhap_rounds": {"r5": {"label": "Round 5", "pit_year": 2023}}}
    spm = pd.DataFrame([("CA-1 Home CoC", "CA-1", "M3", "2024", 5.0), ("California", None, "M3", "2024", 50.0),
                        ("CA-9 Other", "CA-9", "M3", "2024", 7.0), ("CA-1 Home CoC", "CA-1", "PIT Count", "2021", math.nan)],
                       columns=["location", "coc_id", "metric", "period", "value"])
    hhap = pd.DataFrame([("Round 5", "coc", "Home CoC", 10.4, 2017), ("Round 5", "city", "Home", 20.6, 2017),
                         ("Round 5", "county", "Home County", 30.0, 2017), ("Round 5", "city", "Elsewhere", 99.0, 2023)],
                        columns=["round", "kind", "name", "amount", "basis_year"])
    pit = pd.DataFrame([("CA-1", 2021, math.nan, 4.0, math.nan), ("CA-1", 2022, 9.0, 4.0, 5.0)],
                       columns=["coc_id", "year", "total", "sheltered", "unsheltered"]).assign(carried=[False, True])
    city = [{"fy": 2024, "expenditures": 42.4, "revenue": 34.6, "kind": "actual"}]
    pop = pd.DataFrame({"fy": [2024], "population": [1_380_000], "source": ["reported"]})
    p = homelessness_payload(spm, hhap, city, pit, pop, cfg)
    assert p["hhap"] == [{"round": "Round 5", "coc_id": "CA-1", "pit_year": 2017, "coc": 10, "city": 21, "county": 30}]
    assert {r["coc_id"] for r in p["measures"]} == {"CA-1", "CA"}  # CA-9 is not configured; California is the state row
    assert p["pit"][0] == {"coc_id": "CA-1", "year": 2021, "total": None, "sheltered": 4, "unsheltered": None, "carried": False}
    assert [r["role"] for r in p["regions"]] == ["home", "peer"] and "total" not in p["city"][0]
    assert p["population"] == [{"fy": 2024, "population": 1380000}]
    mixed = hhap.assign(basis_year=[2017, 2023, 2017, 2023])
    with pytest.raises(ValueError, match="different count years"):
        homelessness_payload(spm, mixed, city, pit, pop, cfg)
