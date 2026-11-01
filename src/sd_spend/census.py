"""Census Annual Survey of State and Local Government Finances: individual unit files for chosen cities.

Layouts (2024 Public Use Files Technical Documentation):
  Fin_PID: id 1-12, name 13-76, population 117-125, fiscal-year end (MMDD) 141-144.
  FinEstDAT: id 1-12, item code 13-15, amount in THOUSANDS of dollars 16-27.
Expenditure item codes start with E, F, G, I, J, L, M or S; everything else (revenue, debt balances) is ignored.
"""
import io
import zipfile

import pandas as pd

EXPENDITURE_PREFIXES = "EFGIJLMS"
PER_RESIDENT_RANGE = (500, 8000)


class CensusError(Exception):
    pass


def read_zip_member(zip_bytes: bytes, suffix: str) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            if name.endswith(suffix):
                return z.read(name).decode("latin-1")
    raise CensusError(f"{suffix} not found in zip")


def read_survey(zip_bytes: bytes, year: int) -> tuple[str, str]:
    """(unit-file text, item-file text) from one year's zip. Census renamed the files over the years
    (..._modp.txt, ..._modp_pu.txt), so find them by their stable parts."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        def member(part: str) -> str:
            for name in z.namelist():
                if part in name.rsplit("/", 1)[-1]:
                    return z.read(name).decode("latin-1")
            raise CensusError(f"{part} not found in the {year} zip")
        return member(f"Fin_PID_{year}"), member("FinEstDAT")


def parse_units(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if len(line) < 144 or not line[116:125].strip():
            continue  # short lines and rows with no population (e.g. state totals)
        rows.append({"unit_id": line[0:12], "name": line[12:76].strip(),
                     "population": int(line[116:125]), "fy_end": line[140:144]})
    return pd.DataFrame(rows, columns=["unit_id", "name", "population", "fy_end"])


def parse_items(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if len(line) < 27:
            continue
        rows.append({"unit_id": line[0:12], "item": line[12:15], "amount_usd": int(line[15:27]) * 1000})
    return pd.DataFrame(rows, columns=["unit_id", "item", "amount_usd"])


def check_peers(tidy: pd.DataFrame) -> None:
    low, high = PER_RESIDENT_RANGE
    # Schools, health and welfare are excluded: a city that runs them (Boston) legitimately spends far more.
    totals = tidy[tidy["kind"] != "outside"].groupby("city").agg(amount=("amount_usd", "sum"), population=("population", "first"))
    for city, row in totals.iterrows():
        per = row.amount / row.population
        if not low <= per <= high:
            raise CensusError(f"{city}: total ${per:,.0f} per resident is outside ${low}-${high}")


def build_peer_spending(units: pd.DataFrame, items: pd.DataFrame, peers_cfg: dict, functions_cfg: dict) -> pd.DataFrame:
    wanted = {peers_cfg["home"]: {"city": "San Diego", "state": "CA", "region": "West", "is_home": True}}
    for p in peers_cfg["peers"]:
        wanted[p["id"]] = {"city": p["name"], "state": p["state"], "region": p["region"], "is_home": False}
    present = units[units["unit_id"].isin(wanted)]
    for uid in wanted:
        n = (present["unit_id"] == uid).sum()
        if n != 1:
            raise CensusError(f"city {uid} found {n} times in the unit file (expected 1)")

    code_to_group = {c: g["key"] for g in functions_cfg["groups"] for c in g["codes"]}
    # Older (FY2019-21) files break intergovernmental transfers (L, M, S) out by function, and list "other capital
    # outlay" (G: equipment and land) apart from construction (F). FY2022+ files fold G into F. So transfers roll up
    # by prefix and each G code is counted with its F twin (G62 with F62) to keep the years comparable.
    prefix_groups = functions_cfg.get("prefix_groups", {})
    twins = functions_cfg.get("code_twins", {})
    spend = items[items["unit_id"].isin(wanted) & items["item"].str[0].isin(list(EXPENDITURE_PREFIXES))]
    spend = spend.assign(group=[code_to_group.get(twins.get(c[0], c[0]) + c[1:]) or prefix_groups.get(c[0]) for c in spend["item"]])
    unmapped = sorted(set(spend.loc[spend["group"].isna(), "item"]))
    if unmapped:
        raise CensusError(f"expenditure item codes not mapped in census_functions.json: {', '.join(unmapped)}")

    by_group = (spend.groupby(["unit_id", "group"], as_index=False)["amount_usd"].sum())
    rows = []
    for uid, meta in wanted.items():
        u = present[present["unit_id"] == uid].iloc[0]
        for g in functions_cfg["groups"]:
            hit = by_group[(by_group["unit_id"] == uid) & (by_group["group"] == g["key"])]
            amount = int(hit["amount_usd"].iloc[0]) if len(hit) else 0
            rows.append({"unit_id": uid, **meta, "population": int(u["population"]), "fy_end": u["fy_end"],
                         "group": g["key"], "label": g["label"], "kind": g["kind"], "amount_usd": amount,
                         "per_resident": amount / int(u["population"])})
    tidy = pd.DataFrame(rows)
    check_peers(tidy)
    return tidy
