"""City of San Diego estimated population by fiscal year, from the State Controller's Office
city revenues dataset (bythenumbers.sco.ca.gov, Socrata SoQL API; no key needed).

The SCO reports a population in every row of the dataset; we group to one row per year.
Years 2006 and 2010 are absent from the SCO data (the build step interpolates them).
"""
from sd_spend.io import get_with_retry, save_raw

URL = "https://bythenumbers.sco.ca.gov/resource/rrtv-rsj9.csv"
PARAMS = {
    "$select": "entity_name,fiscal_year,estimated_population",
    "$where": "entity_name='San Diego'",
    "$group": "entity_name,fiscal_year,estimated_population",
    "$order": "fiscal_year",
    "$limit": "100",
}


def main() -> None:
    response = get_with_retry(URL, params=PARAMS)
    print("fetched", response.url, flush=True)
    save_raw(response.content, "sco/san_diego_population.csv", response.url)


if __name__ == "__main__":
    main()
