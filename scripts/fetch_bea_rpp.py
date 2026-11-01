"""BEA Regional Price Parities by metropolitan area (MARPP), 2008-2024. Public domain.

The zip holds MARPP_MSA_2008_2024.csv: price levels where the US average is 100 (line 1 = all items).
"""
from sd_spend.io import get_with_retry, save_raw

URL = "https://apps.bea.gov/regional/zip/MARPP.zip"


def main() -> None:
    response = get_with_retry(URL)
    print("fetched", response.url, len(response.content), flush=True)
    save_raw(response.content, "bea/MARPP.zip", response.url)


if __name__ == "__main__":
    main()
