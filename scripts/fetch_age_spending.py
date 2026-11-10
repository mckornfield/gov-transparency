"""Age-spending sources: Treasury outlays, Census population by age, CMS health spending by age, VA by age.

SSA and the White House block automated downloads, so those two are downloaded in a browser and passed in:
    uv run python scripts/fetch_age_spending.py --ssa-file ~/Downloads/age/5a.pdf --omb-file ~/Downloads/age/hist03z2.xlsx
"""
import argparse
from pathlib import Path

from sd_spend.io import get_with_retry, save_raw

FISCAL_YEAR = 2024
MTS = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9"
       f"?filter=record_fiscal_year:eq:{FISCAL_YEAR},record_calendar_month:eq:09&page%5Bsize%5D=300")
CENSUS = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/national/asrh/nc-est2024-agesex-res.csv"
CMS = ("https://www.cms.gov/research-statistics-data-and-systems/statistics-trends-and-reports/"
       "nationalhealthexpenddata/downloads/ageandgendercsvfiles.zip")
VA = {"va_compensation_by_age_fy2024.csv": "https://www.data.va.gov/api/views/ibas-uwj3/rows.csv?accessType=DOWNLOAD",
      "va_pension_by_age_fy2024.csv": "https://www.data.va.gov/api/views/sbtk-kfnm/rows.csv?accessType=DOWNLOAD"}
SSA_PAGE = "https://www.ssa.gov/policy/docs/statcomps/supplement/2025/5a.pdf"
OMB_PAGE = "https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/"
HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}


def fetch(url: str, rel: str) -> None:
    response = get_with_retry(url, headers=HEADERS)
    print("fetched", url, len(response.content), flush=True)
    save_raw(response.content, rel, url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssa-file", type=Path, help="SSA Annual Statistical Supplement 2025 section 5.A PDF")
    parser.add_argument("--omb-file", type=Path, help="OMB historical table 3.2 (outlays by function and subfunction) .xlsx")
    args = parser.parse_args()
    fetch(MTS, f"treasury/mts_table9_fy{FISCAL_YEAR}_sep.json")
    fetch(CENSUS, "census/nc-est2024-agesex-res.csv")
    fetch(CMS, "cms/age_and_sex_csv_files.zip")
    for name, url in VA.items():
        fetch(url, f"va/{name}")
    if args.ssa_file:
        save_raw(args.ssa_file.read_bytes(), "ssa/statcomps_2025_5a.pdf", SSA_PAGE)
        print("stored", args.ssa_file)
    if args.omb_file:
        save_raw(args.omb_file.read_bytes(), "omb/hist03z2.xlsx", OMB_PAGE)
        print("stored", args.omb_file)


if __name__ == "__main__":
    main()
