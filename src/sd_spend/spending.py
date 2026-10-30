"""Turn the raw San Diego operating files into tidy spending tables, with reconciliation checks."""
import pandas as pd

# FY26 budget rows have a blank budget_cycle; they are treated as the adopted budget (see methods page).
BLANK_CYCLE_AS = "adopted"
UNCLASSIFIED = "Unclassified"
PENDING = "Description pending"
ID_COLS = {"account_number": str, "funds_center_number": str, "fund_number": str, "report_fy": str}
KEYS = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class", "account_group", "account"]


class ReconciliationError(AssertionError):
    pass


def read_operating(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=ID_COLS, keep_default_na=False)


def actuals_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["basis"] = "actual"
    return out


def budget_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cycle = df["budget_cycle"].where(df["budget_cycle"] != "", BLANK_CYCLE_AS)
    keep = cycle == "adopted"
    out = df[keep].copy()
    out["basis"] = "adopted"
    return out, {"proposed_rows_dropped": int((cycle == "proposed").sum())}


def _dept_lookups(depts: pd.DataFrame):
    usable = depts[depts["dept_group"] != PENDING]
    by_center = usable.drop_duplicates("funds_center_number").set_index("funds_center_number")["dept_group"]
    by_name = usable.groupby("dept_name")["dept_group"].agg(lambda s: s.mode().iloc[0])
    return by_center, by_name


def classify(df: pd.DataFrame, accounts: pd.DataFrame, depts: pd.DataFrame) -> pd.DataFrame:
    if not accounts["account_number"].is_unique:
        raise ReconciliationError("account reference has duplicate account_number values")
    by_center, by_name = _dept_lookups(depts)
    cols = ["account_number", "account_type", "account_class", "account_group"]
    out = df.merge(accounts[cols], on="account_number", how="left")
    for col in cols[1:]:
        out[col] = out[col].fillna(UNCLASSIFIED)
    group = out["funds_center_number"].map(by_center)
    group = group.fillna(out["dept_name"].map(by_name))
    out["dept_group"] = group.fillna(UNCLASSIFIED)
    out["fy"] = 2000 + out["report_fy"].astype(int)
    return out


def split_expenses(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_expense = df["account_number"].str.startswith("5")
    return df[is_expense], df[~is_expense]


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(KEYS, as_index=False)["amount"].sum()


def _totals(df: pd.DataFrame) -> pd.Series:
    return df.groupby(["basis", "fy"])["amount"].sum()


def _nested_totals(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for (basis, fy), amount in _totals(df).items():
        out.setdefault(basis, {})[str(fy)] = round(float(amount), 2)
    return out


def check_totals(expenses: pd.DataFrame, tidy: pd.DataFrame) -> None:
    diff = (_totals(expenses) - _totals(tidy)).abs()
    bad = diff[diff > 0.5]
    if len(bad):
        raise ReconciliationError(f"aggregation changed totals:\n{bad}")


def check_budget_vs_actual(tidy: pd.DataFrame, tolerance: float = 0.25) -> None:
    totals = _totals(tidy).unstack("basis")
    both = totals.dropna(subset=["actual", "adopted"])
    ratio = both["adopted"] / both["actual"] - 1
    bad = ratio[ratio.abs() > tolerance]
    if len(bad):
        raise ReconciliationError(f"adopted budget differs from actuals by more than {tolerance:.0%}:\n{bad}")


def check_yoy(tidy: pd.DataFrame, limit: float = 0.4) -> None:
    totals = _totals(tidy).unstack("basis").sort_index()
    change = totals.pct_change(fill_method=None)
    bad = change[(change.abs() > limit).any(axis=1)]
    if len(bad):
        raise ReconciliationError(f"year-over-year total changed by more than {limit:.0%}:\n{bad}")


def build_spending(actuals: pd.DataFrame, budget: pd.DataFrame, accounts: pd.DataFrame,
                   depts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    budget_rows, report = budget_frame(budget)
    combined = pd.concat([actuals_frame(actuals), budget_rows], ignore_index=True)
    classified = classify(combined, accounts, depts)
    expenses, other = split_expenses(classified)
    tidy = aggregate(expenses)
    check_totals(expenses, tidy)
    check_budget_vs_actual(tidy)
    check_yoy(tidy)
    report["excluded_non_expense"] = _nested_totals(other)
    report["blank_account"] = _nested_totals(other[other["account_number"] == ""])
    report["unclassified_amount"] = round(float(
        tidy.loc[(tidy["dept_group"] == UNCLASSIFIED) | (tidy["account_class"] == UNCLASSIFIED), "amount"].sum()), 2)
    return tidy, report


def build_population(raw: pd.DataFrame, first_fy: int = 2011, last_fy: int = 2026) -> pd.DataFrame:
    reported_by_year = (raw.assign(fy=raw["fiscal_year"].astype(int),
                                   population=raw["estimated_population"].astype(float))
                        .drop_duplicates("fy").set_index("fy")["population"])
    years = pd.RangeIndex(first_fy, last_fy + 1)
    reported = reported_by_year.reindex(years)
    filled = reported.interpolate(limit_area="inside")
    source = pd.Series("reported", index=years)
    source[reported.isna() & filled.notna()] = "interpolated"
    source[filled.isna()] = "carried_forward"
    filled = filled.ffill()
    return pd.DataFrame({"fy": list(years), "population": filled.round().astype(int).to_numpy(),
                         "source": source.to_numpy()})
