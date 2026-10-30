# Peer Cities Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen: native) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "San Diego vs peers" page showing per-resident spending by function for San Diego and 11 comparable US cities, from the Census Bureau's FY2024 Annual Survey of State and Local Government Finances.

**Architecture:** One fetch script saves the Census "Individual Unit Files" zip (gz + MANIFEST row). `src/sd_spend/census.py` parses the two fixed-width files inside, keeps the 12 configured cities, maps item codes to functions via a committed config, validates, and writes a tidy CSV plus `site/data/peers.json`. A new static page draws a dot plot per function with a table for each chart.

**Tech Stack:** Python/pandas (existing), fixed-width parsing, Observable Plot 0.6.16 (existing), `node --test`, Playwright smoke tests.

**Spec:** `docs/superpowers/specs/2026-10-29-gov-transparency-design.md` ("Peer gap methodology", "Pages" #4). Rulings versus the spec, made with the user on 2026-10-30: consolidated city-counties (Indianapolis etc.) are excluded because they carry county services; three smaller Northeast/Pacific Northwest cities (Boston, Seattle, Portland, 0.64-0.75M people) are added for regional spread; the BEA cost-of-living toggle is deferred to a later plan.

## Global Constraints

- Python >=3.11, uv, pandas; no new Python dependencies.
- Raw originals committed under `data/raw/census/` via `save_raw`; every fetched file has a MANIFEST row.
- No bundler. Observable Plot 0.6.16 and d3 7.9.0 from jsDelivr only.
- Peer-gap numbers are never blended with margin and never described as "waste". Wording: "spends more/less per resident than the middle peer".
- Every chart has a keyboard-reachable table, a Method drawer, light/dark CSS variables, and works at phone width.
- Build fails (raises) on: a configured city missing from the data, a duplicated city, any expenditure item code not mapped in the config, or a total per resident outside $500-$8,000.
- Census amounts are in THOUSANDS of dollars; the processed table stores whole dollars.

## Review Focus

- A peer's fiscal year ends in a different month (Dec 2024 vs Jun 2024): shown on the page, never adjusted.
- A function where a city reports $0 (a service run by a county or special district): shown as "$0 / not provided by the city", never ranked as the cheapest.
- Cities with dependent school systems (Boston) or utilities others lack: separate "kinds" off by default, so the default view compares like with like.
- San Diego ranking: rank is among all 12 cities for that function; ties and zeros must not crash the median.
- Item codes the Census adds or renames next year: unmapped code must fail the build, not vanish.

---

### Task 1: Config files and Census fetch script

**Files:**
- Create: `config/peers.json`, `config/census_functions.json`
- Create: `scripts/fetch_census_finances.py`
- Create: `tests/test_census_config.py`
- Modify: `tests/test_manifest.py` (add the Census zip to the required list)

**Interfaces:**
- Produces: `config/peers.json` = `{"home": "062073207598", "peers": [{"id", "name", "state", "region"}...]}`; `config/census_functions.json` = `{"groups": [{"key", "label", "kind", "codes": [...]}]}` with kinds `core`, `utility`, `outside`, `debt`, `other`; raw file `data/raw/census/2024_Individual_Unit_Files.zip.gz`.

- [ ] **Step 1: Write the failing test** `tests/test_census_config.py`

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "config" / name).read_text())


def test_peers_config_shape():
    cfg = load("peers.json")
    ids = [cfg["home"]] + [p["id"] for p in cfg["peers"]]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert all(len(i) == 12 for i in ids)
    assert {p["region"] for p in cfg["peers"]} >= {"West", "South", "Northeast", "Pacific Northwest"}


