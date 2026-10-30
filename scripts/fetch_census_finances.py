"""Census Bureau Annual Survey of State and Local Government Finances, FY2024 individual unit files.

One zip holds Fin_PID_2024.txt (government names, populations, fiscal year ends) and the item-level amounts
(in thousands of dollars). Public domain. The methodology PDF is saved beside it.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://www2.census.gov/programs-surveys/gov-finances/tables/2024/"
FILES = ["2024_Individual_Unit_Files.zip", "2024_methodology.pdf"]


def main() -> None:
    for name in FILES:
        response = get_with_retry(BASE + name)
        print("fetched", response.url, len(response.content), flush=True)
        save_raw(response.content, f"census/{name}", response.url)


if __name__ == "__main__":
    main()
