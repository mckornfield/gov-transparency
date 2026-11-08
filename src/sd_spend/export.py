"""Shape the tidy tables into the compact JSON the static site loads."""
import pandas as pd

SITE_COLUMNS = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class"]


def spending_payload(tidy: pd.DataFrame) -> dict:
    """Collapse to department x spending-class level (the account level stays in data/processed)."""
    slim = tidy.groupby(SITE_COLUMNS, as_index=False)["amount"].sum()
    slim["amount"] = slim["amount"].round().astype("int64")
    rows = [[v.item() if hasattr(v, "item") else v for v in row]
            for row in slim[SITE_COLUMNS + ["amount"]].itertuples(index=False, name=None)]
    return {"columns": SITE_COLUMNS + ["amount"], "rows": rows}


def meta_payload(tidy: pd.DataFrame, retrieved: str) -> dict:
    """How old the data is: when the raw actuals were fetched and the latest year each basis covers."""
    return {"retrieved": retrieved,
            "latest_actual_fy": int(tidy.loc[tidy["basis"] == "actual", "fy"].max()),
            "latest_budget_fy": int(tidy.loc[tidy["basis"] == "adopted", "fy"].max())}


def population_payload(pop: pd.DataFrame) -> dict:
    return {"rows": [{"fy": int(r.fy), "population": int(r.population), "source": str(r.source)}
                     for r in pop.itertuples(index=False)]}


def vendors_payload(vendors: pd.DataFrame, cov: dict) -> dict:
    by_key: dict[str, dict] = {}
    for row in vendors.itertuples(index=False):
        entry = by_key.setdefault(row.vendor_key, {"name": row.vendor_name, "ids": set(), "amounts": {}, "latest": 0})
        entry["ids"].update(row.vendor_ids.split("; "))
        entry["amounts"][str(int(row.fy))] = int(round(row.amount))
        if row.fy >= entry["latest"]:
            entry["latest"], entry["name"] = int(row.fy), row.vendor_name
    ranked = sorted(by_key.values(), key=lambda e: (-sum(e["amounts"].values()), e["name"]))
    return {
        "years": sorted(int(y) for y in vendors["fy"].unique()),
        "coverage": {str(fy): {"vendors_total": int(round(c["vendors_total"])),
                               "reference_total": int(round(c["reference_total"])),
                               "reference_basis": c["reference_basis"]} for fy, c in sorted(cov.items())},
        "vendors": [{"name": e["name"], "ids": "; ".join(sorted(e["ids"])), "amounts": e["amounts"]} for e in ranked],
    }


def peers_payload(tidy: pd.DataFrame) -> dict:
    """One snapshot per Census survey year (oldest first); `rpp` is the BEA price level (US = 100)."""
    groups = tidy[["group", "label", "kind"]].drop_duplicates().rename(columns={"group": "key"})
    home = tidy.loc[tidy["is_home"], "city"].iloc[0]
    years = []
    for fiscal_year, year in sorted(tidy.groupby("fiscal_year"), key=lambda kv: kv[0]):
        cities = year[["city", "state", "region", "population", "fy_end", "is_home", "reference", "rpp"]].drop_duplicates("city")
        rows = year[["city", "group", "amount_usd", "per_resident"]].rename(columns={"amount_usd": "amount"})
        years.append({
            "fiscal_year": int(fiscal_year),
            "cities": [{**c, "population": int(c["population"]), "is_home": bool(c["is_home"]), "reference": bool(c["reference"]), "rpp": round(float(c["rpp"]), 2)}
                       for c in cities.to_dict("records")],
            "rows": [{**r, "amount": int(r["amount"]), "per_resident": round(float(r["per_resident"]), 2)}
                     for r in rows.to_dict("records")],
        })
    return {"home": home, "groups": groups.to_dict("records"), "years": years}


def _num(x):
    return None if pd.isna(x) else round(float(x))


def homelessness_payload(spm: pd.DataFrame, hhap: pd.DataFrame, city: list[dict], pit: pd.DataFrame,
                         pop: pd.DataFrame, cfg: dict) -> dict:
    """One JSON for the homelessness page. Missing values are null (never 0); city and state dollars stay in
    separate lists because the city's grant revenue includes state money."""
    regions = cfg["regions"]
    ids = {r["coc_id"] for r in regions}
    measures = spm[spm.coc_id.isin(ids) | (spm.location == "California")]
    hhap_rows = []
    for rnd in hhap["round"].drop_duplicates():
        one = hhap[hhap["round"] == rnd]
        for r in regions:
            if "hhap" not in r:
                continue
            row = {"round": rnd, "coc_id": r["coc_id"]}
            for kind in ("coc", "city", "county"):
                match = one[(one.kind == kind) & (one.name == r["hhap"][kind])]
                if len(match) != 1:
                    raise ValueError(f"{rnd}: expected one {kind} row named {r['hhap'][kind]!r}, found {len(match)}")
                row[kind] = _num(match.amount.iloc[0])
            hhap_rows.append(row)
    return {
        "home": cfg["home"],
        "regions": [{"coc_id": r["coc_id"], "name": r["name"], "role": r["role"]} for r in regions],
        "pit": [{"coc_id": r.coc_id, "year": int(r.year), "total": _num(r.total), "sheltered": _num(r.sheltered),
                 "unsheltered": _num(r.unsheltered), "carried": bool(r.carried)} for r in pit.itertuples()],
        "measures": [{"coc_id": r.coc_id if isinstance(r.coc_id, str) else "CA", "metric": r.metric, "period": r.period,
                      "value": None if pd.isna(r.value) else round(float(r.value), 4)} for r in measures.itertuples()],
        "hhap": hhap_rows,
        "city": [{"fy": c["fy"], "expenditures": _num(c["expenditures"]), "revenue": _num(c["revenue"]),
                  "kind": c["kind"]} for c in city],
        "population": [{"fy": int(r.fy), "population": int(r.population)} for r in pop.itertuples()],
    }
