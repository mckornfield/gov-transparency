# Foundation and "Where Your Dollar Goes" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deployed GitHub Pages site whose first page shows City of San Diego spending (actuals FY2011-23, adopted budgets FY2011-26) as an interactive treemap, with committed raw data and reproducible fetch/build scripts.

**Architecture:** Python (`uv`) fetch scripts save gzip copies of raw CSVs plus a `MANIFEST.csv`; a build step classifies and aggregates them into tidy CSVs and compact JSON in `site/data/`; a static, no-bundler site (`site/`) renders them with d3 and Observable Plot loaded from a pinned CDN URL. Pure JS logic lives in testable ES modules; the DOM layer is covered by a Playwright smoke test.

**Tech Stack:** Python >=3.11, uv, pandas, requests, pytest, pytest-playwright; Node >=20 (`node --test`, no npm dependencies); d3 7.9.0, Observable Plot 0.6.16 (CDN); GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-10-29-gov-transparency-design.md` (this plan covers its build-order steps 1 and 2 plus the Data & Methods page skeleton; steps 3-6 get their own plans).

## Global Constraints

- Python `>=3.11`, managed with `uv`; layout `scripts/fetch_*.py`, `scripts/build_*.py`, `data/raw/` (+ `MANIFEST.csv`), `data/processed/`, `site/`.
- Raw originals are committed (gzip-compressed as `*.csv.gz`); `MANIFEST.csv` records url, retrieved date and sha256 of the original bytes.
- Front end is plain static HTML/JS served from `site/`; no bundler, no npm dependencies.
- Dollars are nominal; fiscal year is labelled by its END year (`report_fy` 23 = FY2023).
- Missing benchmark/coverage is shown as such, never filled in (applies later; do not invent values here).
- Phone layout works (no horizontal scroll at 390px); light and dark mode; every chart has a keyboard-reachable data table; page state is deep-linkable via the URL hash.
- Every commit message ends with these two trailer lines (after a blank line):
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01TciBBGx2gbU5jx95hjH4EJ`
- Do not `git push`, create a GitHub repo, or enable Pages; those are outward-facing and need the user's go-ahead (Task 7, last step).

## Facts about the real data (verified 2026-10-29; the tests below encode them)

- Sources (all CSV, from `https://seshat.datasd.org/`): `operating_actuals/actuals_operating_datasd.csv` (~66 MB, FY11-FY23 only), `operating_budget/budget_operating_datasd.csv` (~61 MB), `accounts_city_budget/budget_reference_accounts_datasd.csv`, `departments_city_budget/budget_reference_depts_datasd.csv`, plus a `*_dictionary_datasd.csv` beside each.
- Actuals columns: `amount, report_fy, fund_type, fund_number, dept_name, funds_center_number, account, account_number`. Budget adds `budget_cycle` (`adopted`, `proposed`, or blank).
- Budget FY24 and FY25 contain BOTH `adopted` and `proposed` rows; summing both double-counts (FY24 expense would be $8.9B instead of about $4.5B). FY26 rows have a blank `budget_cycle`.
- Account numbers starting `5` are expenses, `4` revenue. 12 FY26 budget rows have a blank `account_number`.
- 388 FY26 budget funds centers are absent from the departments reference; all 96 actuals `dept_name`s and the budget ones exist in the reference's `dept_name`.
- `budget_reference_accounts` has unique `account_number`s; expense `account_class`es: Capital Expenditures, Contingencies, Contracts & Services, Debt, Depreciation Expense - Modified, Energy and Utilities, Fringe Benefits, Information Technology, Other, Personnel Cost, Reserves, Supplies, Transfers Out.
- FY23 actual expense is about $3.98B, of which `Transfers Out` is about $0.50B (money moved between funds; hidden by default in the UI).
- `dept_group` has about 65 values in the reference ("Description pending" marks unusable rows). The treemap therefore colours by `account_class`.
- Population: SCO `bythenumbers.sco.ca.gov` dataset `rrtv-rsj9`, `entity_name='San Diego'`, field `estimated_population`; reported for 2003-05, 2007-09, 2011-25; missing 2006, 2010 and 2026.

## Review Focus

- Budget file lists both `adopted` and `proposed` rows for FY24/25: totals must use adopted only (Task 3 test + Task 4 real-data test).
- FY26 budget rows have a blank `budget_cycle` and 388 funds centers missing from the department reference: they must be kept, treated as adopted, and classified via the department-name fallback, not dropped (Task 3).
- Rows with a blank `account_number` have unknown sign: they are excluded from spending but their total is reported in `build_report.json`, never silently dropped (Task 3).
- A treemap leaf that nets to zero or negative (credits) cannot be drawn: it is left out of the picture, included in the totals, and disclosed on the page (Task 5, Task 7).
- Population is missing for some years; per-resident figures for those years use interpolated/carried values and the page says "population estimated" (Task 3, Task 6).
- A hash like `#fy=2030&basis=garbage` must fall back to valid defaults, never throw (Task 5).

## File Structure

```
pyproject.toml                       uv project, pytest config
package.json                         {"type":"module","scripts":{"test":...}} for node --test
.gitignore
README.md                            reproduce steps, sources, data-quality notes
src/sd_spend/__init__.py
src/sd_spend/io.py                   get_with_retry, save_raw, MANIFEST upsert
src/sd_spend/spending.py             classify/aggregate/reconcile operating data; build_population
src/sd_spend/export.py               tidy frames -> site JSON
scripts/fetch_sd_budget.py           4 CSVs + 4 dictionaries -> data/raw/sandiego/
scripts/fetch_sco_population.py      SCO API -> data/raw/sco/
scripts/build_processed.py           raw -> data/processed/*.csv + site/data/*.json
data/raw/MANIFEST.csv, data/raw/**   committed gz copies
data/processed/                      spending.csv, population.csv, build_report.json
site/index.html, site/methods.html
site/css/site.css
site/js/format.js                    money formatting          (+ format.test.js)
site/js/model.js                     rows -> hierarchy/totals  (+ model.test.js)
site/js/state.js                     URL hash <-> state        (+ state.test.js)
site/js/main.js                      DOM wiring, d3/Plot rendering
site/data/spending.json, population.json
tests/test_io.py, test_manifest.py, test_spending.py, test_population.py,
tests/test_export.py, test_real_data.py, test_site_smoke.py
.github/workflows/pages.yml
```

---

### Task 1: Project scaffold and fetch helpers

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `package.json`, `src/sd_spend/__init__.py`, `src/sd_spend/io.py`
- Test: `tests/test_io.py`

**Interfaces:**
- Produces: `sd_spend.io.RAW: Path`; `get_with_retry(url: str, retries: int = 4, backoff: float = 2.0, **kwargs) -> requests.Response`; `save_raw(content: bytes, rel_path: str, url: str, raw_dir: Path = RAW, retrieved: str | None = None) -> Path` (writes `raw_dir/rel_path + ".gz"`, upserts `raw_dir/MANIFEST.csv` with columns `path,url,retrieved,sha256_original,bytes_original`).

- [ ] **Step 1: Create the project files**

