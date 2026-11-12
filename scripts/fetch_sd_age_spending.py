"""San Diego local age-spending sources: the County of San Diego's open-budget tables (2024-25 adopted budget by program
and revenue source), its Behavioral Health Services databook (clients by age), and Census county population by age.
The school ledger, city budget and state caseload files come from the other fetch scripts.

    uv run python scripts/fetch_sd_age_spending.py
"""
from sd_spend.io import get_with_retry, save_raw

HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}
FISCAL_YEAR = "2025"
FILES = {
    "census/cc-est2024-syasex-06.csv": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/asrh/cc-est2024-syasex-06.csv",
    "sdcounty/bhs_databook_fy2024_25.pdf": "https://www.sandiegocounty.gov/content/dam/sdc/bhs/TRL/TRL%20Section%206/BHS%20Databook%20FY%2024-25.pdf",
}
# Socrata datasets behind the county's open-budget site: expenditures and revenues by program.
TABLES = {"sdcounty/open_budget_exp_fy2025.csv": "u4wm-r3vc", "sdcounty/open_budget_rev_fy2025.csv": "sucv-y5vk"}


def main() -> None:
    for rel, url in FILES.items():
        response = get_with_retry(url, headers=HEADERS)
        print("fetched", url, len(response.content), flush=True)
        save_raw(response.content, rel, url)
    for rel, dataset in TABLES.items():
        response = get_with_retry(f"https://data.sandiegocounty.gov/resource/{dataset}.csv", headers=HEADERS,
                                  params={"$where": f"fiscal_year={FISCAL_YEAR}", "$order": ":id", "$limit": "200000"})
        if response.content.count(b"\n") < 1000:
            raise SystemExit(f"{dataset} returned too few rows for fiscal year {FISCAL_YEAR}")
        print("fetched", response.url, len(response.content), flush=True)
        save_raw(response.content, rel, response.url)


if __name__ == "__main__":
    main()
