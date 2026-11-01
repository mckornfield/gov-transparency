"""Build per-function, per-resident spending (FY2019-FY2024) for San Diego and its peer cities from the committed Census zips,
with each city's BEA price level for the same fiscal year."""
import gzip
import json

import pandas as pd

from sd_spend.census import build_peer_spending, parse_items, parse_units, read_survey
from sd_spend.export import peers_payload
from sd_spend.io import RAW, ROOT
from sd_spend.prices import add_price_levels, parse_rpp

YEARS = range(2019, 2025)
OUT = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def main() -> None:
    peers = json.loads((ROOT / "config" / "peers.json").read_text())
    functions = json.loads((ROOT / "config" / "census_functions.json").read_text())
    rpp = parse_rpp(gzip.decompress((RAW / "bea" / "MARPP.zip.gz").read_bytes()))
    frames = []
    for year in YEARS:
        units_text, items_text = read_survey(gzip.decompress((RAW / "census" / f"{year}_Individual_Unit_Files.zip.gz").read_bytes()), year)
        tidy = build_peer_spending(parse_units(units_text), parse_items(items_text), peers, functions)
        tidy = add_price_levels(tidy, peers, rpp, year)
        frames.append(tidy.assign(fiscal_year=year))
    tidy = pd.concat(frames, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(OUT / "peer_spending.csv", index=False)
    (SITE_DATA / "peers.json").write_text(json.dumps(peers_payload(tidy), separators=(",", ":")))
    totals = tidy[tidy["kind"] == "core"].groupby(["fiscal_year", "city"])["per_resident"].sum().unstack(0).round(0)
    print(totals.to_string())


if __name__ == "__main__":
    main()
