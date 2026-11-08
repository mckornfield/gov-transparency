"""Homelessness sources: Cal ICH system performance measures (data.ca.gov), HCD HHAP allocation tables,
the City's Homelessness Strategies and Solutions budget volumes, and HUD's point-in-time counts.

HUD blocks automated downloads, so its workbook is downloaded in a browser and passed in:
    uv run python scripts/fetch_homelessness.py --hud-file ~/Downloads/2007-2024-PIT-Counts-by-CoC.xlsb
"""
import argparse
from pathlib import Path

from sd_spend.io import get_with_retry, save_raw

CKAN = "https://data.ca.gov/api/3/action/package_search?q=system+performance+measures+CoC&rows=5"
DATASET = "CA System Performance Measures, Statewide and by CoC"
RESOURCES = {"CA SPMs Prior Years and Last Twelve Months": "calich/ca_spms.csv",
             "CA SPM Data Dictionary": "calich/ca_spms_dictionary.csv"}
HCD = "https://www.hcd.ca.gov/sites/default/files/docs/grants-and-funding/calich/"
HHAP = {"hhap_r1_redir": "https://hcd.ca.gov/sites/default/files/docs/grants-and-funding/calich/hhap_r1_redir_allocations.pdf",
        "hhap_r2": HCD + "hhap_r2_allocations.pdf", "hhap_r3": HCD + "hhap_r3_allocations.pdf",
        "hhap_r4": HCD + "hhap_r4_allocations.pdf", "hhap_r5": HCD + "hhap-5-allocations.pdf"}
SD = "https://www.sandiego.gov/sites/default/files/"
BUDGETS = {2023: SD + "fy23ab_v2hsd.pdf", 2024: SD + "fy24ab_v2hssd.pdf",
           2025: SD + "2024-08/fy25ab_v2hssd.pdf", 2026: SD + "2025-08/fy26ab_v2hssd.pdf"}
# HCD refuses the default python-requests agent; an honest, identifying one is accepted.
HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}
HUD_PAGE = "https://www.huduser.gov/portal/datasets/ahar/2024-ahar-part-1-pit-estimates-of-homelessness-in-the-us.html"


def fetch(url: str, rel: str) -> None:
    response = get_with_retry(url, headers=HEADERS)
    print("fetched", url, len(response.content), flush=True)
    save_raw(response.content, rel, url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hud-file", type=Path, help="HUD 2007-2024 PIT Counts by CoC .xlsb, downloaded in a browser")
    args = parser.parse_args()
    packages = get_with_retry(CKAN, headers=HEADERS).json()["result"]["results"]
    package = next((p for p in packages if p["title"] == DATASET), None)
    if package is None:
        raise SystemExit(f"data.ca.gov has no dataset titled {DATASET!r}")
    for name, rel in RESOURCES.items():
        match = [r["url"] for r in package["resources"] if r["name"] == name and r["format"] == "CSV"]
        if len(match) != 1:
            raise SystemExit(f"expected one resource named {name!r}, found {len(match)}")
        fetch(match[0], rel)
    for name, url in HHAP.items():
        fetch(url, f"hcd/{name}.pdf")
    for fy, url in BUDGETS.items():
        fetch(url, f"sandiego/hssd_budget_fy{fy}.pdf")
    if args.hud_file:
        save_raw(args.hud_file.read_bytes(), "hud/2007-2024-PIT-Counts-by-CoC.xlsb", HUD_PAGE)
        print("stored", args.hud_file)


if __name__ == "__main__":
    main()
