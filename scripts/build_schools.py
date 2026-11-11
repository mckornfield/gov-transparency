"""Build where school money goes for San Diego County school districts (2023-24) from the stored state ledger extracts.

Writes data/processed/schools_spending.csv and site/data/schools.json.
"""
import csv
import gzip
import json

from sd_spend.io import RAW, ROOT
from sd_spend.schools import CATEGORY_ORDER, PURPOSES, REVENUES, parse_districts, parse_ledger, parse_titles, summarize

YEAR_LABEL = "2023-24"


def raw(rel: str) -> str:
    return gzip.decompress((RAW / (rel + ".gz")).read_bytes()).decode()


def build() -> dict:
    listed = parse_districts(raw("cde/sacs2324_san_diego_districts.csv"))
    summary = summarize(parse_ledger(raw("cde/sacs2324_san_diego_ledger.csv")), parse_titles(raw("cde/sacs2324_funds.csv")))
    unknown = [code for code in summary if code not in listed]
    if unknown:
        raise SystemExit(f"ledger has districts that are not in the district list: {unknown}")
    districts = []
    for code, info in sorted(listed.items(), key=lambda kv: kv[1]["name"]):
        s = summary.get(code)
        if s is None or sum(s["spending"].values()) <= 0:
            continue  # listed by the state but filed no general-fund spending
        if abs(sum(s["spending"].values()) - sum(s["purpose"].values())) > 1:
            raise SystemExit(f"{info['name']}: categories and purposes do not add up to the same total")
        districts.append({"code": code, **info, **{k: {name: round(v, 2) for name, v in s[k].items()} for k in ("spending", "purpose", "revenue", "other_funds")}})
    total = sum(sum(d["spending"].values()) for d in districts)
    groups = dict((label, group) for group, label in CATEGORY_ORDER)
    payroll = sum(v for d in districts for label, v in d["spending"].items() if groups[label] != "Everything else")
    if len(districts) < 40:
        raise SystemExit(f"only {len(districts)} districts have general-fund spending")
    if not 6e9 < total < 10e9:
        raise SystemExit(f"county general-fund spending of {total:,.0f} is outside the plausible range")
    if not 0.70 < payroll / total < 0.92:
        raise SystemExit(f"salaries and benefits are {payroll / total:.0%} of general-fund spending, outside the plausible range")
    return {"year_label": YEAR_LABEL, "county": "San Diego County",
            "categories": [{"label": label, "group": group} for group, label in CATEGORY_ORDER],
            "purposes": [label for label, _, _ in PURPOSES], "revenues": [label for label, _, _ in REVENUES],
            "districts": districts}


def main() -> None:
    data = build()
    (ROOT / "site" / "data" / "schools.json").write_text(json.dumps(data, indent=1) + "\n")
    with (ROOT / "data" / "processed" / "schools_spending.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fiscal_year", "district_code", "district", "students_ada", "group", "category", "dollars"])
        for d in data["districts"]:
            for c in data["categories"]:
                writer.writerow([YEAR_LABEL, d["code"], d["name"], d["ada"], c["group"], c["label"], round(d["spending"].get(c["label"], 0))])
    total = sum(sum(d["spending"].values()) for d in data["districts"])
    print(f"{len(data['districts'])} districts, general-fund spending {total / 1e9:.2f}B, students {sum(d['ada'] for d in data['districts']):,.0f}")
    for c in data["categories"]:
        v = sum(d["spending"].get(c["label"], 0) for d in data["districts"])
        print(c["group"].ljust(16), c["label"].ljust(72), f"{v / 1e6:8,.0f}M {v / total:6.1%}")
    for key in ("purposes", "revenues"):
        field = "purpose" if key == "purposes" else "revenue"
        for label in data[key]:
            print(field.ljust(8), label.ljust(62), f"{sum(d[field].get(label, 0) for d in data['districts']) / 1e6:8,.0f}M")


if __name__ == "__main__":
    main()
