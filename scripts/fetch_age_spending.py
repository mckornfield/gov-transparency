"""Age-spending sources: Treasury outlays, Census population by age, CMS health spending by age, VA by age.

SSA and the White House block automated downloads, so those two are downloaded in a browser and passed in:
    uv run python scripts/fetch_age_spending.py --ssa-file ~/Downloads/age/oasdi_2025.pdf --omb-file ~/Downloads/age/hist_fy2027.zip
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
NHE = "https://www.cms.gov/files/zip/nhe-tables.zip"
SNAP_REPORT = "https://www.fns.usda.gov/sites/default/files/resource-files/snap-FY23-Characteristics-Report.pdf"
FNS_KEYDATA = "https://www.fns.usda.gov/sites/default/files/data-files/keydata-january-2025.pdf"
IRS = {"irs/22in25ic.xls": "https://www.irs.gov/pub/irs-soi/22in25ic.xls", "irs/22in33ar.xls": "https://www.irs.gov/pub/irs-soi/22in33ar.xls"}
CDC_BIRTHS = "https://www.cdc.gov/nchs/data/nvsr/nvsr75/nvsr75-02.pdf"
SSA_PAGE = "https://www.ssa.gov/policy/docs/statcomps/supplement/2025/5a.pdf"
HUD_PAGE = "https://www.huduser.gov/portal/datasets/assthsg.html"
OMB_PAGE = "https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/"
HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}


def fetch(url: str, rel: str) -> None:
    response = get_with_retry(url, headers=HEADERS)
    print("fetched", url, len(response.content), flush=True)
    save_raw(response.content, rel, url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssa-file", type=Path, help="SSA Annual Statistical Supplement 2025 section 5.A PDF")
    parser.add_argument("--omb-file", type=Path, help="OMB historical tables .zip (table 3.2, outlays by function and subfunction, is inside)")
    parser.add_argument("--hud-housing-file", type=Path, help="HUD Picture of Subsidized Households US_2024_2020census.xlsx (the HUD site only serves browsers)")
    args = parser.parse_args()
    fetch(MTS, f"treasury/mts_table9_fy{FISCAL_YEAR}_sep.json")
    fetch(CENSUS, "census/nc-est2024-agesex-res.csv")
    fetch(CMS, "cms/age_and_sex_csv_files.zip")
    for rel, url in IRS.items():
        fetch(url, rel)
    fetch(CDC_BIRTHS, "cdc/nvsr75_02_births_final_2024.pdf")
    fetch(NHE, "cms/nhe_tables.zip")
    fetch(SNAP_REPORT, "fns/snap_characteristics_fy2023.pdf")
    fetch(FNS_KEYDATA, "fns/keydata_jan2025_fy2024.pdf")
    for name, url in VA.items():
        fetch(url, f"va/{name}")
    if args.ssa_file:
        save_raw(args.ssa_file.read_bytes(), "ssa/statcomps_2025_5a.pdf", SSA_PAGE)
        print("stored", args.ssa_file)
    if args.hud_housing_file:
        save_raw(args.hud_housing_file.read_bytes(), "hud/US_2024_2020census.xlsx", HUD_PAGE)
        print("stored", args.hud_housing_file)
    if args.omb_file:
        save_raw(args.omb_file.read_bytes(), "omb/hist_fy2027.zip", OMB_PAGE)
        print("stored", args.omb_file)


if __name__ == "__main__":
    main()
