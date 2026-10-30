"""Checks against the committed processed data; guards the known traps in the raw files."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spending = pd.read_csv(ROOT / "data/processed/spending.csv")
population = pd.read_csv(ROOT / "data/processed/population.csv")
site = json.loads((ROOT / "site/data/spending.json").read_text())
report = json.loads((ROOT / "data/processed/build_report.json").read_text())


def total(basis, fy, df=spending):
    return df[(df["basis"] == basis) & (df["fy"] == fy)]["amount"].sum()


def test_fy2023_actual_is_about_four_billion():
    assert 3.5e9 < total("actual", 2023) < 4.5e9


def test_adopted_budget_is_not_double_counted():
    # raw FY24 has adopted+proposed rows; summing both gives about $8.9B
    assert 3.5e9 < total("adopted", 2024) < 6e9
    assert 3.5e9 < total("adopted", 2025) < 6e9
    assert report["proposed_rows_dropped"] > 0


def test_fy2026_blank_cycle_rows_are_kept():
    assert total("adopted", 2026) > 1e9


def test_unmapped_funds_centers_are_classified_not_dropped():
    # 388 FY26 funds centers are missing from the reference; the dept_name fallback must still place them
    fy26 = spending[(spending["basis"] == "adopted") & (spending["fy"] == 2026)]
    unclassified = fy26.loc[fy26["dept_group"] == "Unclassified", "amount"].sum()
    assert unclassified < 0.02 * fy26["amount"].sum()
    assert fy26["dept_group"].nunique() > 20


def test_blank_account_rows_are_reported_not_hidden():
    assert report["blank_account"]["adopted"]["2026"] != 0


def test_population_covers_every_fiscal_year():
    assert list(population["fy"]) == list(range(2011, 2027))
    assert set(population["source"]) <= {"reported", "interpolated", "carried_forward"}
    assert population.loc[population["fy"] == 2026, "source"].item() == "carried_forward"
    assert population.loc[population["fy"] == 2023, "source"].item() == "reported"


def test_site_json_conserves_totals():
    rows = pd.DataFrame(site["rows"], columns=site["columns"])
    for (basis, fy), expected in spending.groupby(["basis", "fy"])["amount"].sum().items():
        got = rows[(rows["basis"] == basis) & (rows["fy"] == fy)]["amount"].sum()
        n = ((rows["basis"] == basis) & (rows["fy"] == fy)).sum()
        assert abs(got - expected) <= 0.5 * n + 1, (basis, fy)


def test_meta_json_states_data_age():
    meta = json.loads((ROOT / "site/data/meta.json").read_text())
    assert meta["latest_actual_fy"] == 2023
    assert meta["latest_budget_fy"] == 2026
    assert len(meta["retrieved"]) == 10 and meta["retrieved"][4] == "-"
