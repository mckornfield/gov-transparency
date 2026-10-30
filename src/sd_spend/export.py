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


def population_payload(pop: pd.DataFrame) -> dict:
    return {"rows": [{"fy": int(r.fy), "population": int(r.population), "source": str(r.source)}
                     for r in pop.itertuples(index=False)]}
