"""Shape the tidy tables into the compact JSON the static site loads."""
import pandas as pd

SITE_COLUMNS = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class"]


def spending_payload(tidy: pd.DataFrame) -> dict:
    """Collapse to department x spending-class level (the account level stays in data/processed)."""
    slim = tidy.groupby(SITE_COLUMNS, as_index=False)["amount"].sum()
    slim["amount"] = slim["amount"].round().astype("int64")
    rows = [[v.item() if hasattr(v, "item") else v for v in row]
            for row in slim[SITE_COLUMNS + ["amount"]].itertuples(index=False, name=None)]
    return {"columns": SITE_COLUMNS + ["amount"], "rows": rows}


def meta_payload(tidy: pd.DataFrame, retrieved: str) -> dict:
    """How old the data is: when the raw actuals were fetched and the latest year each basis covers."""
    return {"retrieved": retrieved,
            "latest_actual_fy": int(tidy.loc[tidy["basis"] == "actual", "fy"].max()),
            "latest_budget_fy": int(tidy.loc[tidy["basis"] == "adopted", "fy"].max())}


def population_payload(pop: pd.DataFrame) -> dict:
    return {"rows": [{"fy": int(r.fy), "population": int(r.population), "source": str(r.source)}
                     for r in pop.itertuples(index=False)]}


def vendors_payload(vendors: pd.DataFrame, cov: dict) -> dict:
    by_key: dict[str, dict] = {}
    for row in vendors.itertuples(index=False):
        entry = by_key.setdefault(row.vendor_key, {"name": row.vendor_name, "ids": set(), "amounts": {}, "latest": 0})
        entry["ids"].update(row.vendor_ids.split("; "))
        entry["amounts"][str(int(row.fy))] = int(round(row.amount))
        if row.fy >= entry["latest"]:
            entry["latest"], entry["name"] = int(row.fy), row.vendor_name
    ranked = sorted(by_key.values(), key=lambda e: (-sum(e["amounts"].values()), e["name"]))
    return {
        "years": sorted(int(y) for y in vendors["fy"].unique()),
        "coverage": {str(fy): {"vendors_total": int(round(c["vendors_total"])),
                               "reference_total": int(round(c["reference_total"])),
                               "reference_basis": c["reference_basis"]} for fy, c in sorted(cov.items())},
        "vendors": [{"name": e["name"], "ids": "; ".join(sorted(e["ids"])), "amounts": e["amounts"]} for e in ranked],
    }
