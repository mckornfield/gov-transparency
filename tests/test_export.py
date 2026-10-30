import pandas as pd

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