`pyproject.toml`:
```toml
[project]
name = "gov-transparency"
version = "0.1.0"
description = "San Diego government spending transparency explorer"
requires-python = ">=3.11"
dependencies = ["pandas>=2.2", "requests>=2.32"]

[dependency-groups]
dev = ["pytest>=8", "pytest-playwright>=0.5"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sd_spend"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["smoke: browser tests that need `playwright install chromium`"]
```

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
node_modules/
.pytest_cache/
test-results/
```

`package.json`:
```json
{
  "name": "gov-transparency-site",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test site/js/*.test.js"
  }
}
```

`src/sd_spend/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/test_io.py`:
```python
import csv
import gzip
import hashlib

import pytest
import requests

from sd_spend import io as sdio


def read_manifest(raw_dir):
    with (raw_dir / "MANIFEST.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_save_raw_writes_gzip_and_manifest(tmp_path):
    content = b"a,b\n1,2\n"
    target = sdio.save_raw(content, "x/data.csv", "http://example.test/data.csv",
                           raw_dir=tmp_path, retrieved="2026-10-29")
    assert target == tmp_path / "x" / "data.csv.gz"
    assert gzip.decompress(target.read_bytes()) == content
    (row,) = read_manifest(tmp_path)
    assert row == {
        "path": "x/data.csv.gz",
        "url": "http://example.test/data.csv",
        "retrieved": "2026-10-29",
        "sha256_original": hashlib.sha256(content).hexdigest(),
        "bytes_original": str(len(content)),
    }


def test_save_raw_upserts_same_path(tmp_path):
    sdio.save_raw(b"one", "d.csv", "http://u", raw_dir=tmp_path, retrieved="2026-01-01")
    sdio.save_raw(b"two", "d.csv", "http://u", raw_dir=tmp_path, retrieved="2026-02-02")
    sdio.save_raw(b"other", "a.csv", "http://v", raw_dir=tmp_path, retrieved="2026-02-02")
    rows = read_manifest(tmp_path)
    assert [r["path"] for r in rows] == ["a.csv.gz", "d.csv.gz"]
    assert rows[1]["sha256_original"] == hashlib.sha256(b"two").hexdigest()


class FakeResponse:
    def raise_for_status(self):
        pass


def test_get_with_retry_retries_then_succeeds(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("boom")
        return FakeResponse()

    monkeypatch.setattr(sdio.requests, "get", fake_get)
    monkeypatch.setattr(sdio.time, "sleep", lambda s: None)
    assert isinstance(sdio.get_with_retry("http://u"), FakeResponse)
    assert len(calls) == 3


def test_get_with_retry_raises_after_exhausting(monkeypatch):
    def always_fail(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(sdio.requests, "get", always_fail)
    monkeypatch.setattr(sdio.time, "sleep", lambda s: None)
    with pytest.raises(requests.ConnectionError):
        sdio.get_with_retry("http://u", retries=2)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv sync && uv run pytest tests/test_io.py -v`
Expected: FAIL (`ImportError: cannot import name 'io' from 'sd_spend'` or similar).

- [ ] **Step 4: Implement `src/sd_spend/io.py`**

```python
"""Fetch helpers: retrying GET, gzip raw copies, and the MANIFEST.csv of what was fetched."""
import csv
import gzip
import hashlib
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
FIELDS = ["path", "url", "retrieved", "sha256_original", "bytes_original"]


def get_with_retry(url: str, retries: int = 4, backoff: float = 2.0, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 300)
    for attempt in range(retries):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(backoff**attempt)


def save_raw(content: bytes, rel_path: str, url: str, raw_dir: Path = RAW,
             retrieved: str | None = None) -> Path:
    """Write content gzip-compressed to raw_dir/rel_path + '.gz' and upsert its MANIFEST row.

    The manifest hashes the ORIGINAL bytes, so a re-fetch can be compared without decompressing.
    """
    target = raw_dir / (rel_path + ".gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(target, "wb", mtime=0) as f:
        f.write(content)
    _upsert_manifest(raw_dir / "MANIFEST.csv", {
        "path": rel_path + ".gz",
        "url": url,
        "retrieved": retrieved or date.today().isoformat(),
        "sha256_original": hashlib.sha256(content).hexdigest(),
        "bytes_original": str(len(content)),
    })
    return target


def _upsert_manifest(path: Path, row: dict) -> None:
    rows = {}
    if path.exists():
        with path.open(newline="") as f:
            rows = {r["path"]: r for r in csv.DictReader(f)}
    rows[row["path"]] = row
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[k] for k in sorted(rows))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_io.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore package.json src tests
git commit -m "Scaffold uv project with fetch helpers and raw-data manifest"
```

---

### Task 2: Fetch scripts and committed raw data

**Files:**
- Create: `scripts/fetch_sd_budget.py`, `scripts/fetch_sco_population.py`
- Create (by running them): `data/raw/MANIFEST.csv`, `data/raw/sandiego/*.csv.gz`, `data/raw/sco/san_diego_population.csv.gz`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `sd_spend.io.get_with_retry`, `save_raw`.
- Produces raw files (read by Task 4) at: `data/raw/sandiego/actuals_operating.csv.gz`, `budget_operating.csv.gz`, `accounts.csv.gz`, `depts.csv.gz`, four `*_dictionary.csv.gz`, and `data/raw/sco/san_diego_population.csv.gz` (columns `entity_name,fiscal_year,estimated_population`).

- [ ] **Step 1: Write the failing manifest-integrity test**

`tests/test_manifest.py`:
```python
import csv
import gzip
import hashlib

from sd_spend.io import RAW

REQUIRED = {
    "sandiego/actuals_operating.csv.gz",
    "sandiego/budget_operating.csv.gz",
    "sandiego/accounts.csv.gz",
    "sandiego/depts.csv.gz",
    "sco/san_diego_population.csv.gz",
}


def manifest_rows():
    with (RAW / "MANIFEST.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_required_sources_are_in_manifest():
    assert REQUIRED <= {r["path"] for r in manifest_rows()}


def test_every_manifest_file_exists_and_matches_hash():
    for row in manifest_rows():
        data = gzip.decompress((RAW / row["path"]).read_bytes())
        assert hashlib.sha256(data).hexdigest() == row["sha256_original"], row["path"]
        assert str(len(data)) == row["bytes_original"], row["path"]
        assert row["url"].startswith("https://"), row["path"]


def test_no_raw_file_is_missing_from_manifest():
    listed = {r["path"] for r in manifest_rows()}
    on_disk = {p.relative_to(RAW).as_posix() for p in RAW.rglob("*.gz")}
    assert on_disk == listed
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: FAIL (`FileNotFoundError` for `MANIFEST.csv`).

- [ ] **Step 3: Write the fetch scripts**

`scripts/fetch_sd_budget.py`:
```python
"""City of San Diego operating budget, operating actuals and their reference tables
(data.sandiego.gov; the files are served from seshat.datasd.org).

report_fy is the END year of the fiscal year (23 = FY2023). The budget file holds both
'adopted' and 'proposed' rows for some years; build_processed.py keeps adopted only.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://seshat.datasd.org"
FILES = {
    "sandiego/actuals_operating.csv": "operating_actuals/actuals_operating_datasd.csv",
    "sandiego/actuals_operating_dictionary.csv": "operating_actuals/operating_actuals_dictionary_datasd.csv",
    "sandiego/budget_operating.csv": "operating_budget/budget_operating_datasd.csv",
    "sandiego/budget_operating_dictionary.csv": "operating_budget/operating_budget_dictionary_datasd.csv",
    "sandiego/accounts.csv": "accounts_city_budget/budget_reference_accounts_datasd.csv",
    "sandiego/accounts_dictionary.csv": "accounts_city_budget/budget_reference_accounts_dictionary_datasd.csv",
    "sandiego/depts.csv": "departments_city_budget/budget_reference_depts_datasd.csv",
    "sandiego/depts_dictionary.csv": "departments_city_budget/budget_reference_depts_dictionary_datasd.csv",
}


def main() -> None:
    for rel_path, remote in FILES.items():
        url = f"{BASE}/{remote}"
        print("fetching", url, flush=True)
        save_raw(get_with_retry(url).content, rel_path, url)


if __name__ == "__main__":
    main()
```

`scripts/fetch_sco_population.py`:
```python
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
```

- [ ] **Step 4: Run the fetch scripts (needs network; about 130 MB download)**

Run:
```bash
uv run python scripts/fetch_sd_budget.py
uv run python scripts/fetch_sco_population.py
du -sh data/raw
```
Expected: 9 "fetching/fetched" lines; `data/raw` a few tens of MB. If any file individually exceeds 50 MB compressed, stop and tell the user before committing.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts data/raw tests/test_manifest.py
git commit -m "Fetch San Diego budget/actuals and SCO population; commit raw copies with manifest"
```

---

### Task 3: Spending and population build logic

**Files:**
- Create: `src/sd_spend/spending.py`
- Test: `tests/test_spending.py`, `tests/test_population.py`

**Interfaces:**
- Consumes: pandas only.
- Produces (all in `sd_spend.spending`):
  - `read_operating(path) -> DataFrame` (ids as str, blanks preserved as `""`, `amount` float)
  - `actuals_frame(df) -> DataFrame` (adds `basis="actual"`)
  - `budget_frame(df) -> tuple[DataFrame, dict]` (adopted only, blank cycle treated as `BLANK_CYCLE_AS`; dict is `{"proposed_rows_dropped": int}`; adds `basis="adopted"`)
  - `classify(df, accounts, depts) -> DataFrame` (adds `fy:int`, `dept_group`, `account_type`, `account_class`, `account_group`; unmapped -> `"Unclassified"`)
  - `split_expenses(df) -> tuple[DataFrame, DataFrame]` (expense rows have `account_number` starting `"5"`; second frame is everything else)
  - `aggregate(df) -> DataFrame` (columns `KEYS + ["amount"]`)
  - `build_spending(actuals, budget, accounts, depts) -> tuple[DataFrame, dict]` (tidy table + report dict)
  - `check_totals(expenses, tidy)`, `check_budget_vs_actual(tidy, tolerance=0.25)`, `check_yoy(tidy, limit=0.4)`; each raises `ReconciliationError`
  - `build_population(raw, first_fy=2011, last_fy=2026) -> DataFrame` (columns `fy, population, source`; source in `reported|interpolated|carried_forward`)
  - constants `KEYS`, `UNCLASSIFIED`, `BLANK_CYCLE_AS`

- [ ] **Step 1: Write the failing spending tests**

`tests/test_spending.py`:
```python
import pandas as pd
import pytest

from sd_spend import spending as sp

ACCOUNTS = pd.DataFrame({
    "account_type": ["Personnel", "Non-Personnel", "Non-Personnel", "Property Tax Revenue"],
    "account_class": ["Personnel Cost", "Contracts & Services", "Transfers Out", "Property Taxes"],
    "account_group": ["Salaries", "Consultants", "Transfers Out", "Property Tax"],
    "account": ["Salaried Wages", "Consulting", "Transfer Out", "Prop Tax"],
    "account_number": ["500011", "510001", "590001", "400001"],
})
DEPTS = pd.DataFrame({
    "dept_group": ["Police", "Library", "Description pending"],
    "dept_name": ["Police", "Library", "Description pending"],
    "dept_division": ["x", "y", "z"],
    "dept_section": ["x", "y", "z"],
    "funds_center": ["a", "b", "DELETE"],
    "funds_center_number": ["1001", "2002", "0"],
})


def actuals_df(rows):
    return pd.DataFrame(rows, columns=["amount", "report_fy", "fund_type", "fund_number",
                                       "dept_name", "funds_center_number", "account", "account_number"])


def budget_df(rows):
    return pd.DataFrame(rows, columns=["amount", "report_fy", "budget_cycle", "fund_type", "fund_number",
                                       "dept_name", "funds_center_number", "account", "account_number"])


def test_budget_frame_keeps_adopted_and_blank_cycle_drops_proposed():
    df = budget_df([
        (100.0, "24", "adopted", "General Fund", "1", "Police", "1001", "x", "500011"),
        (100.0, "24", "proposed", "General Fund", "1", "Police", "1001", "x", "500011"),
        (50.0, "26", "", "General Fund", "1", "Police", "1001", "x", "500011"),
    ])
    out, report = sp.budget_frame(df)
    assert sorted(out["report_fy"]) == ["24", "26"]
    assert set(out["basis"]) == {"adopted"}
    assert report == {"proposed_rows_dropped": 1}


def test_classify_maps_reference_and_falls_back_to_unclassified():
    df = actuals_df([
        (10.0, "23", "General Fund", "1", "Police", "1001", "Salaried Wages", "500011"),
        (5.0, "23", "General Fund", "1", "Library", "9999", "Mystery", "599999"),
        (7.0, "23", "General Fund", "1", "Unknown Dept", "9998", "Consulting", "510001"),
    ])
    out = sp.classify(sp.actuals_frame(df), ACCOUNTS, DEPTS)
    by_center = out.set_index("funds_center_number")
    assert by_center.loc["1001", "dept_group"] == "Police"
    assert by_center.loc["1001", "account_class"] == "Personnel Cost"
    # funds center missing from the reference falls back to the dept_name mapping
    assert by_center.loc["9999", "dept_group"] == "Library"
    # unmapped account number
    assert by_center.loc["9999", "account_class"] == sp.UNCLASSIFIED
    # neither funds center nor dept_name known
    assert by_center.loc["9998", "dept_group"] == sp.UNCLASSIFIED
    assert (out["fy"] == 2023).all()


def test_classify_rejects_duplicate_account_numbers():
    dup = pd.concat([ACCOUNTS, ACCOUNTS.iloc[[0]]], ignore_index=True)
    df = actuals_df([(1.0, "23", "General Fund", "1", "Police", "1001", "x", "500011")])
    with pytest.raises(sp.ReconciliationError):
        sp.classify(sp.actuals_frame(df), dup, DEPTS)


def test_split_expenses_separates_revenue_and_blank_accounts():
    df = actuals_df([
        (10.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (99.0, "23", "General Fund", "1", "Police", "1001", "rev", "400001"),
        (3.0, "23", "General Fund", "1", "Police", "1001", "blank", ""),
    ])
    expenses, other = sp.split_expenses(sp.actuals_frame(df))
    assert list(expenses["amount"]) == [10.0]
    assert sorted(other["amount"]) == [3.0, 99.0]


def test_build_spending_keeps_negatives_and_reports_excluded():
    actuals = actuals_df([
        (100.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (-20.0, "23", "General Fund", "1", "Police", "1001", "x", "500011"),
        (40.0, "23", "General Fund", "1", "Library", "2002", "x", "510001"),
        (500.0, "23", "General Fund", "1", "Police", "1001", "rev", "400001"),
    ])
    budget = budget_df([
        (105.0, "23", "adopted", "General Fund", "1", "Police", "1001", "x", "500011"),
        (42.0, "23", "adopted", "General Fund", "1", "Library", "2002", "x", "510001"),
        (999.0, "23", "proposed", "General Fund", "1", "Police", "1001", "x", "500011"),
        (8.0, "26", "", "General Fund", "1", "Police", "5555", "x", ""),
    ])
    tidy, report = sp.build_spending(actuals, budget, ACCOUNTS, DEPTS)
    total = tidy.groupby(["basis", "fy"])["amount"].sum()
    assert total[("actual", 2023)] == 120.0
    assert total[("adopted", 2023)] == 147.0
    assert ("adopted", 2026) not in total.index
    assert list(tidy.columns) == sp.KEYS + ["amount"]
    assert report["proposed_rows_dropped"] == 1
    assert report["excluded_non_expense"]["adopted"]["2026"] == 8.0
    assert report["excluded_non_expense"]["actual"]["2023"] == 500.0
    assert report["blank_account"] == {"adopted": {"2026": 8.0}}


def test_check_totals_detects_a_lost_row():
    expenses = pd.DataFrame({"basis": ["actual"], "fy": [2023], "amount": [100.0]})
    tidy = pd.DataFrame({"basis": ["actual"], "fy": [2023], "amount": [90.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_totals(expenses, tidy)


def test_check_budget_vs_actual_flags_double_counting():
    tidy = pd.DataFrame({"basis": ["actual", "adopted"], "fy": [2023, 2023], "amount": [100.0, 210.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_budget_vs_actual(tidy)
    ok = pd.DataFrame({"basis": ["actual", "adopted"], "fy": [2023, 2023], "amount": [100.0, 110.0]})
    sp.check_budget_vs_actual(ok)


def test_check_yoy_flags_a_doubled_year():
    tidy = pd.DataFrame({"basis": ["adopted"] * 3, "fy": [2023, 2024, 2025],
                         "amount": [100.0, 105.0, 210.0]})
    with pytest.raises(sp.ReconciliationError):
        sp.check_yoy(tidy)
```

`tests/test_population.py`:
```python
import pandas as pd

from sd_spend.spending import build_population


def raw(pairs):
    return pd.DataFrame({
        "entity_name": "San Diego",
        "fiscal_year": [str(y) for y, _ in pairs],
        "estimated_population": [str(p) for _, p in pairs],
    })


def test_interpolates_gaps_and_carries_forward():
    out = build_population(raw([(2011, 100), (2013, 300), (2014, 400)]), first_fy=2011, last_fy=2015)
    assert list(out["fy"]) == [2011, 2012, 2013, 2014, 2015]
    assert list(out["population"]) == [100, 200, 300, 400, 400]
    assert list(out["source"]) == ["reported", "interpolated", "reported", "reported", "carried_forward"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_spending.py tests/test_population.py -v`
Expected: FAIL (`ImportError: cannot import name 'spending'`).

- [ ] **Step 3: Implement `src/sd_spend/spending.py`**

```python
"""Turn the raw San Diego operating files into tidy spending tables, with reconciliation checks."""
import pandas as pd

# FY26 budget rows have a blank budget_cycle; they are treated as the adopted budget (see methods page).
BLANK_CYCLE_AS = "adopted"
UNCLASSIFIED = "Unclassified"
PENDING = "Description pending"
ID_COLS = {"account_number": str, "funds_center_number": str, "fund_number": str, "report_fy": str}
KEYS = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class", "account_group", "account"]


class ReconciliationError(AssertionError):
    pass


def read_operating(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=ID_COLS, keep_default_na=False)


def actuals_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["basis"] = "actual"
    return out


def budget_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cycle = df["budget_cycle"].where(df["budget_cycle"] != "", BLANK_CYCLE_AS)
    keep = cycle == "adopted"
    out = df[keep].copy()
    out["basis"] = "adopted"
    return out, {"proposed_rows_dropped": int((cycle == "proposed").sum())}


def _dept_lookups(depts: pd.DataFrame):
    usable = depts[depts["dept_group"] != PENDING]
    by_center = usable.drop_duplicates("funds_center_number").set_index("funds_center_number")["dept_group"]
    by_name = usable.groupby("dept_name")["dept_group"].agg(lambda s: s.mode().iloc[0])
    return by_center, by_name


def classify(df: pd.DataFrame, accounts: pd.DataFrame, depts: pd.DataFrame) -> pd.DataFrame:
    if not accounts["account_number"].is_unique:
        raise ReconciliationError("account reference has duplicate account_number values")
    by_center, by_name = _dept_lookups(depts)
    cols = ["account_number", "account_type", "account_class", "account_group"]
    out = df.merge(accounts[cols], on="account_number", how="left")
    for col in cols[1:]:
        out[col] = out[col].fillna(UNCLASSIFIED)
    group = out["funds_center_number"].map(by_center)
    group = group.fillna(out["dept_name"].map(by_name))
    out["dept_group"] = group.fillna(UNCLASSIFIED)
    out["fy"] = 2000 + out["report_fy"].astype(int)
    return out


def split_expenses(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_expense = df["account_number"].str.startswith("5")
    return df[is_expense], df[~is_expense]


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(KEYS, as_index=False)["amount"].sum()


def _totals(df: pd.DataFrame) -> pd.Series:
    return df.groupby(["basis", "fy"])["amount"].sum()


def _nested_totals(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for (basis, fy), amount in _totals(df).items():
        out.setdefault(basis, {})[str(fy)] = round(float(amount), 2)
    return out


def check_totals(expenses: pd.DataFrame, tidy: pd.DataFrame) -> None:
    diff = (_totals(expenses) - _totals(tidy)).abs()
    bad = diff[diff > 0.5]
    if len(bad):
        raise ReconciliationError(f"aggregation changed totals:\n{bad}")


def check_budget_vs_actual(tidy: pd.DataFrame, tolerance: float = 0.25) -> None:
    totals = _totals(tidy).unstack("basis")
    both = totals.dropna(subset=["actual", "adopted"])
    ratio = both["adopted"] / both["actual"] - 1
    bad = ratio[ratio.abs() > tolerance]
    if len(bad):
        raise ReconciliationError(f"adopted budget differs from actuals by more than {tolerance:.0%}:\n{bad}")


def check_yoy(tidy: pd.DataFrame, limit: float = 0.4) -> None:
    totals = _totals(tidy).unstack("basis").sort_index()
    change = totals.pct_change(fill_method=None)
    bad = change[(change.abs() > limit).any(axis=1)]
    if len(bad):
        raise ReconciliationError(f"year-over-year total changed by more than {limit:.0%}:\n{bad}")


def build_spending(actuals: pd.DataFrame, budget: pd.DataFrame, accounts: pd.DataFrame,
                   depts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    budget_rows, report = budget_frame(budget)
    combined = pd.concat([actuals_frame(actuals), budget_rows], ignore_index=True)
    classified = classify(combined, accounts, depts)
    expenses, other = split_expenses(classified)
    tidy = aggregate(expenses)
    check_totals(expenses, tidy)
    check_budget_vs_actual(tidy)
    check_yoy(tidy)
    report["excluded_non_expense"] = _nested_totals(other)
    report["blank_account"] = _nested_totals(other[other["account_number"] == ""])
    report["unclassified_amount"] = round(float(
        tidy.loc[(tidy["dept_group"] == UNCLASSIFIED) | (tidy["account_class"] == UNCLASSIFIED), "amount"].sum()), 2)
    return tidy, report


def build_population(raw: pd.DataFrame, first_fy: int = 2011, last_fy: int = 2026) -> pd.DataFrame:
    reported_by_year = (raw.assign(fy=raw["fiscal_year"].astype(int),
                                   population=raw["estimated_population"].astype(float))
                        .drop_duplicates("fy").set_index("fy")["population"])
    years = pd.RangeIndex(first_fy, last_fy + 1)
    reported = reported_by_year.reindex(years)
    filled = reported.interpolate(limit_area="inside")
    source = pd.Series("reported", index=years)
    source[reported.isna() & filled.notna()] = "interpolated"
    source[filled.isna()] = "carried_forward"
    filled = filled.ffill()
    return pd.DataFrame({"fy": list(years), "population": filled.round().astype(int).to_numpy(),
                         "source": source.to_numpy()})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spending.py tests/test_population.py -v`
Expected: all pass. If `test_check_yoy_flags_a_doubled_year` fails because `pct_change` output contains NaN in the first row, confirm `(change.abs() > limit).any(axis=1)` ignores NaN (it does) before changing anything else.

- [ ] **Step 5: Commit**

```bash
git add src/sd_spend/spending.py tests/test_spending.py tests/test_population.py
git commit -m "Add spending classification, aggregation, reconciliation and population build"
```

---

### Task 4: Export to site JSON and run the real build

**Files:**
- Create: `src/sd_spend/export.py`, `scripts/build_processed.py`
- Create (by running): `data/processed/spending.csv`, `data/processed/population.csv`, `data/processed/build_report.json`, `site/data/spending.json`, `site/data/population.json`
- Test: `tests/test_export.py`, `tests/test_real_data.py`

**Interfaces:**
- Consumes: `sd_spend.spending.*` (Task 3), raw files (Task 2).
- Produces: `sd_spend.export.spending_payload(tidy) -> dict` and `population_payload(pop) -> dict`; `site/data/spending.json` shaped `{"columns": ["basis","fy","dept_group","dept_name","account_type","account_class","amount"], "rows": [[...], ...]}` (amount = whole dollars, int); `site/data/population.json` shaped `{"rows": [{"fy": 2023, "population": 1368395, "source": "reported"}, ...]}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_export.py`:
```python
import pandas as pd

from sd_spend import export
from sd_spend.spending import KEYS


def test_spending_payload_collapses_to_class_level_and_rounds():
    tidy = pd.DataFrame([
        ("actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Wages", 100.4),
        ("actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", "Salaries", "Overtime", 50.4),
        ("actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", "Books", "Books", -3.0),
    ], columns=KEYS + ["amount"])
    payload = export.spending_payload(tidy)
    assert payload["columns"] == ["basis", "fy", "dept_group", "dept_name", "account_type",
                                  "account_class", "amount"]
    assert sorted(payload["rows"]) == [
        ["actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", -3],
        ["actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", 151],
    ]


def test_population_payload():
    pop = pd.DataFrame({"fy": [2011, 2012], "population": [10, 20], "source": ["reported", "interpolated"]})
    assert export.population_payload(pop) == {"rows": [
        {"fy": 2011, "population": 10, "source": "reported"},
        {"fy": 2012, "population": 20, "source": "interpolated"},
    ]}
```

`tests/test_real_data.py`:
```python
"""Checks against the committed processed data; guards the known traps in the raw files."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spending = pd.read_csv(ROOT / "data/processed/spending.csv")
population = pd.read_csv(ROOT / "data/processed/population.csv")
site = json.loads((ROOT / "site/data/spending.json").read_text())
report = json.loads((ROOT / "data/processed/build_report.json").read_text())


def total(basis, fy, df=spending):
    return df[(df["basis"] == basis) & (df["fy"] == fy)]["amount"].sum()


def test_fy2023_actual_is_about_four_billion():
    assert 3.5e9 < total("actual", 2023) < 4.5e9


def test_adopted_budget_is_not_double_counted():
    # raw FY24 has adopted+proposed rows; summing both gives about $8.9B
    assert 3.5e9 < total("adopted", 2024) < 6e9
    assert 3.5e9 < total("adopted", 2025) < 6e9
    assert report["proposed_rows_dropped"] > 0


def test_fy2026_blank_cycle_rows_are_kept():
    assert total("adopted", 2026) > 1e9


def test_unmapped_funds_centers_are_classified_not_dropped():
    # 388 FY26 funds centers are missing from the reference; the dept_name fallback must still place them
    fy26 = spending[(spending["basis"] == "adopted") & (spending["fy"] == 2026)]
    unclassified = fy26.loc[fy26["dept_group"] == "Unclassified", "amount"].sum()
    assert unclassified < 0.02 * fy26["amount"].sum()
    assert fy26["dept_group"].nunique() > 20


def test_blank_account_rows_are_reported_not_hidden():
    assert report["blank_account"]["adopted"]["2026"] != 0


def test_population_covers_every_fiscal_year():
    assert list(population["fy"]) == list(range(2011, 2027))
    assert set(population["source"]) <= {"reported", "interpolated", "carried_forward"}
    assert population.loc[population["fy"] == 2026, "source"].item() == "carried_forward"
    assert population.loc[population["fy"] == 2023, "source"].item() == "reported"


def test_site_json_conserves_totals():
    rows = pd.DataFrame(site["rows"], columns=site["columns"])
    for (basis, fy), expected in spending.groupby(["basis", "fy"])["amount"].sum().items():
        got = rows[(rows["basis"] == basis) & (rows["fy"] == fy)]["amount"].sum()
        n = ((rows["basis"] == basis) & (rows["fy"] == fy)).sum()
        assert abs(got - expected) <= 0.5 * n + 1, (basis, fy)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL (`ImportError: cannot import name 'export'`). (`tests/test_real_data.py` also fails at collection because the processed files do not exist yet; that is expected until Step 5.)

- [ ] **Step 3: Implement `src/sd_spend/export.py`**

```python
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


def population_payload(pop: pd.DataFrame) -> dict:
    return {"rows": [{"fy": int(r.fy), "population": int(r.population), "source": str(r.source)}
                     for r in pop.itertuples(index=False)]}
```

- [ ] **Step 4: Write `scripts/build_processed.py`**

```python
"""Raw San Diego files -> data/processed/*.csv and site/data/*.json.

Fails (ReconciliationError) rather than writing numbers that do not reconcile; do not loosen the
tolerances in sd_spend.spending to make it pass, investigate the data and tell the user.
"""
import json

import pandas as pd

from sd_spend import export, spending
from sd_spend.io import RAW, ROOT

PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n")


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    sd = RAW / "sandiego"
    actuals = spending.read_operating(sd / "actuals_operating.csv.gz")
    budget = spending.read_operating(sd / "budget_operating.csv.gz")
    accounts = pd.read_csv(sd / "accounts.csv.gz", dtype=str, keep_default_na=False)
    depts = pd.read_csv(sd / "depts.csv.gz", dtype=str, keep_default_na=False)
    tidy, report = spending.build_spending(actuals, budget, accounts, depts)
    population = spending.build_population(
        pd.read_csv(RAW / "sco" / "san_diego_population.csv.gz", dtype=str))

    tidy.to_csv(PROCESSED / "spending.csv", index=False)
    population.to_csv(PROCESSED / "population.csv", index=False)
    (PROCESSED / "build_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_json(SITE_DATA / "spending.json", export.spending_payload(tidy))
    write_json(SITE_DATA / "population.json", export.population_payload(population))

    print(tidy.groupby(["basis", "fy"])["amount"].sum().div(1e6).round(0).unstack("basis"))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the build and all Python tests**

Run: `uv run python scripts/build_processed.py && uv run pytest -v`
Expected: the printed table shows actual FY2011-23 near $2.3B-$4.0B and adopted FY2011-26 near $2.5B-$5.2B (no year near $9B); every test passes. If a `ReconciliationError` fires or a real-data test fails, stop, do not change tolerances or expected ranges, and report the output to the user.

- [ ] **Step 6: Check output size and commit**

Run: `ls -la site/data data/processed`
Expected: `site/data/spending.json` under about 8 MB (GitHub Pages gzips it in transit). If larger, tell the user before committing.

```bash
git add src/sd_spend/export.py scripts/build_processed.py data/processed site/data tests/test_export.py tests/test_real_data.py
git commit -m "Build processed spending tables and site JSON with reconciliation checks"
```

---

### Task 5: Pure JS modules (format, model, state)

**Files:**
- Create: `site/js/format.js`, `site/js/model.js`, `site/js/state.js`
- Test: `site/js/format.test.js`, `site/js/model.test.js`, `site/js/state.test.js`

**Interfaces:**
- Produces:
  - `format.js`: `formatMoney(value: number): string`, `formatPerResident(value: number): string`
  - `model.js`: `DEFAULTS = {fy: 2023, basis: "actual", mode: "total", transfers: false}`; `TRANSFERS_CLASS = "Transfers Out"`; `rowsFromColumns({columns, rows}) -> object[]`; `availableYears(rows) -> {actual: number[], adopted: number[]}`; `totalsByYear(rows, {basis, includeTransfers?}) -> {fy, total}[]`; `buildHierarchy(rows, {fy, basis, divisor?, includeTransfers?}) -> {root, total, rawTotal, omitted: {amount, count}}` where `root = {name, children: [{name: dept_group, children: [{name: account_class, value}]}]}`
  - `state.js`: `parseHash(hash: string, years: {actual: number[], adopted: number[]}) -> {fy, basis, mode, transfers}`; `serializeHash(state) -> string`

- [ ] **Step 1: Write the failing tests**

`site/js/format.test.js`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { formatMoney, formatPerResident } from "./format.js";

test("formatMoney scales and rounds", () => {
  assert.equal(formatMoney(3.98e9), "$4.0B");
  assert.equal(formatMoney(320e6), "$320M");
  assert.equal(formatMoney(12.34e6), "$12.3M");
  assert.equal(formatMoney(45600), "$46K");
  assert.equal(formatMoney(812), "$812");
  assert.equal(formatMoney(0), "$0");
  assert.equal(formatMoney(-2.5e6), "-$2.5M");
});

test("formatMoney never prints a rounded value at the wrong scale", () => {
  assert.equal(formatMoney(999_600), "$1.0M");
  assert.equal(formatMoney(99_960_000), "$100M");
  assert.equal(formatMoney(999_600_000), "$1.0B");
});

test("formatPerResident", () => {
  assert.equal(formatPerResident(1234.6), "$1,235");
  assert.equal(formatPerResident(-50), "-$50");
});
```

`site/js/model.test.js`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { rowsFromColumns, availableYears, totalsByYear, buildHierarchy } from "./model.js";

const columns = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class", "amount"];
const rows = rowsFromColumns({ columns, rows: [
  ["actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", 600],
  ["actual", 2023, "Police", "Police", "Non-Personnel", "Supplies", 100],
  ["actual", 2023, "Police", "Police", "Non-Personnel", "Transfers Out", 50],
  ["actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", -30],
  ["actual", 2022, "Police", "Police", "Personnel", "Personnel Cost", 900],
  ["adopted", 2023, "Police", "Police", "Personnel", "Personnel Cost", 700],
] });

test("rowsFromColumns builds objects", () => {
  assert.deepEqual(rows[0], { basis: "actual", fy: 2023, dept_group: "Police", dept_name: "Police",
    account_type: "Personnel", account_class: "Personnel Cost", amount: 600 });
});

test("availableYears per basis", () => {
  assert.deepEqual(availableYears(rows), { actual: [2022, 2023], adopted: [2023] });
});

test("totalsByYear hides transfers unless asked", () => {
  assert.deepEqual(totalsByYear(rows, { basis: "actual" }), [{ fy: 2022, total: 900 }, { fy: 2023, total: 670 }]);
  assert.equal(totalsByYear(rows, { basis: "actual", includeTransfers: true })[1].total, 720);
});

test("buildHierarchy nests group -> class, sorted, excluding transfers by default", () => {
  const { root, total, rawTotal } = buildHierarchy(rows, { fy: 2023, basis: "actual" });
  assert.deepEqual(root.children.map((g) => g.name), ["Police"]);
  assert.deepEqual(root.children[0].children, [
    { name: "Personnel Cost", value: 600 }, { name: "Supplies", value: 100 }]);
  assert.equal(total, 670);
  assert.equal(rawTotal, 670);
});

test("net-credit leaves are omitted from the tree, kept in the total, and disclosed", () => {
  const { root, total, omitted } = buildHierarchy(rows, { fy: 2023, basis: "actual" });
  assert.ok(!root.children.some((g) => g.name === "Library"));
  assert.equal(total, 670); // includes the -30
  assert.deepEqual(omitted, { amount: -30, count: 1 });
});

test("includeTransfers adds the transfers leaf", () => {
  const { root, total } = buildHierarchy(rows, { fy: 2023, basis: "actual", includeTransfers: true });
  assert.deepEqual(root.children[0].children.map((c) => c.name), ["Personnel Cost", "Supplies", "Transfers Out"]);
  assert.equal(total, 720);
});

test("divisor scales values and total but not rawTotal", () => {
  const { root, total, rawTotal } = buildHierarchy(rows, { fy: 2023, basis: "actual", divisor: 10 });
  assert.equal(root.children[0].children[0].value, 60);
  assert.equal(total, 67);
  assert.equal(rawTotal, 670);
});

test("other basis/year are ignored and an empty selection is safe", () => {
  assert.equal(buildHierarchy(rows, { fy: 2023, basis: "adopted" }).total, 700);
  const empty = buildHierarchy(rows, { fy: 1999, basis: "actual" });
  assert.deepEqual(empty.root.children, []);
  assert.equal(empty.total, 0);
});
```

`site/js/state.test.js`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { parseHash, serializeHash } from "./state.js";

const years = { actual: [2011, 2012, 2023], adopted: [2011, 2023, 2026] };

test("parses a valid hash", () => {
  assert.deepEqual(parseHash("#fy=2012&basis=actual&mode=perResident&transfers=1", years),
    { fy: 2012, basis: "actual", mode: "perResident", transfers: true });
});

test("garbage falls back to defaults without throwing", () => {
  assert.deepEqual(parseHash("#fy=abc&basis=zzz&mode=%00&transfers=maybe", years),
    { fy: 2023, basis: "actual", mode: "total", transfers: false });
  assert.deepEqual(parseHash("", years), { fy: 2023, basis: "actual", mode: "total", transfers: false });
});

test("a year that does not exist for the basis falls back to the default year", () => {
  assert.equal(parseHash("#fy=2030&basis=adopted", years).fy, 2023);
  assert.equal(parseHash("#fy=2026&basis=actual", years).fy, 2023);
});

test("when the default year is unavailable, the latest year is used", () => {
  assert.equal(parseHash("", { actual: [2011, 2012], adopted: [] }).fy, 2012);
});

test("serialize then parse round-trips", () => {
  const state = { fy: 2026, basis: "adopted", mode: "perResident", transfers: true };
  assert.deepEqual(parseHash(serializeHash(state), years), state);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test`
Expected: FAIL (`ERR_MODULE_NOT_FOUND` for `./format.js`, `./model.js`, `./state.js`).

- [ ] **Step 3: Implement the modules**

`site/js/format.js`:
```js
// Compact money formatting. Thresholds sit just below each power of ten so a value that rounds up
// (999,600 -> "1.0") is printed at the next scale instead of as "$1000K".
export function formatMoney(value) {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 999.5e6) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 99.95e6) return `${sign}$${Math.round(abs / 1e6)}M`;
  if (abs >= 999.5e3) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 999.5) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

export function formatPerResident(value) {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.round(Math.abs(value)).toLocaleString("en-US")}`;
}
```

`site/js/model.js`:
```js
export const DEFAULTS = { fy: 2023, basis: "actual", mode: "total", transfers: false };
// Money moved between city funds; counting it makes the same dollars appear twice, so it is
// hidden unless the reader asks for it.
export const TRANSFERS_CLASS = "Transfers Out";

export function rowsFromColumns({ columns, rows }) {
  return rows.map((row) => Object.fromEntries(columns.map((column, i) => [column, row[i]])));
}

function selected(rows, includeTransfers) {
  return includeTransfers ? rows : rows.filter((r) => r.account_class !== TRANSFERS_CLASS);
}

export function availableYears(rows) {
  const years = { actual: new Set(), adopted: new Set() };
  for (const row of rows) years[row.basis]?.add(row.fy);
  const sorted = (set) => [...set].sort((a, b) => a - b);
  return { actual: sorted(years.actual), adopted: sorted(years.adopted) };
}

export function totalsByYear(rows, { basis, includeTransfers = false }) {
  const totals = new Map();
  for (const row of selected(rows, includeTransfers)) {
    if (row.basis === basis) totals.set(row.fy, (totals.get(row.fy) ?? 0) + row.amount);
  }
  return [...totals].sort((a, b) => a[0] - b[0]).map(([fy, total]) => ({ fy, total }));
}

export function buildHierarchy(rows, { fy, basis, divisor = 1, includeTransfers = false }) {
  const leaves = new Map();
  let rawTotal = 0;
  for (const row of selected(rows, includeTransfers)) {
    if (row.basis !== basis || row.fy !== fy) continue;
    rawTotal += row.amount;
    const key = `${row.dept_group}\u0000${row.account_class}`;
    leaves.set(key, (leaves.get(key) ?? 0) + row.amount);
  }
  const groups = new Map();
  let omittedAmount = 0;
  let omittedCount = 0;
  for (const [key, amount] of leaves) {
    if (amount <= 0) { // a treemap cannot draw a zero or negative area; disclosed to the reader
      omittedAmount += amount;
      omittedCount += 1;
      continue;
    }
    const [group, spendClass] = key.split("\u0000");
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push({ name: spendClass, value: amount / divisor });
  }
  const children = [...groups].map(([name, kids]) => ({
    name, children: kids.sort((a, b) => b.value - a.value) }));
  return {
    root: { name: "City of San Diego", children },
    total: rawTotal / divisor,
    rawTotal,
    omitted: { amount: omittedAmount, count: omittedCount },
  };
}
```

`site/js/state.js`:
```js
import { DEFAULTS } from "./model.js";

const BASES = ["actual", "adopted"];
const MODES = ["total", "perResident"];

// Always returns a valid state: unknown values fall back to the default, never throw.
export function parseHash(hash, years) {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const basis = BASES.includes(params.get("basis")) ? params.get("basis") : DEFAULTS.basis;
  const mode = MODES.includes(params.get("mode")) ? params.get("mode") : DEFAULTS.mode;
  const transfers = params.get("transfers") === "1";
  const valid = years[basis] ?? [];
  const wanted = Number.parseInt(params.get("fy"), 10);
  let fy = DEFAULTS.fy;
  if (valid.includes(wanted)) fy = wanted;
  else if (!valid.includes(DEFAULTS.fy)) fy = valid.at(-1) ?? DEFAULTS.fy;
  return { fy, basis, mode, transfers };
}

export function serializeHash({ fy, basis, mode, transfers }) {
  return `#fy=${fy}&basis=${basis}&mode=${mode}&transfers=${transfers ? 1 : 0}`;
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `npm test`
Expected: all tests pass (format 3, model 8, state 5).

- [ ] **Step 5: Commit**

```bash
git add site/js
git commit -m "Add tested JS modules for money formatting, spending hierarchy and URL state"
```

---

### Task 6: Page UI and Data & Methods page

**Files:**
- Create: `site/index.html`, `site/methods.html`, `site/css/site.css`, `site/js/main.js`

**Interfaces:**
- Consumes: `site/data/spending.json`, `site/data/population.json` (Task 4); `model.js`, `state.js`, `format.js` (Task 5).
- Produces DOM ids used by the smoke test (Task 7): `#headline`, `#totals-chart`, `#treemap` (contains `svg rect.leaf`), `#legend`, `#omitted-note`, `#table-body`, `#value-head`, `#fy`, `#fy-label`, `#transfers`, radios `input[name=basis]` (`actual|adopted`) and `input[name=mode]` (`total|perResident`), and at least two `details.method` elements.

- [ ] **Step 1: Write `site/css/site.css`**

```css
:root {
  --bg: #ffffff; --text: #1b1f24; --muted: #5b6672; --line: #d8dee4;
  --accent: #0b5fff; --bar: #b9c4d4; --panel: #f5f7fa;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12161b; --text: #e6e9ee; --muted: #9aa5b1; --line: #2a323b;
    --accent: #6ea0ff; --bar: #3a4656; --panel: #1a2028;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
a { color: var(--accent); }
.site-header { border-bottom: 1px solid var(--line); }
.site-header nav { display: flex; flex-wrap: wrap; gap: 1rem; align-items: baseline;
  max-width: 1100px; margin: 0 auto; padding: .75rem 16px; }
.site-header a[aria-current="page"] { font-weight: 600; color: var(--text); text-decoration: none; }
main { max-width: 1100px; margin: 0 auto; padding: 1rem 16px 3rem; }
h1 { font-size: clamp(1.5rem, 4vw, 2.1rem); line-height: 1.2; margin: .5rem 0; }
h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; }
.headline { font-size: 1.15rem; color: var(--text); margin: .25rem 0 1rem; }
.controls { display: flex; flex-wrap: wrap; gap: 1rem 2rem; align-items: flex-end;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: .75rem 1rem; }
.controls fieldset { border: 0; margin: 0; padding: 0; }
.controls legend { font-size: .8rem; color: var(--muted); padding: 0; }
.controls label { margin-right: .75rem; white-space: nowrap; }
.year-control { flex: 1 1 260px; }
.year-control input[type="range"] { width: 100%; }
figure { margin: 0; }
#treemap, #totals-chart { width: 100%; overflow-x: auto; }
#treemap svg { display: block; max-width: 100%; height: auto; }
#treemap rect.leaf { stroke: none; }
#treemap text.group { font-size: 11px; fill: var(--text); paint-order: stroke;
  stroke: var(--bg); stroke-width: 3px; pointer-events: none; }
#legend { display: flex; flex-wrap: wrap; gap: .25rem 1rem; padding: 0; list-style: none; font-size: .85rem; }
#legend .swatch { display: inline-block; width: .8rem; height: .8rem; margin-right: .3rem; vertical-align: -1px; }
.note { color: var(--muted); font-size: .9rem; }
details.method { margin: .5rem 0 0; font-size: .9rem; color: var(--muted); }
details.method summary { cursor: pointer; }
table { border-collapse: collapse; width: 100%; font-size: .95rem; }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--line); }
th:not(:first-child), td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
.table-wrap { overflow-x: auto; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- [ ] **Step 2: Write `site/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Where San Diego's money goes</title>
  <meta name="description" content="Interactive look at City of San Diego spending: actuals for FY2011-23 and adopted budgets through FY2026.">
  <link rel="stylesheet" href="css/site.css">
</head>
<body>
  <header class="site-header">
    <nav>
      <strong>San Diego Spending</strong>
      <a href="index.html" aria-current="page">Where your dollar goes</a>
      <a href="methods.html">Data &amp; methods</a>
    </nav>
  </header>
  <main>
    <h1>Where San Diego's money goes</h1>
    <p id="headline" class="headline" aria-live="polite">Loading…</p>

    <form class="controls" aria-label="Chart controls" onsubmit="return false">
      <fieldset>
        <legend>Show</legend>
        <label><input type="radio" name="basis" value="actual" checked> Actual spending</label>
        <label><input type="radio" name="basis" value="adopted"> Adopted budget</label>
      </fieldset>
      <fieldset>
        <legend>Amounts</legend>
        <label><input type="radio" name="mode" value="total" checked> Total</label>
        <label><input type="radio" name="mode" value="perResident"> Per resident</label>
      </fieldset>
      <fieldset>
        <legend>Transfers</legend>
        <label><input type="checkbox" id="transfers"> Include transfers between city funds</label>
      </fieldset>
      <div class="year-control">
        <label for="fy">Fiscal year: <strong id="fy-label"></strong></label>
        <input type="range" id="fy" min="2011" max="2023" step="1" value="2023">
      </div>
    </form>

    <h2>Total by year</h2>
    <figure>
      <div id="totals-chart" role="img" aria-label="Bar chart of total city spending by fiscal year"></div>
      <figcaption class="note">Highlighted bar is the year selected above. Dollars are nominal (not adjusted for inflation).</figcaption>
      <details class="method">
        <summary>Method</summary>
        <p>Sum of all expense accounts (account numbers starting with 5) in the City's operating
          <em>actuals</em> or <em>adopted budget</em> files, by fiscal year (named for the year it ends).
          Source: City of San Diego Department of Finance via data.sandiego.gov.
          See <a href="methods.html">Data &amp; methods</a>.</p>
      </details>
    </figure>

    <h2>What it is spent on</h2>
    <figure>
      <div id="treemap"></div>
      <ul id="legend" aria-label="Colour key for types of spending"></ul>
      <p id="omitted-note" class="note"></p>
      <details class="method">
        <summary>Method</summary>
        <p>Each rectangle is one department group and one type of spending; its area is the amount.
          Colour shows the type of spending. "Transfers Out" (money moved between city funds) is hidden by
          default because it counts the same dollars twice. Per-resident figures divide by the City's
          estimated population for that year (<a href="methods.html">years where population is estimated are flagged</a>).</p>
      </details>
    </figure>

    <h2>Table view</h2>
    <div class="table-wrap">
      <table>
        <caption class="note">Department groups, largest first (same data as the chart above).</caption>
        <thead><tr><th scope="col">Department group</th><th scope="col" id="value-head">Spending</th><th scope="col">Share</th></tr></thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </main>
  <script type="module" src="js/main.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `site/js/main.js`**

```js
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { rowsFromColumns, availableYears, totalsByYear, buildHierarchy } from "./model.js";
import { parseHash, serializeHash } from "./state.js";
import { formatMoney, formatPerResident } from "./format.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const [spending, population] = await Promise.all([
  fetch("data/spending.json").then((r) => r.json()),
  fetch("data/population.json").then((r) => r.json()),
]);
const rows = rowsFromColumns(spending);
const years = availableYears(rows);
const popByFy = new Map(population.rows.map((p) => [p.fy, p]));
let state = parseHash(location.hash, years);

function update(patch) {
  state = parseHash(serializeHash({ ...state, ...patch }), years); // re-validates (e.g. year vs basis)
  history.replaceState(null, "", serializeHash(state));
  render();
}

function truncate(text, maxChars) {
  return text.length <= maxChars ? text : `${text.slice(0, Math.max(0, maxChars - 1))}…`;
}

function drawTotals(data) {
  const accent = css("--accent");
  const bar = css("--bar");
  const chart = Plot.plot({
    width: Math.max(300, $("totals-chart").clientWidth),
    height: 180,
    marginLeft: 56,
    x: { tickFormat: "d", label: null, tickSize: 0 },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [
      Plot.barY(data, {
        x: "fy", y: "total",
        fill: (d) => (d.fy === state.fy ? accent : bar),
        title: (d) => `FY${d.fy}: ${formatMoney(d.total)}`,
      }),
      Plot.ruleY([0]),
    ],
  });
  $("totals-chart").replaceChildren(chart);
}

function drawTreemap(tree, fmt) {
  const el = $("treemap");
  const width = Math.max(300, el.clientWidth);
  const height = Math.round(Math.min(640, Math.max(360, width * 0.7)));
  const h = d3.hierarchy(tree.root).sum((d) => d.value ?? 0).sort((a, b) => b.value - a.value);
  d3.treemap().size([width, height]).paddingInner(1).paddingOuter(2)
    .paddingTop((d) => (d.depth === 1 ? 16 : 2)).round(true)(h);
  const classes = [...new Set(h.leaves().map((d) => d.data.name))].sort();
  const color = d3.scaleOrdinal(d3.schemeTableau10.concat(d3.schemeSet3)).domain(classes);

  const svg = d3.create("svg")
    .attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height)
    .attr("role", "img")
    .attr("aria-label", "Treemap of city spending by department group and type of spending");
  svg.selectAll("rect.leaf").data(h.leaves()).join("rect")
    .attr("class", "leaf")
    .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
    .attr("width", (d) => d.x1 - d.x0).attr("height", (d) => d.y1 - d.y0)
    .attr("fill", (d) => color(d.data.name))
    .append("title").text((d) => `${d.parent.data.name} › ${d.data.name}: ${fmt(d.value)}`);
  svg.selectAll("text.group").data(h.descendants().filter((d) => d.depth === 1 && d.x1 - d.x0 > 50))
    .join("text").attr("class", "group")
    .attr("x", (d) => d.x0 + 3).attr("y", (d) => d.y0 + 12)
    .text((d) => truncate(d.data.name, Math.floor((d.x1 - d.x0) / 6.5)));
  el.replaceChildren(svg.node());

  $("legend").replaceChildren(...classes.map((name) => {
    const li = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = color(name);
    li.append(swatch, name);
    return li;
  }));
}

function drawTable(tree, fmt) {
  const groups = tree.root.children
    .map((g) => ({ name: g.name, value: d3.sum(g.children, (c) => c.value) }))
    .sort((a, b) => b.value - a.value);
  const sum = d3.sum(groups, (g) => g.value);
  $("table-body").replaceChildren(...groups.map((g) => {
    const tr = document.createElement("tr");
    for (const text of [g.name, fmt(g.value), `${((100 * g.value) / sum).toFixed(1)}%`]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  }));
}

function render() {
  const fyList = years[state.basis];
  const slider = $("fy");
  slider.min = fyList[0];
  slider.max = fyList.at(-1);
  slider.value = state.fy;
  $("fy-label").textContent = `FY${state.fy}`;
  document.querySelector(`input[name=basis][value=${state.basis}]`).checked = true;
  document.querySelector(`input[name=mode][value=${state.mode}]`).checked = true;
  $("transfers").checked = state.transfers;

  const pop = popByFy.get(state.fy);
  const perResident = state.mode === "perResident";
  const fmt = perResident ? formatPerResident : formatMoney;
  const tree = buildHierarchy(rows, {
    fy: state.fy, basis: state.basis, includeTransfers: state.transfers,
    divisor: perResident ? pop.population : 1,
  });
  const label = state.basis === "actual" ? "actual spending" : "adopted budget";
  const estimated = pop.source === "reported" ? "" : " (population estimated)";
  $("headline").textContent =
    `FY${state.fy} ${label}: ${formatMoney(tree.rawTotal)}, or ${formatPerResident(tree.rawTotal / pop.population)} per resident${estimated}.`;
  $("value-head").textContent = perResident ? "Per resident" : "Spending";
  $("omitted-note").textContent = tree.omitted.count
    ? `${tree.omitted.count} spending categories net to a credit (${formatMoney(tree.omitted.amount)}) and are left out of the picture; totals include them.`
    : "";

  drawTotals(totalsByYear(rows, { basis: state.basis, includeTransfers: state.transfers }));
  drawTreemap(tree, fmt);
  drawTable(tree, fmt);
}

document.querySelectorAll("input[name=basis]").forEach((el) =>
  el.addEventListener("change", () => update({ basis: el.value })));
document.querySelectorAll("input[name=mode]").forEach((el) =>
  el.addEventListener("change", () => update({ mode: el.value })));
$("transfers").addEventListener("change", (e) => update({ transfers: e.target.checked }));
$("fy").addEventListener("input", (e) => update({ fy: Number(e.target.value) }));
window.addEventListener("hashchange", () => { state = parseHash(location.hash, years); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("treemap").clientWidth;
new ResizeObserver(() => {
  const width = $("treemap").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("treemap"));

render();
```

- [ ] **Step 4: Write `site/methods.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Data &amp; methods · San Diego Spending</title>
  <link rel="stylesheet" href="css/site.css">
</head>
<body>
  <header class="site-header">
    <nav>
      <strong>San Diego Spending</strong>
      <a href="index.html">Where your dollar goes</a>
      <a href="methods.html" aria-current="page">Data &amp; methods</a>
    </nav>
  </header>
  <main>
    <h1>Data &amp; methods</h1>
    <p>Every number on this site comes from public files committed to the project's repository
      (<code>data/raw/</code>, with the source URL, retrieval date and checksum of each file in
      <code>data/raw/MANIFEST.csv</code>) and is rebuilt by scripts in <code>scripts/</code>.</p>

    <h2>Sources</h2>
    <ul>
      <li><strong>Operating actuals</strong> (FY2011-23) and <strong>operating budget</strong> (FY2011-26):
        City of San Diego Department of Finance, <a href="https://data.sandiego.gov/datasets/operating-actuals/">data.sandiego.gov</a>.
        Account and department reference tables come from the same portal.</li>
      <li><strong>Population</strong>: City of San Diego estimated population as reported in the California
        State Controller's Office local-government finance data
        (<a href="https://bythenumbers.sco.ca.gov/">bythenumbers.sco.ca.gov</a>).</li>
    </ul>

    <h2>How the numbers are built</h2>
    <ul>
      <li><strong>Spending</strong> is every row whose account number starts with 5 (expense accounts).
        Revenue rows (starting with 4) are not used on this page.</li>
      <li><strong>Fiscal years</strong> are named by the year they end: FY2023 is July 2022 to June 2023.</li>
      <li><strong>Dollars are nominal</strong>, not adjusted for inflation.</li>
      <li><strong>Adopted budget only.</strong> The budget file also contains "proposed" rows for FY2024 and
        FY2025; they are excluded because adding them to the adopted rows would count the budget twice.</li>
      <li><strong>FY2026 budget</strong> rows have no budget stage in the source file. They are treated as the
        adopted budget. There are no FY2024-26 actuals yet.</li>
      <li><strong>Transfers Out</strong> (money moved between city funds) is about 13% of FY2023 spending. It is
        hidden by default because it counts the same dollars twice; the checkbox adds it back.</li>
      <li><strong>Credits.</strong> A department and spending type that nets to a credit cannot be drawn in a
        treemap. It is left out of the picture, included in the totals, and listed under the chart.</li>
      <li><strong>Unclassified.</strong> Rows whose department or account is missing from the City's reference
        tables are kept and labelled "Unclassified". Rows with a blank account number cannot be identified as
        spending or revenue and are excluded; their totals are recorded in
        <code>data/processed/build_report.json</code>.</li>
      <li><strong>Population</strong> is missing from the source for a few years. Those years are
        interpolated, and years after the latest report use the latest value. Per-resident figures for them are
        marked "(population estimated)".</li>
    </ul>

    <h2>Checks that run on every build</h2>
    <ul>
      <li>Aggregating never changes a total.</li>
      <li>Adopted budget stays within 25% of actual spending for every year that has both.</li>
      <li>No year's total changes by more than 40% from the year before (this would catch double counting).</li>
    </ul>
    <p class="note">Margin estimates (spending compared with private-sector prices) and peer-city comparisons are
      not on the site yet.</p>
  </main>
</body>
</html>
```

- [ ] **Step 5: Serve locally and check the files load**

Run:
```bash
uv run python -m http.server 8765 --directory site >/dev/null 2>&1 &
sleep 1
for p in / /methods.html /css/site.css /js/main.js /data/spending.json /data/population.json; do
  curl -s -o /dev/null -w "$p %{http_code}\n" http://127.0.0.1:8765$p; done
kill %1
```
Expected: six lines, all `200`.

- [ ] **Step 6: Commit**

```bash
git add site
git commit -m "Add spending explorer page, styles and Data & methods page"
```

---

### Task 7: Browser smoke test, CI/Pages workflow and README

**Files:**
- Create: `tests/test_site_smoke.py`, `.github/workflows/pages.yml`, `README.md`

**Interfaces:**
- Consumes: DOM ids from Task 6.

- [ ] **Step 1: Write the smoke test**

`tests/test_site_smoke.py`:
```python
"""Loads the real site in Chromium. Needs network access (d3/Plot come from the jsDelivr CDN)
and `uv run playwright install chromium`."""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke
SITE = Path(__file__).resolve().parents[1] / "site"


@pytest.fixture(scope="module")
def site_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                             "--directory", str(SITE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()


def open_index(page, site_url, hash_=""):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/{hash_}")
    page.wait_for_selector("#treemap rect.leaf")
    return errors


def test_index_renders_chart_table_and_headline(page, site_url):
    errors = open_index(page, site_url)
    assert page.locator("#treemap rect.leaf").count() > 20
    assert page.locator("#table-body tr").count() > 10
    assert "FY2023" in page.locator("#headline").inner_text()
    assert "$" in page.locator("#headline").inner_text()
    assert errors == []


def test_every_figure_has_a_method_drawer(page, site_url):
    open_index(page, site_url)
    assert page.locator("figure").count() == page.locator("figure details.method").count() >= 2


def test_mode_toggle_updates_hash_and_table(page, site_url):
    open_index(page, site_url)
    before = page.locator("#value-head").inner_text()
    page.check("input[name=mode][value=perResident]")
    page.wait_for_function("location.hash.includes('mode=perResident')")
    assert page.locator("#value-head").inner_text() != before


def test_deep_link_restores_state(page, site_url):
    open_index(page, site_url, "#fy=2015&basis=actual&mode=total&transfers=1")
    assert page.input_value("#fy") == "2015"
    assert page.is_checked("#transfers")
    assert "FY2015" in page.locator("#headline").inner_text()


def test_garbage_hash_falls_back_without_errors(page, site_url):
    errors = open_index(page, site_url, "#fy=abc&basis=zzz&mode=%00")
    assert page.input_value("#fy") == "2023"
    assert errors == []


def test_year_slider_works_from_the_keyboard(page, site_url):
    open_index(page, site_url)
    page.focus("#fy")
    page.keyboard.press("ArrowLeft")
    page.wait_for_function("document.getElementById('fy').value === '2022'")
    assert "FY2022" in page.locator("#headline").inner_text()


def test_switching_to_adopted_budget_extends_the_years(page, site_url):
    open_index(page, site_url)
    page.check("input[name=basis][value=adopted]")
    page.wait_for_function("document.getElementById('fy').max === '2026'")


def test_no_horizontal_scroll_on_a_phone(page, site_url):
    page.set_viewport_size({"width": 390, "height": 800})
    open_index(page, site_url)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_methods_page(page, site_url):
    page.goto(f"{site_url}/methods.html")
    assert "methods" in page.locator("h1").inner_text().lower()
    assert "Transfers Out" in page.locator("main").inner_text()
```

- [ ] **Step 2: Install the browser and run the smoke tests**

Run: `uv run playwright install chromium && uv run pytest -m smoke -v`
Expected: 9 passed. A failure on `test_index_renders_chart_table_and_headline` that mentions a network or module error means the CDN is unreachable; fix connectivity before changing code. Any other failure is a real bug in Task 6: fix `main.js`/`index.html`, not the test, unless the test itself is wrong.

- [ ] **Step 3: Write the CI and deploy workflow**

`.github/workflows/pages.yml`:
```yaml
name: pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: uv sync
      - run: uv run pytest -m "not smoke"
      - run: npm test
  deploy:
    needs: test
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 4: Write `README.md`**

````markdown
# San Diego Spending

Interactive charts of City of San Diego spending, published with GitHub Pages from `site/`.
Goal: make public spending data legible, and later measure how much is spent above a private-sector
equivalent ("margin"). See `docs/superpowers/specs/` for the design.

## Reproduce everything
```bash
uv sync
uv run python scripts/fetch_sd_budget.py        # ~130 MB download -> data/raw/sandiego/*.csv.gz
uv run python scripts/fetch_sco_population.py   # -> data/raw/sco/
uv run python scripts/build_processed.py        # -> data/processed/, site/data/
uv run pytest -m "not smoke" && npm test        # unit + data checks
uv run playwright install chromium && uv run pytest -m smoke   # browser smoke test
uv run python -m http.server --directory site   # preview at http://localhost:8000
```
`data/raw/MANIFEST.csv` records the URL, retrieval date and sha256 of every raw file (hash of the
original bytes; files are stored gzip-compressed).

## Data sources
| Data | Source | Script |
|---|---|---|
| Operating actuals FY2011-23, operating budget FY2011-26, account and department reference tables | City of San Diego Dept. of Finance, data.sandiego.gov (files on seshat.datasd.org) | `fetch_sd_budget.py` |
| City population by year | State Controller's Office, bythenumbers.sco.ca.gov (dataset rrtv-rsj9) | `fetch_sco_population.py` |

## Data-quality notes
- Fiscal years are named by the year they end (FY2023 = July 2022 to June 2023). Dollars are nominal.
- The budget file contains `adopted` and `proposed` rows for FY2024-25; only adopted rows are used (summing both double-counts).
- FY2026 budget rows have a blank `budget_cycle` and are treated as adopted. No actuals exist after FY2023.
- Expense = account numbers starting with 5. 12 FY2026 budget rows have a blank account number and are excluded; their total is in `data/processed/build_report.json`.
- `Transfers Out` (~13% of FY2023 spending) is hidden by default in the UI because it moves money between city funds.
- The build fails if aggregation changes a total, if adopted budget differs from actuals by more than 25%, or if any year's total jumps more than 40%.
- SCO population is missing for 2006, 2010 and 2026; the build interpolates or carries forward and flags those years.
````

- [ ] **Step 5: Run the whole verification**

Run: `uv run pytest -m "not smoke" -q && npm test && uv run pytest -m smoke -q`
Expected: all three commands succeed (Python tests pass, 16 JS tests pass, 9 smoke tests pass).

- [ ] **Step 6: Commit**

```bash
git add tests/test_site_smoke.py .github README.md
git commit -m "Add browser smoke test, CI/Pages workflow and README"
```

- [ ] **Step 7: Ask the user before anything outward-facing**

Do NOT push. Tell the user the site is built and verified locally, and ask whether to create the GitHub repository, push `main`, and enable Pages (Settings, Pages, Source: GitHub Actions). Also ask whether to file the records request now (that part is theirs to send).
