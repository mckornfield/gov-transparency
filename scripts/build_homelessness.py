"""Build the homelessness page data from the committed raw files: Cal ICH measures, HHAP awards (HCD), the City's
department budget lines and HUD point-in-time counts."""
import gzip
import json
import subprocess

import pandas as pd

from sd_spend.export import homelessness_payload
from sd_spend.homeless import parse_budget, parse_hhap, parse_hud_pit, parse_spm
from sd_spend.io import RAW, ROOT

OUT = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def raw_bytes(rel: str) -> bytes:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes())


def pdf_text(rel: str) -> str:
    done = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw_bytes(rel), capture_output=True, check=True)
    return done.stdout.decode()


def city_lines() -> list[dict]:
    """Actual spending from each volume's actual year, then the latest volume's budget and adopted years."""
    lines = {}
    for fy in range(2023, 2027):
        b = parse_budget(pdf_text(f"sandiego/hssd_budget_fy{fy}.pdf"))
        a = b["actual_year"]
        lines[a] = {"fy": a, "expenditures": b["expenditures"][a], "revenue": b["revenue"][a], "kind": "actual"}
    for fy, kind in ((2025, "budget"), (2026, "adopted")):
        lines[fy] = {"fy": fy, "expenditures": b["expenditures"][fy], "revenue": b["revenue"][fy], "kind": kind}
    return [lines[k] for k in sorted(lines)]


def main() -> None:
    cfg = json.loads((ROOT / "config" / "homelessness.json").read_text())
    spm = parse_spm(raw_bytes("calich/ca_spms.csv").decode("utf-8"))
    hhap = pd.concat([parse_hhap(pdf_text(f"hcd/{key}.pdf"), label) for key, label in cfg["hhap_rounds"].items()],
                     ignore_index=True)
    pit = parse_hud_pit(raw_bytes("hud/2007-2024-PIT-Counts-by-CoC.xlsb"), [r["coc_id"] for r in cfg["regions"]])
    city = city_lines()
    pop = pd.read_csv(OUT / "population.csv")
    payload = homelessness_payload(spm, hhap, city, pit, pop, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    pit.to_csv(OUT / "homeless_pit.csv", index=False)
    spm.to_csv(OUT / "homeless_measures.csv", index=False)
    hhap.to_csv(OUT / "homeless_hhap.csv", index=False)
    pd.DataFrame(city).to_csv(OUT / "homeless_city.csv", index=False)
    (SITE_DATA / "homelessness.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(pd.DataFrame(city).to_string(index=False))


if __name__ == "__main__":
    main()
