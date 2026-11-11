"""California age-spending sources: the 2025-26 Governor's Budget (2023-24 actuals), Census state population by age, and
state counts of recipients by age. The CMS age shape and the SSA SSI report come from fetch_age_spending.py.

    uv run python scripts/fetch_ca_age_spending.py
"""
from sd_spend.io import get_with_retry, save_raw

HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}
FILES = {
    "ca/schedule9_2025_26_gb.pdf": "https://ebudget.ca.gov/2025-26/pdf/BudgetSummary/BS_SCH9.pdf",
    "ca/dss_5180_2025_26_gb.pdf": "https://ebudget.ca.gov/2025-26/pdf/GovernorsBudget/4000/5180.pdf",
    "census/sc-est2024-agesex-civ.csv": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/asrh/sc-est2024-agesex-civ.csv",
    "ca/ihss_program_data_jan2024.xlsx": "https://www.cdss.ca.gov/Portals/9/IHSS/Data/IHSS_Program_Data-Jan2024.xlsx",
    "ca/ca237cw_fy2023_24.xlsx": "https://cdss.ca.gov/Portals/9/DSSDB/DataTables/CA237CW%20FY%202023-24.xlsx",
    "ca/dds_pos_statewide_fy2023_24.xlsx": "https://www.dds.ca.gov/wp-content/uploads/2024/12/AnnualPOSReportDeid_Statewide_20241220.xlsx",
    "macpac/exhibit21_fy2023.xlsx": ("https://www.macpac.gov/wp-content/uploads/2026/02/EXHIBIT-21.-Medicaid-Spending-by-State-"
                                     "Eligibility-Group-and-Dually-Eligible-Status-FY-2023-1.xlsx"),
}
MEDI_CAL_PACKAGE = "https://data.ca.gov/api/3/action/package_show?id=medi-cal-certified-eligibles-data-by-month-with-demographics"
DDS_PACKAGE = "https://data.ca.gov/api/3/action/package_show?id=dds-consumers-served-by-age-group-and-gender"


def fetch(url: str, rel: str) -> None:
    response = get_with_retry(url, headers=HEADERS)
    print("fetched", url, len(response.content), flush=True)
    save_raw(response.content, rel, url)


def main() -> None:
    for rel, url in FILES.items():
        fetch(url, rel)
    resources = get_with_retry(DDS_PACKAGE, headers=HEADERS).json()["result"]["resources"]
    dds = next((r["url"] for r in resources if r["format"] == "CSV" and "Dictionary" not in r["name"]), None)
    if dds is None:
        raise SystemExit("the DDS consumers-by-age dataset has no CSV resource")
    fetch(dds, "ca/dds_consumers_by_age_gender.csv")
    resources = get_with_retry(MEDI_CAL_PACKAGE, headers=HEADERS).json()["result"]["resources"]
    eligibles = next((r["url"] for r in resources if r["format"] == "CSV" and r["name"].startswith("By Age Group and Sex")), None)
    if eligibles is None:
        raise SystemExit("the Medi-Cal certified eligibles dataset has no age-and-sex CSV")
    fetch(eligibles, "ca/medi_cal_eligibles_age_sex.csv")


if __name__ == "__main__":
    main()
