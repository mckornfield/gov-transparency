"""Raw San Diego files -> data/processed/*.csv and site/data/*.json.

Fails (ReconciliationError) rather than writing numbers that do not reconcile; do not loosen the
tolerances in sd_spend.spending to make it pass, investigate the data and tell the user.
"""
import csv
import json

import pandas as pd

from sd_spend import export, spending
from sd_spend.io import RAW, ROOT

PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n")


def retrieved_date(raw_path: str) -> str:
    with (RAW / "MANIFEST.csv").open(newline="") as f:
        return next(r["retrieved"] for r in csv.DictReader(f) if r["path"] == raw_path)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    sd = RAW / "sandiego"
    actuals = spending.read_operating(sd / "actuals_operating.csv.gz")
    budget = spending.read_operating(sd / "budget_operating.csv.gz")
    accounts = pd.read_csv(sd / "accounts.csv.gz", dtype=str, keep_default_na=False)
    depts = pd.read_csv(sd / "depts.csv.gz", dtype=str, keep_default_na=False)
    tidy, report = spending.build_spending(actuals, budget, accounts, depts)
    population = spending.build_population(
        pd.read_csv(RAW / "sco" / "san_diego_population.csv.gz", dtype=str))

    tidy.to_csv(PROCESSED / "spending.csv", index=False)
    population.to_csv(PROCESSED / "population.csv", index=False)
    (PROCESSED / "build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_json(SITE_DATA / "spending.json", export.spending_payload(tidy))
    write_json(SITE_DATA / "meta.json",
               export.meta_payload(tidy, retrieved_date("sandiego/actuals_operating.csv.gz")))
    write_json(SITE_DATA / "population.json", export.population_payload(population))

    print(tidy.groupby(["basis", "fy"])["amount"].sum().div(1e6).round(0).unstack("basis"))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
