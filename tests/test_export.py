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
