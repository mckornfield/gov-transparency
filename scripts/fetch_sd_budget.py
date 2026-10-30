"""City of San Diego operating budget, operating actuals and their reference tables
(data.sandiego.gov; the files are served from seshat.datasd.org).

report_fy is the END year of the fiscal year (23 = FY2023). The budget file holds both
'adopted' and 'proposed' rows for some years; build_processed.py keeps adopted only.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://seshat.datasd.org"
FILES = {
    "sandiego/actuals_operating.csv": "operating_actuals/actuals_operating_datasd.csv",
    "sandiego/actuals_operating_dictionary.csv": "operating_actuals/operating_actuals_dictionary_datasd.csv",
    "sandiego/budget_operating.csv": "operating_budget/budget_operating_datasd.csv",
    "sandiego/budget_operating_dictionary.csv": "operating_budget/operating_budget_dictionary_datasd.csv",
    "sandiego/accounts.csv": "accounts_city_budget/budget_reference_accounts_datasd.csv",
    "sandiego/accounts_dictionary.csv": "accounts_city_budget/budget_reference_accounts_dictionary_datasd.csv",
    "sandiego/depts.csv": "departments_city_budget/budget_reference_depts_datasd.csv",
    "sandiego/depts_dictionary.csv": "departments_city_budget/budget_reference_depts_dictionary_datasd.csv",
}


def main() -> None:
    for rel_path, remote in FILES.items():
        url = f"{BASE}/{remote}"
        print("fetching", url, flush=True)
        save_raw(get_with_retry(url).content, rel_path, url)


if __name__ == "__main__":
    main()
