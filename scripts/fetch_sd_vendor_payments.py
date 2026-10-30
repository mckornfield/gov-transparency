"""City of San Diego 'Cumulative Amounts Paid to Vendors - $25,000 or more', one PDF per fiscal year
(sandiego.gov; the City publishes no CSV of these).

FY2026 is the report covering July 2025 to June 2026. A separate file in the same series
(2025-10/cumulative-paid-fy26.pdf) covers only July-September 2025 and is deliberately not used.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://www.sandiego.gov/sites/default/files"
REPORTS = {
    2022: "2024-10/fy2022-cumulative-amounts-paid-1.pdf",
    2023: "2024-10/fy2023-cumulative-amounts-paid-2.pdf",
    2024: "2024-10/fy2024-cumulative-amounts-paid.pdf",
    2025: "2025-07/cumulative-paid-fy25.pdf",
    2026: "2026-04/cumulative-paid-fy26.pdf",
}


def main() -> None:
    for fy, path in REPORTS.items():
        url = f"{BASE}/{path}"
        print("fetching", url, flush=True)
        save_raw(get_with_retry(url).content, f"sandiego/vendor_payments_fy{fy}.pdf", url)


if __name__ == "__main__":
    main()
