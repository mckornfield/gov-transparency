"""Build per-function, per-resident spending for San Diego and its peer cities from the committed Census zip."""
import gzip
import json

from sd_spend.census import build_peer_spending, parse_items, parse_units, read_zip_member
from sd_spend.export import peers_payload
from sd_spend.io import RAW, ROOT

ZIP = RAW / "census" / "2024_Individual_Unit_Files.zip.gz"
OUT = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def main() -> None:
    zip_bytes = gzip.decompress(ZIP.read_bytes())
    units = parse_units(read_zip_member(zip_bytes, "Fin_PID_2024.txt"))
    items = parse_items(read_zip_member(zip_bytes, "modp.txt"))
    peers = json.loads((ROOT / "config" / "peers.json").read_text())
    functions = json.loads((ROOT / "config" / "census_functions.json").read_text())
    tidy = build_peer_spending(units, items, peers, functions)
    OUT.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(OUT / "peer_spending.csv", index=False)
    (SITE_DATA / "peers.json").write_text(json.dumps(peers_payload(tidy), separators=(",", ":")))
    print(tidy.groupby("city")["per_resident"].sum().round(0).sort_values().to_string())


if __name__ == "__main__":
    main()
