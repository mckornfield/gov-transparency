"""The City's accounts-payable payments (PRA 26-11538) -> data/processed/vendor_payments*.csv and site/data/vendors.json.

Vendors are named only in a fiscal year they were paid $25,000 or more, as in the City's own published lists; smaller
payees are counted in every total but not named. Fails rather than writing numbers that do not look right.
"""
import gzip
import json

import pandas as pd

from sd_spend import vendors
from sd_spend.io import RAW, ROOT
from sd_spend.payments import FUNDS, NAMED_MINIMUM, fund_class, parse_payments

PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"
FULL_YEARS = range(2022, 2027)
PARTIAL = {2027: "July to September 2026"}


def check(rows: pd.DataFrame) -> None:
    if len(rows) < 800_000:
        raise SystemExit(f"only {len(rows):,} payment lines")
    if sorted(rows["fy"].unique()) != [*FULL_YEARS, *PARTIAL]:
        raise SystemExit(f"unexpected fiscal years {sorted(rows['fy'].unique())}")
    totals = rows.groupby("fy")["amount"].sum()
    bad = {fy: round(totals[fy] / 1e9, 2) for fy in FULL_YEARS if not 1.5e9 < totals[fy] < 4.5e9}
    if bad:
        raise SystemExit(f"yearly payment totals look wrong (billions): {bad}")
    if rows["date"].max().isoformat() != "2026-09-30":
        raise SystemExit("the payments file should run to 30 September 2026")


def main() -> None:
    rows = parse_payments(gzip.decompress((RAW / "sandiego" / "pra_26_11538_ap_detail.tsv.gz").read_bytes()).decode())
    check(rows)
    rows["fund_class"] = [fund_class(c, n) for c, n in zip(rows["fund_code"], rows["fund"])]

    # One company under several ids or spellings is one vendor (the same rules as the City's PDF lists used).
    per_id = rows.groupby(["fy", "vendor_id"], as_index=False).agg(vendor_name=("vendor_name", "last"), amount=("amount", "sum"))
    table = vendors.combine({int(fy): df.drop(columns="fy") for fy, df in per_id.groupby("fy")})
    key_of = {(int(r.fy), i): r.vendor_key for r in table.itertuples() for i in r.vendor_ids.split("; ")}
    rows["vendor_key"] = [key_of[(fy, i)] for fy, i in zip(rows["fy"], rows["vendor_id"])]
    table["named"] = (table["amount"] >= NAMED_MINIMUM) & (table["vendor_name"] != "")
    named = set(zip(table.loc[table["named"], "fy"], table.loc[table["named"], "vendor_key"]))
    rows["named"] = [(fy, k) in named for fy, k in zip(rows["fy"], rows["vendor_key"])]

    spending = pd.read_csv(PROCESSED / "spending.csv")
    cov = vendors.coverage(table[table["fy"].isin(FULL_YEARS)].groupby("fy")["amount"].sum(), spending)
    vendors.check_coverage(cov)

    departments = sorted(rows["dept"].unique())
    types = rows.groupby("type")["amount"].sum().sort_values(ascending=False).index.tolist()
    d_index = {d: i for i, d in enumerate(departments)}
    t_index = {t: i for i, t in enumerate(types)}
    years = [*FULL_YEARS, *PARTIAL]

    def summary(part: pd.DataFrame) -> dict:
        small = part[~part["named"]]
        return {"total": round(part["amount"].sum()),
                "unnamed": {"count": int(small["vendor_key"].nunique()), "amount": round(small["amount"].sum())},
                "types": {t: round(v) for t, v in part.groupby("type")["amount"].sum().items() if round(v)},
                "funds": {f: round(v) for f, v in part.groupby("fund_class")["amount"].sum().items() if round(v)}}

    totals = {str(fy): {"all": summary(part), "departments": {d: summary(p) for d, p in part.groupby("dept")}}
              for fy, part in rows.groupby("fy")}

    months = sorted(rows["date"].map(lambda d: d.isoformat()[:7]).unique())
    rows["month"] = rows["date"].map(lambda d: d.isoformat()[:7])
    by_month = rows.groupby(["dept", "month"])["amount"].sum()
    monthly = {"months": months, "all": [round(v) for v in rows.groupby("month")["amount"].sum().reindex(months, fill_value=0)],
               "departments": {d: [round(v) for v in by_month[d].reindex(months, fill_value=0)] for d in departments}}

    named_rows = rows[rows["named"]]
    by_dept = named_rows.groupby(["vendor_key", "fy", "dept"])["amount"].sum()
    by_type = named_rows.groupby(["vendor_key", "fy", "type"])["amount"].sum()
    entries: dict[str, dict] = {}
    for r in table[table["named"]].sort_values("fy").itertuples():
        e = entries.setdefault(r.vendor_key, {"name": r.vendor_name, "ids": set(), "amounts": {}, "by_dept": {}, "by_type": {}})
        e["name"] = r.vendor_name
        e["ids"].update(r.vendor_ids.split("; "))
        fy = str(r.fy)
        e["amounts"][fy] = round(r.amount)
        e["by_dept"][fy] = sorted(([d_index[d], round(v)] for d, v in by_dept[(r.vendor_key, r.fy)].items()), key=lambda x: -x[1])
        e["by_type"][fy] = sorted(([t_index[t], round(v)] for t, v in by_type[(r.vendor_key, r.fy)].items()), key=lambda x: -x[1])
    ranked = sorted(entries.values(), key=lambda e: (-sum(e["amounts"].values()), e["name"]))

    payload = {
        "years": years, "full_years": list(FULL_YEARS), "partial": {str(k): v for k, v in PARTIAL.items()},
        "named_minimum": NAMED_MINIMUM, "departments": departments, "types": types, "funds": FUNDS,
        "coverage": {str(fy): {"vendors_total": round(c["vendors_total"]), "reference_total": round(c["reference_total"]),
                               "reference_basis": c["reference_basis"]} for fy, c in sorted(cov.items())},
        "totals": totals, "monthly": monthly,
        "vendors": [{**{k: v for k, v in e.items() if k != "ids"}, "ids": "; ".join(sorted(e["ids"]))} for e in ranked],
    }
    for fy in years:  # every named vendor's departments add up to its year total, and named + unnamed to the year
        named_sum = sum(e["amounts"].get(str(fy), 0) for e in payload["vendors"])
        if abs(named_sum + totals[str(fy)]["all"]["unnamed"]["amount"] - totals[str(fy)]["all"]["total"]) > len(payload["vendors"]):
            raise SystemExit(f"FY{fy}: named and unnamed payments do not add up to the year")

    table[table["named"]].drop(columns="named").to_csv(PROCESSED / "vendor_payments.csv", index=False)
    (named_rows.groupby(["fy", "vendor_key", "dept", "type", "fund_class"], as_index=False)["amount"].sum()
     .round({"amount": 2}).to_csv(PROCESSED / "vendor_payments_by_department.csv", index=False))
    (SITE_DATA / "vendors.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    for fy in years:
        a = totals[str(fy)]["all"]
        print(f"FY{fy}: ${a['total'] / 1e6:,.1f}M; {sum(1 for e in ranked if str(fy) in e['amounts']):,} vendors named; "
              f"{a['unnamed']['count']:,} smaller payees ${a['unnamed']['amount'] / 1e6:,.1f}M")
    print(f"vendors.json {len(json.dumps(payload, separators=(',', ':'))) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