def test_function_codes_unique_and_kinds_known():
    groups = load("census_functions.json")["groups"]
    codes = [c for g in groups for c in g["codes"]]
    assert len(codes) == len(set(codes)), "an item code is mapped to two groups"
    assert {g["kind"] for g in groups} <= {"core", "utility", "outside", "debt", "other"}
    assert all(c[0] in "EFGIJLMS" for c in codes)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_census_config.py -v` — Expected: FAIL (FileNotFoundError config/peers.json).

- [ ] **Step 3: Create `config/peers.json`**

```json
{
  "home": "062073207598",
  "peers": [
    {"id": "042013207536", "name": "Phoenix", "state": "AZ", "region": "West"},
    {"id": "062085100745", "name": "San Jose", "state": "CA", "region": "West"},
    {"id": "482029175988", "name": "San Antonio", "state": "TX", "region": "South"},
    {"id": "482113187649", "name": "Dallas", "state": "TX", "region": "South"},
    {"id": "482453176394", "name": "Austin", "state": "TX", "region": "South"},
    {"id": "482439176375", "name": "Fort Worth", "state": "TX", "region": "South"},
    {"id": "372119194726", "name": "Charlotte", "state": "NC", "region": "South"},
    {"id": "392049209050", "name": "Columbus", "state": "OH", "region": "Midwest"},
    {"id": "532033184255", "name": "Seattle", "state": "WA", "region": "Pacific Northwest"},
    {"id": "412051211254", "name": "Portland", "state": "OR", "region": "Pacific Northwest"},
    {"id": "252025128108", "name": "Boston", "state": "MA", "region": "Northeast"}
  ]
}
```

- [ ] **Step 4: Create `config/census_functions.json`** (current-operation `E`, construction `F`; every code present for these 12 cities in FY2024 is mapped)

```json
{
  "groups": [
    {"key": "police", "label": "Police", "kind": "core", "codes": ["E62", "F62"]},
    {"key": "fire", "label": "Fire", "kind": "core", "codes": ["E24", "F24"]},
    {"key": "parks", "label": "Parks & recreation", "kind": "core", "codes": ["E61", "F61"]},
    {"key": "libraries", "label": "Libraries", "kind": "core", "codes": ["E52", "F52"]},
    {"key": "roads", "label": "Roads & highways", "kind": "core", "codes": ["E44", "F44"]},
    {"key": "sanitation", "label": "Sewer & trash", "kind": "core", "codes": ["E80", "F80", "E81", "F81"]},
    {"key": "housing", "label": "Housing & community development", "kind": "core", "codes": ["E50", "F50"]},
    {"key": "admin", "label": "Administration, courts & inspection", "kind": "core",
     "codes": ["E23", "F23", "E29", "F29", "E31", "F31", "E89", "F89", "E25", "F25", "E66", "F66", "E59", "F59"]},
    {"key": "water", "label": "Water utility", "kind": "utility", "codes": ["E91", "F91"]},
    {"key": "power", "label": "Electric & gas utilities", "kind": "utility", "codes": ["E92", "F92", "E93", "F93"]},
    {"key": "transit", "label": "Transit", "kind": "utility", "codes": ["E94", "F94"]},
    {"key": "enterprise", "label": "Airports, parking & other commercial", "kind": "utility",
     "codes": ["E01", "F01", "E60", "F60", "E03", "F03"]},
    {"key": "county", "label": "Health, welfare, jails & schools", "kind": "outside",
     "codes": ["E32", "F32", "E36", "F36", "E79", "F79", "E04", "F04", "E12", "F12"]},
    {"key": "debt", "label": "Interest on debt", "kind": "debt", "codes": ["I89", "I91", "I92", "I93", "I94"]},
    {"key": "transfers", "label": "Grants & payments to other governments", "kind": "other", "codes": ["J19", "L89", "M89"]}
  ]
}
```

- [ ] **Step 5: Run** `uv run pytest tests/test_census_config.py -v` — Expected: 2 PASS.

- [ ] **Step 6: Create `scripts/fetch_census_finances.py`**

```python
"""Census Bureau Annual Survey of State and Local Government Finances, FY2024 individual unit files.

One zip holds Fin_PID_2024.txt (government names, populations, fiscal year ends) and the item-level amounts
(in thousands of dollars). Public domain. The methodology PDF is saved beside it.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://www2.census.gov/programs-surveys/gov-finances/tables/2024/"
FILES = ["2024_Individual_Unit_Files.zip", "2024_methodology.pdf"]


def main() -> None:
    for name in FILES:
        response = get_with_retry(BASE + name)
        print("fetched", response.url, len(response.content), flush=True)
        save_raw(response.content, f"census/{name}", response.url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run it and commit the raw data** — `uv run python scripts/fetch_census_finances.py && ls -la data/raw/census` — Expected: two `.gz` files, zip about 4 MB; `grep census data/raw/MANIFEST.csv` shows 2 rows.

- [ ] **Step 8: Extend `tests/test_manifest.py`** — add `census/2024_Individual_Unit_Files.zip.gz` and `census/2024_methodology.pdf.gz` to its list of required raw paths (follow how the five vendor PDFs are listed). Run `uv run pytest tests/test_manifest.py -v` — Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add config scripts/fetch_census_finances.py data/raw tests/test_census_config.py tests/test_manifest.py
git commit -m "Fetch Census FY2024 city finances; add peer and function config"
```

---

### Task 2: Parse, map and validate (`census.py`)

**Files:**
- Create: `src/sd_spend/census.py`
- Create: `tests/test_census.py`

**Interfaces:**
- Consumes: the two config files from Task 1.
- Produces:
  - `class CensusError(Exception)`
  - `parse_units(text: str) -> pd.DataFrame` columns `unit_id, name, population, fy_end` (population int, fy_end str like `"0630"`)
  - `parse_items(text: str) -> pd.DataFrame` columns `unit_id, item, amount_usd` (int dollars; thousands x 1000)
  - `build_peer_spending(units, items, peers_cfg, functions_cfg) -> pd.DataFrame` tidy columns `unit_id, city, state, region, is_home, population, fy_end, group, label, kind, amount_usd, per_resident`
  - `check_peers(tidy)` raises `CensusError` on the rules in Global Constraints (called inside `build_peer_spending`).
  - `read_zip_member(zip_bytes: bytes, suffix: str) -> str`

- [ ] **Step 1: Write failing tests** `tests/test_census.py`

```python
import io
import zipfile

import pandas as pd
import pytest

from sd_spend.census import (CensusError, build_peer_spending, parse_items, parse_units, read_zip_member)

HOME, PEER = "062073207598", "482113187649"
PEERS = {"home": HOME, "peers": [{"id": PEER, "name": "Dallas", "state": "TX", "region": "South"}]}
FUNCS = {"groups": [
    {"key": "police", "label": "Police", "kind": "core", "codes": ["E62", "F62"]},
    {"key": "water", "label": "Water utility", "kind": "utility", "codes": ["E91"]},
]}


def unit_line(uid, name, pop, fy="0630"):
    return f"{uid}{name:<64}{'County':<35}{'66000':<5}{pop:>9}24{'':>7}  {'':>2}  {'':>2}{fy}24"


def item_line(uid, code, thousands):
    return f"{uid}{code}{thousands:>12}2024R "


def units_text(pop_home=1_000_000, pop_peer=1_000_000):
    return "\n".join([unit_line(HOME, "SAN DIEGO CITY", pop_home), unit_line(PEER, "DALLAS CITY", pop_peer, "0930")])


def items_text(rows):
    return "\n".join(item_line(u, c, v) for u, c, v in rows)


def test_parse_units_reads_fixed_columns():
    u = parse_units(units_text())
    assert list(u["unit_id"]) == [HOME, PEER]
    assert list(u["population"]) == [1_000_000, 1_000_000]
    assert list(u["fy_end"]) == ["0630", "0930"]
    assert u.loc[0, "name"] == "SAN DIEGO CITY"


def test_parse_items_converts_thousands_to_dollars():
    i = parse_items(items_text([(HOME, "E62", 5)]))
    assert i.loc[0, "amount_usd"] == 5000 and i.loc[0, "item"] == "E62"


def good_items():
    return parse_items(items_text([(HOME, "E62", 200_000), (HOME, "F62", 50_000), (HOME, "E91", 100_000),
                                   (PEER, "E62", 300_000), (PEER, "E91", 80_000), (HOME, "A01", 999)]))


def test_build_sums_codes_per_group_and_per_resident():
    t = build_peer_spending(parse_units(units_text()), good_items(), PEERS, FUNCS)
    home_police = t[(t.is_home) & (t.group == "police")].iloc[0]
    assert home_police.amount_usd == 250_000_000 and home_police.per_resident == 250
    assert t[(~t.is_home) & (t.group == "police")].iloc[0].city == "Dallas"
    assert set(t.columns) >= {"city", "region", "fy_end", "kind", "label", "per_resident"}


def test_missing_function_is_zero_row_not_absent():
    items = parse_items(items_text([(HOME, "E62", 200_000), (PEER, "E62", 300_000), (HOME, "E91", 100_000)]))
    t = build_peer_spending(parse_units(units_text()), items, PEERS, FUNCS)
    assert t[(~t.is_home) & (t.group == "water")].iloc[0].amount_usd == 0


def test_revenue_codes_are_ignored():
    t = build_peer_spending(parse_units(units_text()), good_items(), PEERS, FUNCS)
    assert "A01" not in set(t["group"])


def test_unmapped_expenditure_code_fails():
    items = parse_items(items_text([(HOME, "E62", 200_000), (PEER, "E62", 300_000), (HOME, "E77", 5)]))
    with pytest.raises(CensusError, match="E77"):
        build_peer_spending(parse_units(units_text()), items, PEERS, FUNCS)


def test_missing_city_fails():
    units = parse_units(unit_line(HOME, "SAN DIEGO CITY", 1_000_000))
    with pytest.raises(CensusError, match=PEER):
        build_peer_spending(units, good_items(), PEERS, FUNCS)


def test_implausible_total_per_resident_fails():
    # population given in thousands by mistake -> $250,000 per resident
    with pytest.raises(CensusError, match="per resident"):
        build_peer_spending(parse_units(units_text(pop_home=1_000)), good_items(), PEERS, FUNCS)


def test_read_zip_member_finds_by_suffix():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2024_Individual_Unit_Files/Fin_PID_2024.txt", "hello")
    assert read_zip_member(buf.getvalue(), "Fin_PID_2024.txt") == "hello"
    with pytest.raises(CensusError):
        read_zip_member(buf.getvalue(), "missing.txt")
```

- [ ] **Step 2: Run** `uv run pytest tests/test_census.py -v` — Expected: FAIL (ImportError: sd_spend.census).

- [ ] **Step 3: Implement `src/sd_spend/census.py`**

```python
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


def parse_units(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if len(line) < 144:
            continue
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
    totals = tidy.groupby("city")[["amount_usd", "population"]].agg({"amount_usd": "sum", "population": "first"})
    for city, row in totals.iterrows():
        per = row.amount_usd / row.population
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

    code_to_group = {c: g for g in functions_cfg["groups"] for c in g["codes"]}
    spend = items[items["unit_id"].isin(wanted) & items["item"].str[0].isin(list(EXPENDITURE_PREFIXES))]
    unmapped = sorted(set(spend["item"]) - set(code_to_group))
    if unmapped:
        raise CensusError(f"expenditure item codes not mapped in census_functions.json: {', '.join(unmapped)}")

    by_group = (spend.assign(group=spend["item"].map(code_to_group))
                .groupby(["unit_id", "group"], as_index=False)["amount_usd"].sum())
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
```

Note: `unit_line` in the test pads the fields to the documented widths (id 12, name 64, county 35, FIPS place 5, population 9, pop-year 2, enrollment 7, enroll-year 2, function 2, school 2, fy 4, survey 2). If Step 4 shows an offset mismatch, fix the test helper's padding to the documented positions, not the parser (the parser positions are copied from the Census doc and checked against the real file in Task 3).

- [ ] **Step 4: Run** `uv run pytest tests/test_census.py -v` — Expected: 9 PASS. (If `unit_line` offsets are off, adjust the test helper per the note.)

- [ ] **Step 5: Commit**

```bash
git add src/sd_spend/census.py tests/test_census.py
git commit -m "Parse and validate Census city finances into per-function, per-resident rows"
```

---

### Task 3: Build script, payload and real-data test

**Files:**
- Modify: `src/sd_spend/export.py` (add `peers_payload`)
- Create: `scripts/build_peers.py`
- Create: `tests/test_real_peers.py`
- Modify: `tests/test_export.py`

**Interfaces:**
- Consumes: Task 2 functions; `save_raw` raw path `data/raw/census/2024_Individual_Unit_Files.zip.gz`.
- Produces: `data/processed/peer_spending.csv`; `site/data/peers.json` =
  `{"fiscal_year": 2024, "home": "San Diego", "groups": [{"key","label","kind"}], "cities": [{"city","state","region","population","fy_end","is_home"}], "rows": [{"city","group","amount","per_resident"}]}`.
  `peers_payload(tidy) -> dict`.

- [ ] **Step 1: Failing test** — append to `tests/test_export.py`

```python
def test_peers_payload_shape():
    import pandas as pd
    from sd_spend.export import peers_payload
    tidy = pd.DataFrame([
        {"city": "San Diego", "state": "CA", "region": "West", "is_home": True, "population": 100, "fy_end": "0630",
         "group": "police", "label": "Police", "kind": "core", "amount_usd": 5000, "per_resident": 50.0},
        {"city": "Dallas", "state": "TX", "region": "South", "is_home": False, "population": 200, "fy_end": "0930",
         "group": "police", "label": "Police", "kind": "core", "amount_usd": 6000, "per_resident": 30.0},
    ])
    p = peers_payload(tidy)
    assert p["home"] == "San Diego" and p["fiscal_year"] == 2024
    assert p["groups"] == [{"key": "police", "label": "Police", "kind": "core"}]
    assert [c["city"] for c in p["cities"]] == ["San Diego", "Dallas"]
    assert p["rows"][0] == {"city": "San Diego", "group": "police", "amount": 5000, "per_resident": 50.0}
```

Run `uv run pytest tests/test_export.py -k peers -v` — Expected: FAIL (ImportError).

- [ ] **Step 2: Implement `peers_payload`** in `src/sd_spend/export.py`

```python
def peers_payload(tidy: pd.DataFrame, fiscal_year: int = 2024) -> dict:
    groups = tidy[["group", "label", "kind"]].drop_duplicates().rename(columns={"group": "key"})
    cities = tidy[["city", "state", "region", "population", "fy_end", "is_home"]].drop_duplicates("city")
    rows = tidy[["city", "group", "amount_usd", "per_resident"]].rename(columns={"amount_usd": "amount"})
    home = tidy.loc[tidy["is_home"], "city"].iloc[0]
    return {
        "fiscal_year": fiscal_year,
        "home": home,
        "groups": groups.to_dict("records"),
        "cities": [{**c, "population": int(c["population"]), "is_home": bool(c["is_home"])}
                   for c in cities.to_dict("records")],
        "rows": [{**r, "amount": int(r["amount"]), "per_resident": round(float(r["per_resident"]), 2)}
                 for r in rows.to_dict("records")],
    }
```

Run the test again — Expected: PASS.

- [ ] **Step 3: Create `scripts/build_peers.py`**

```python
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
    items = parse_items(read_zip_member(zip_bytes, "FinEstDAT_07152026modp.txt"))
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
```

Note: the data file's name embeds a revision date. In `read_zip_member` use suffix `"modp.txt"` if that name differs; prefer `FinEstDAT_*`: change the call to `read_zip_member(zip_bytes, "modp.txt")` only if the exact name above is not in the zip (Step 4 will show).

- [ ] **Step 4: Run** `uv run python scripts/build_peers.py` — Expected: 12 lines of total $ per resident, all between 500 and 8000, no exception. If a `CensusError` names unmapped codes, add them to the right group in `config/census_functions.json` (never loosen the check) and re-run.

- [ ] **Step 5: Real-data test** `tests/test_real_peers.py`

```python
import pandas as pd
from pathlib import Path

CSV = Path(__file__).resolve().parents[1] / "data" / "processed" / "peer_spending.csv"


def test_twelve_cities_all_groups():
    t = pd.read_csv(CSV)
    assert t["city"].nunique() == 12 and t["group"].nunique() == 15
    assert t.groupby("city")["group"].nunique().eq(15).all()


def test_san_diego_police_is_plausible():
    t = pd.read_csv(CSV)
    sd = t[(t.city == "San Diego") & (t.group == "police")].iloc[0]
    assert 300 <= sd.per_resident <= 700   # Census: ~$722M of current operation / 1.38M residents
    assert t[(t.city == "San Diego")].population.iloc[0] == 1_381_162


def test_san_diego_has_no_county_services():
    t = pd.read_csv(CSV)
    assert t[(t.city == "San Diego") & (t.group == "county")].amount_usd.iloc[0] == 0
    assert t[(t.city == "Boston") & (t.group == "county")].amount_usd.iloc[0] > 0  # city-run schools
```

Run `uv run pytest tests/test_real_peers.py -v` — Expected: 3 PASS. If the Boston assertion fails, inspect Boston's E12 in the data and revise the Review Focus note (do not delete the check without a ruling).

- [ ] **Step 6: Commit** `git add -A src scripts tests data/processed site/data && git commit -m "Build peer-city spending table and site JSON from Census data"`

---

### Task 4: JS model with tests

**Files:**
- Create: `site/js/peers-model.js`, `site/js/peers-model.test.js`

**Interfaces:**
- Consumes: `peers.json` shape from Task 3.
- Produces (exported):
  - `KINDS = ["core","utility","outside","debt","other"]`, `DEFAULT_KINDS = ["core"]`
  - `parsePeerHash(hash)` → `{kinds: string[]}` (unknown kinds dropped; empty → default); `serializePeerHash({kinds})` → `"#kinds=core,utility"` (or `""` for the default)
  - `groupStats(data, groupKey)` → `{key,label,home:{per_resident,amount}, median, min, max, rank, of, vsMedianPct, homeIsZero, zeroCities: string[], values:[{city,region,per_resident,is_home}]}` where median/min/max/rank use all 12 cities with `per_resident > 0` (zeros excluded and listed in `zeroCities`), rank 1 = highest per resident, `vsMedianPct` = (home/median - 1) x 100 among non-zero peers (null if home is zero or no non-zero peers)
  - `visibleGroups(data, kinds)` → groups whose kind is in `kinds`, in file order
  - `headline(data, kinds)` → plain-language sentence about the summed per-resident of visible groups, e.g. `"San Diego spends $1,234 per resident on these services, 8% more than the middle peer ($1,143)."`; compares sums only over cities that have at least one visible group >0.

- [ ] **Step 1: Failing tests** `site/js/peers-model.test.js`

```js
import test from "node:test";
import assert from "node:assert/strict";
import { parsePeerHash, serializePeerHash, groupStats, visibleGroups, headline, DEFAULT_KINDS } from "./peers-model.js";

const city = (c, region = "South", home = false) => ({ city: c, state: "XX", region, population: 100, fy_end: "0630", is_home: home });
const data = {
  fiscal_year: 2024, home: "San Diego",
  groups: [{ key: "police", label: "Police", kind: "core" }, { key: "water", label: "Water", kind: "utility" }],
  cities: [city("San Diego", "West", true), city("A"), city("B"), city("C")],
  rows: [
    { city: "San Diego", group: "police", amount: 600, per_resident: 6 },
    { city: "A", group: "police", amount: 400, per_resident: 4 },
    { city: "B", group: "police", amount: 800, per_resident: 8 },
    { city: "C", group: "police", amount: 0, per_resident: 0 },
    { city: "San Diego", group: "water", amount: 0, per_resident: 0 },
    { city: "A", group: "water", amount: 100, per_resident: 1 },
    { city: "B", group: "water", amount: 0, per_resident: 0 },
    { city: "C", group: "water", amount: 0, per_resident: 0 },
  ],
};

test("hash defaults to core and drops unknown kinds", () => {
  assert.deepEqual(parsePeerHash("").kinds, DEFAULT_KINDS);
  assert.deepEqual(parsePeerHash("#kinds=utility,bogus").kinds, ["utility"]);
  assert.deepEqual(parsePeerHash("#kinds=bogus").kinds, DEFAULT_KINDS);
  assert.equal(serializePeerHash({ kinds: DEFAULT_KINDS }), "");
  assert.equal(serializePeerHash({ kinds: ["core", "utility"] }), "#kinds=core,utility");
});

test("stats exclude zero cities from median and rank, and list them", () => {
  const s = groupStats(data, "police");
  assert.equal(s.median, 6); // non-zero values 4,6,8
  assert.equal(s.rank, 2); assert.equal(s.of, 3);
  assert.deepEqual(s.zeroCities, ["C"]);
  assert.equal(s.vsMedianPct, 0);
});

test("home zero gives null comparison, not a crash", () => {
  const s = groupStats(data, "water");
  assert.equal(s.homeIsZero, true); assert.equal(s.vsMedianPct, null); assert.equal(s.rank, null);
});

test("visibleGroups filters by kind", () => {
  assert.deepEqual(visibleGroups(data, ["core"]).map((g) => g.key), ["police"]);
  assert.deepEqual(visibleGroups(data, ["core", "utility"]).map((g) => g.key), ["police", "water"]);
});

test("headline states the comparison in plain words", () => {
  const h = headline(data, ["core"]);
  assert.match(h, /San Diego spends \$6 per resident/);
  assert.match(h, /middle peer/);
});
```

- [ ] **Step 2: Run** `npm test -- site/js/peers-model.test.js` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement `site/js/peers-model.js`**

```js
import { formatPerResident } from "./format.js";

export const KINDS = ["core", "utility", "outside", "debt", "other"];
export const DEFAULT_KINDS = ["core"];

export function parsePeerHash(hash) {
  const m = /kinds=([^&]*)/.exec(hash || "");
  const kinds = m ? m[1].split(",").filter((k) => KINDS.includes(k)) : [];
  return { kinds: kinds.length ? KINDS.filter((k) => kinds.includes(k)) : [...DEFAULT_KINDS] };
}

export function serializePeerHash({ kinds }) {
  const same = kinds.length === DEFAULT_KINDS.length && kinds.every((k, i) => k === DEFAULT_KINDS[i]);
  return same ? "" : `#kinds=${kinds.join(",")}`;
}

export function visibleGroups(data, kinds) {
  return data.groups.filter((g) => kinds.includes(g.kind));
}

function median(values) {
  const v = [...values].sort((a, b) => a - b);
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}

export function groupStats(data, key) {
  const group = data.groups.find((g) => g.key === key);
  const byCity = new Map(data.cities.map((c) => [c.city, c]));
  const values = data.rows.filter((r) => r.group === key)
    .map((r) => ({ city: r.city, region: byCity.get(r.city).region, per_resident: r.per_resident, amount: r.amount, is_home: r.city === data.home }));
  const home = values.find((v) => v.is_home);
  const nonzero = values.filter((v) => v.per_resident > 0);
  const peers = nonzero.filter((v) => !v.is_home);
  const mid = median(peers.map((v) => v.per_resident));
  const homeIsZero = !home || home.per_resident <= 0;
  const ranked = [...nonzero].sort((a, b) => b.per_resident - a.per_resident);
  return {
    key, label: group.label, kind: group.kind, home, values,
    median: mid, min: nonzero.length ? Math.min(...nonzero.map((v) => v.per_resident)) : null,
    max: nonzero.length ? Math.max(...nonzero.map((v) => v.per_resident)) : null,
    rank: homeIsZero ? null : ranked.findIndex((v) => v.is_home) + 1, of: nonzero.length,
    homeIsZero, zeroCities: values.filter((v) => v.per_resident <= 0).map((v) => v.city),
    vsMedianPct: homeIsZero || mid === null || mid === 0 ? null : (home.per_resident / mid - 1) * 100,
  };
}

export function headline(data, kinds) {
  const keys = visibleGroups(data, kinds).map((g) => g.key);
  const totals = new Map();
  for (const r of data.rows) if (keys.includes(r.group)) totals.set(r.city, (totals.get(r.city) || 0) + r.per_resident);
  const home = totals.get(data.home) || 0;
  const peers = [...totals].filter(([c, v]) => c !== data.home && v > 0).map(([, v]) => v);
  const mid = median(peers);
  if (mid === null || mid === 0) return `San Diego spends ${formatPerResident(home)} per resident on these services.`;
  const pct = Math.round(Math.abs(home / mid - 1) * 100);
  const dir = home >= mid ? "more" : "less";
  return `San Diego spends ${formatPerResident(home)} per resident on these services, ${pct}% ${dir} than the middle peer (${formatPerResident(mid)}).`;
}
```

- [ ] **Step 4: Run** `npm test` — Expected: all JS tests pass (29 + 5 new).

- [ ] **Step 5: Commit** `git add site/js/peers-model.js site/js/peers-model.test.js && git commit -m "Add tested JS model for peer comparison"`

---

### Task 5: Peers page, nav, smoke test

**Files:**
- Create: `site/peers.html`, `site/js/peers.js`
- Modify: `site/index.html`, `site/vendors.html`, `site/methods.html` (nav link `peers.html` labelled "Compared with other cities"), `site/css/site.css` (only if a needed class is missing)
- Modify: `tests/test_site_smoke.py`

**Interfaces:**
- Consumes: `peers-model.js` exports, `format.js` (`formatMoney`, `formatPerResident`), `site/data/peers.json`, patterns from `site/vendors.html` and `site/js/vendors.js` (fetch with visible error message, `$`/`css` helpers, `fillTable`, `history.replaceState`).

- [ ] **Step 1: Failing smoke test** — append to `tests/test_site_smoke.py` (follow the existing tests' fixture and `page` usage)

```python
def test_peers_page_renders(site_url, page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/peers.html")
    page.wait_for_selector("#peer-chart svg")
    assert "middle peer" in page.inner_text("#phead")
    assert page.locator("#peer-table tbody tr").count() >= 8
    page.check("#kind-utility")
    assert page.locator("#peer-table tbody tr").count() > 8
    assert "kinds=" in page.url
    assert not errors
```

Run `uv run pytest tests/test_site_smoke.py -m smoke -k peers -v` — Expected: FAIL (404 / selector timeout).

- [ ] **Step 2: Create `site/peers.html`** — same skeleton, `<head>` and nav as `vendors.html` (add the new link in all four pages, `aria-current="page"` here). Main content:
  - `<h1>Compared with other cities</h1>`; `<p id="phead" class="headline" aria-live="polite">Loading…</p>`
  - note paragraph `id="peer-note"`: "Peers are 11 US cities chosen to be broadly similar and to cover several regions. Fiscal years end in different months, and no adjustment is made for cost of living. A higher number is not waste; it can reflect higher prices, wages, or different services. Nothing here is a private-sector comparison."
  - `<form class="controls" aria-label="Which services to include">` with checkboxes `#kind-core` (checked, disabled label "City services (always shown)" — omit disabled if core must be removable; keep it removable but never allow zero: the model defaults to core when none selected), `#kind-utility` "Utilities, transit & airports", `#kind-outside` "Health, welfare, jails & schools (county or school-district services in most places)", `#kind-debt` "Interest on debt", `#kind-other` "Grants to other governments".
  - `<h2>Per resident, by service</h2>`, `<figure>` with `<div id="peer-chart" role="img" aria-label="Dot plot of spending per resident by service for San Diego and 11 peer cities">`, `<details class="method"><summary>Method</summary>` with: source (Census Annual Survey of State and Local Government Finances, FY2024 individual unit files), amounts = current operation plus construction by function, populations as reported by the Census, per resident = amount / population, "a $0 means the city reports no spending there, usually because a county or district provides it; those cities are left out of the median and rank", link to methods.html.
  - `<div class="table-wrap"><table id="peer-table">` with `<caption class="note">` and columns: Service, San Diego, Middle peer, Lowest-highest, San Diego rank, Cities reporting $0.
  - `<h2>The cities</h2>` and `<table id="city-table">`: City, Region, Population, Fiscal year ends.
  - `<script type="module" src="js/peers.js"></script>`

- [ ] **Step 3: Create `site/js/peers.js`** (follow `vendors.js` structure)
  - fetch `data/peers.json`; on failure show message in `#phead` and rethrow.
  - `state = parsePeerHash(location.hash)`; checkbox changes call `update({kinds})` which re-parses via `serializePeerHash`/`parsePeerHash`, `history.replaceState`, `render()`. A "none checked" result falls back to core and re-checks the box.
  - `render()`: set `#phead` to `headline(data, state.kinds)`; groups = `visibleGroups`; stats = groups.map(groupStats).
  - Chart: Plot with `Plot.dot` of peers (`fill` by region using a fixed region domain and CSS variables or a colour-blind-safe scheme such as `Plot.scale({color:{scheme:"tableau10"}})`), median `Plot.tickX`, San Diego `Plot.dot` larger with stroke `css("--accent")` and a text label; y = group labels (`domain` fixed in file order), x = per resident with `tickFormat: formatMoney`; `title` on every dot = `${city}: ${formatPerResident(v)} per resident`; zero cities are not plotted. Width from `clientWidth`, `marginLeft` computed like `drawLeaders` and labels via `truncate`. Add a legend for regions below the chart (plain HTML list, so it is keyboard/screen-reader readable).
  - Tables via a local `fillTable` (copy of the one in `vendors.js`): `peer-table` rows per visible group — label, `formatPerResident(home)` or "$0 (not provided by the city)", median or "n/a", `min-max` or "n/a", `${rank} of ${of}` or "n/a", `zeroCities.join(", ") || "none"`; `city-table` from `data.cities`, fy_end as "June", "September", "December" by `{"0630":"June","0930":"September","1231":"December"}[fy_end] ?? fy_end`.

- [ ] **Step 4: Run** `uv run pytest tests/test_site_smoke.py -m smoke -k peers -v` — Expected: PASS. Then view the page in Chromium at desktop and 390px width (Playwright screenshot to the scratchpad) and read it: labels not clipped, San Diego visibly distinct, legend present.

- [ ] **Step 5: Run the whole suite** `uv run pytest -m "not smoke" && npm test && uv run pytest -m smoke` — Expected: all green.

- [ ] **Step 6: Commit** `git add site tests && git commit -m "Add Compared with other cities page"`

---

### Task 6: Methods page and README

**Files:**
- Modify: `site/methods.html`, `README.md`

- [ ] **Step 1:** In `methods.html` add a section "Compared with other cities" listing: source and URL (`https://www2.census.gov/programs-surveys/gov-finances/tables/2024/`), retrieval date from the MANIFEST, the 11 peers and why (size 0.64-1.7M, city-only providers, regions), exclusions (consolidated city-counties such as Indianapolis, Jacksonville, Philadelphia), fiscal-year-end differences, the function mapping (point to `config/census_functions.json`), the $0 rule, that Boston-type dependent school systems appear only under "Health, welfare, jails & schools", that no cost-of-living adjustment is applied yet, and that this is a peer gap, not a private-sector margin.
- [ ] **Step 2:** In `README.md` add `scripts/fetch_census_finances.py` and `scripts/build_peers.py` to the pipeline description, the new raw/processed paths, and the config files.
- [ ] **Step 3: Run** `uv run pytest -m "not smoke" && npm test` — Expected: green. Smoke methods-page checks still pass: `uv run pytest -m smoke`.
- [ ] **Step 4: Commit** `git add site/methods.html README.md && git commit -m "Document Census peer-city sources, peers and caveats"`
