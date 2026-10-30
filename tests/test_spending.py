import pandas as pd
import pytest

from sd_spend import spending as sp

ACCOUNTS = pd.DataFrame({
    "account_type": ["Personnel", "Non-Personnel", "Non-Personnel", "Property Tax Revenue"],
    "account_class": ["Personnel Cost", "Contracts & Services", "Transfers Out", "Property Taxes"],
    "account_group": ["Salaries", "Consultants", "Transfers Out", "Property Tax"],
    "account": ["Salaried Wages", "Consulting", "Transfer Out", "Prop Tax"],
    "account_number": ["500011", "510001", "590001", "400001"],
})
DEPTS = pd.DataFrame({
    "dept_group": ["Police", "Library", "Description pending"],
    "dept_name": ["Police", "Library", "Description pending"],
    "dept_division": ["x", "y", "z"],
    "dept_section": ["x", "y", "z"],
    "funds_center": ["a", "b", "DELETE"],
    "funds_center_number": ["1001", "2002", "0"],
})


def actuals_df(rows):
    return pd.DataFrame(rows, columns=["amount", "report_fy", "fund_type", "fund_number",
                                       "dept_name", "funds_center_number", "account", "account_number"])


def budget_df(rows):
    return pd.DataFrame(rows, columns=["amount", "report_fy", "budget_cycle", "fund_type", "fund_number",
                                       "dept_name", "funds_center_number", "account", "account_number"])


def test_budget_frame_keeps_adopted_and_blank_cycle_drops_proposed():
    df = budget_df([
        (100.0, "24", "adopted", "General Fund", "1", "Police", "1001", "x", "500011"),
        (100.0, "24", "proposed", "General Fund", "1", "Police", "1001", "x", "500011"),
        (50.0, "26", "", "General Fund", "1", "Police", "1001", "x", "500011"),
    ])
    out, report = sp.budget_frame(df)
    assert sorted(out["report_fy"]) == ["24", "26"]
    assert set(out["basis"]) == {"adopted"}
    assert report == {"proposed_rows_dropped": 1}


def test_classify_maps_reference_and_falls_back_to_unclassified():
    df = actuals_df([
        (10.0, "23", "General Fund", "1", "Police", "1001", "Salaried Wages", "500011"),
        (5.0, "23", "General Fund", "1", "Library", "9999", "Mystery", "599999"),
        (7.0, "23", "General Fund", "1", "Unknown Dept", "9998", "Consulting", "510001"),
    ])
    out = sp.classify(sp.actuals_frame(df), ACCOUNTS, DEPTS)
    by_center = out.set_index("funds_center_number")
    assert by_center.loc["1001", "dept_group"] == "Police"
    assert by_center.loc["1001", "account_class"] == "Personnel Cost"
    # funds center missing from the reference falls back to the dept_name mapping
    assert by_center.loc["9999", "dept_group"] == "Library"
    # unmapped account number
    assert by_center.loc["9999", "account_class"] == sp.UNCLASSIFIED
    # neither funds center nor dept_name known
    assert by_center.loc["9998", "dept_group"] == sp.UNCLASSIFIED
    assert (out["fy"] == 2023).all()


def test_classify_rejects_duplicate_account_numbers():
    dup = pd.concat([ACCOUNTS, ACCOUNTS.iloc[[0]]], ignore_index=True)
    df = actuals_df([(1.0, "23", "General Fund", "1", "Police", "1001", "x", "500011")])
    with pytest.raises(sp.ReconciliationError):
        sp.classify(sp.actuals_frame(df), dup, DEPTS)


def test_split_expenses_separates_revenue_and_blank_accounts():
    df = actuals_df([
        (10.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (99.0, "23", "General Fund", "1", "Police", "1001", "rev", "400001"),
        (3.0, "23", "General Fund", "1", "Police", "1001", "blank", ""),
    ])
    expenses, other = sp.split_expenses(sp.actuals_frame(df))
    assert list(expenses["amount"]) == [10.0]
    assert sorted(other["amount"]) == [3.0, 99.0]


def test_build_spending_keeps_negatives_and_reports_excluded():
    actuals = actuals_df([
        (100.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (-20.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (40.0, "23", "General Fund", "1", "Library", "2002", "x", "510001"),
        (500.0, "23", "General Fund", "1", "Police", "1001", "rev", "400001"),
    ])
    budget = budget_df([
        (105.0, "23", "adopted", "General Fund", "1", "Police", "1001", "x", "500011"),
        (42.0, "23", "adopted", "General Fund", "1", "Library", "2002", "x", "510001"),
        (999.0, "23", "proposed", "General Fund", "1", "Police", "1001", "x", "500011"),
        (8.0, "26", "", "General Fund", "1", "Police", "5555", "x", ""),
    ])
    tidy, report = sp.build_spending(actuals, budget, ACCOUNTS, DEPTS)
    total = tidy.groupby(["basis", "fy"])["amount"].sum()
    assert total[("actual", 2023)] == 120.0
    assert total[("adopted", 2023)] == 147.0
    assert ("adopted", 2026) not in total.index
    assert list(tidy.columns) == sp.KEYS + ["amount"]
    assert report["proposed_rows_dropped"] == 1
    assert report["excluded_non_expense"]["adopted"]["2026"] == 8.0
    assert report["excluded_non_expense"]["actual"]["2023"] == 500.0
    assert report["blank_account"] == {"adopted": {"2026": 8.0}}


def test_check_totals_detects_a_lost_row():
    expenses = pd.DataFrame({"basis": ["actual"], "fy": [2023], "amount": [100.0]})
    tidy = pd.DataFrame({"basis": ["actual"], "fy": [2023], "amount": [90.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_totals(expenses, tidy)


def test_check_budget_vs_actual_flags_double_counting():
    tidy = pd.DataFrame({"basis": ["actual", "adopted"], "fy": [2023, 2023], "amount": [100.0, 210.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_budget_vs_actual(tidy)
    ok = pd.DataFrame({"basis": ["actual", "adopted"], "fy": [2023, 2023], "amount": [100.0, 110.0]})
    sp.check_budget_vs_actual(ok)


def test_check_yoy_flags_a_doubled_year():
    tidy = pd.DataFrame({"basis": ["adopted"] * 3, "fy": [2023, 2024, 2025],
                         "amount": [100.0, 105.0, 210.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_yoy(tidy)
