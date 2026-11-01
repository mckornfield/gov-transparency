"""Census Bureau Annual Survey of State and Local Government Finances, FY2019-FY2024 individual unit files.

Each zip holds Fin_PID_<year>.txt (government names, populations, fiscal year ends) and the item-level amounts
(in thousands of dollars). Public domain. The FY2024 methodology PDF is saved beside them.
Census renamed the zip after 2022, so the upstream name is listed per year; the local name is always
census/<year>_Individual_Unit_Files.zip.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://www2.census.gov/programs-surveys/gov-finances/tables/"
UPSTREAM = {
    2019: "2019_Individual_Unit_File.zip",
    2020: "2020_Individual_Unit_File.zip",
    2021: "2021_Individual_Unit_File.zip",
    2022: "2022_Individual_Unit_File.zip",
    2023: "2023_Individual_Unit_Files.zip",
    2024: "2024_Individual_Unit_Files.zip",
}


def main() -> None:
    for year, name in UPSTREAM.items():
        response = get_with_retry(f"{BASE}{year}/{name}")
        print("fetched", response.url, len(response.content), flush=True)
        save_raw(response.content, f"census/{year}_Individual_Unit_Files.zip", response.url)
    response = get_with_retry(BASE + "2024/2024_methodology.pdf")
    print("fetched", response.url, len(response.content), flush=True)
    save_raw(response.content, "census/2024_methodology.pdf", response.url)


if __name__ == "__main__":
    main()
