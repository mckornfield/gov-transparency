# "Who Gets Paid" Vendor Payments Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the City of San Diego's yearly "Cumulative Amounts Paid to Vendors, $25,000 or more" PDFs (FY2022-FY2026) into a tidy table and ship a "Who gets paid" page: top-vendor leaderboard, concentration, vendor search with trend.

**Architecture:** A fetch script commits gzipped copies of five PDFs. `sd_spend.vendors` turns `pdftotext -layout` text into rows with strict validation, merges vendor-ID/spelling variants, and checks totals against the City's own spending. A build script writes `data/processed/vendor_payments.csv` and `site/data/vendors.json`; a new static page reads the JSON through a small pure-JS model.

**Tech Stack:** Python >=3.11 + pandas + `pdftotext` (poppler, only needed to re-run extraction); pure-JS modules tested with `node --test`; Observable Plot 0.6.16 from the existing CDN pin; Playwright smoke tests. Same repo conventions as the foundation plan.

**Spec:** `docs/superpowers/specs/2026-10-29-gov-transparency-design.md` (build-order step 3 and page 2, "Who gets paid"). Builds on `docs/superpowers/plans/2026-10-29-foundation-and-spending-page.md`, which is already merged.

## Global Constraints

- Python `>=3.11` with `uv`; raw originals committed gzip-compressed with a `MANIFEST.csv` row (url, retrieved date, sha256 of the original bytes).
- Front end is plain static HTML/JS in `site/`, no bundler, no npm dependencies; Plot is loaded from `https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm`.
- Phone layout works (no horizontal scroll at 390px); light and dark mode; every chart has a keyboard-reachable data table; page state is deep-linkable via the URL hash; every figure has a `details.method` drawer.
- Dollars are nominal; fiscal year is named by its END year.
- Never present vendor payments as total spending: always state the coverage percentage and that payments under $25,000 per vendor are not published.
- The City publishes no purpose or category for these payments: do not label any vendor as waste, and say on the page that a large payment can be a pass-through (e.g. to the pension system or a regional water wholesaler).
- Extraction must fail loudly (raise `ExtractionError`) on any unrecognised line, page-count mismatch, duplicate vendor ID, or amount under $25,000; never skip a line silently.
- Every commit message ends with these two trailer lines (after a blank line):
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01TciBBGx2gbU5jx95hjH4EJ`
- Do not `git push` without the user's go-ahead.

## Facts about the real data (verified 2026-10-29; the tests below encode them)

- Reports (all under `https://www.sandiego.gov/sites/default/files/`): FY2022 `2024-10/fy2022-cumulative-amounts-paid-1.pdf` (38 pages), FY2023 `2024-10/fy2023-cumulative-amounts-paid-2.pdf` (42), FY2024 `2024-10/fy2024-cumulative-amounts-paid.pdf` (46), FY2025 `2025-07/cumulative-paid-fy25.pdf` (46), FY2026 `2026-04/cumulative-paid-fy26.pdf` (43; header says "July 2025 to June 2026"). A different file, `2025-10/cumulative-paid-fy26.pdf`, covers only July-September 2025 and must NOT be used.
- `pdftotext -layout` output: each page starts with three header lines (`City of San Diego`, `Cumulative Amounts Paid to Vendors - $25,000 or more` or `- $ 25,000 or more`, `Fiscal Year 20NN (...)`), a column-header line starting `Vendor` and containing `Vendor Name`, and ends with `Page n of N`. FY2023 has a blank line between rows.
- Layout drift between years: vendor ID is `10007317` or zero-padded `0010007317`; amounts are `841,366,616` (FY22, no cents), `$276,824,244.78` (FY23, FY24) or `284,136,895.86` (FY25, FY26); column spacing varies.
- One regex parses every row in all files: FY22 1,532 rows ($3,091.8M), FY23 1,492 ($2,329.9M), FY24 1,587 ($2,630.5M), FY25 1,626 ($3,012.8M), FY26 1,530 ($3,031.1M). No duplicate vendor IDs, no negative amounts, minimum amount 25,000. The PDFs print NO totals, so row sums cannot be reconciled to a stated total.
- Top payees: FY22 SDCERS $841.4M then San Diego County Water Authority $260.2M; FY25 San Diego County Water Authority $284.1M, US Bank National Association $214.2M, Kiewit Infrastructure West Co $88.1M.
- Identity: in FY25 four names appear under two vendor IDs each, e.g. `San Diego Gas and Electric` (10019640, $63.4M) and `San Diego Gas And Electric` (10010990, $15.0M); 213 vendor IDs appear with more than one spelling across years (e.g. `CGI Technologies and Solutions Inc` vs `CGI Technologies & Solutions Inc`).
- Sanity ratio (vendor total / City expense total from `data/processed/spending.csv`): FY22 about 0.86, FY23 about 0.58, FY24-26 about 0.58-0.62 against adopted budgets.

## Review Focus

- The same company under several vendor IDs or spellings must be merged (case, punctuation, `&` vs `and`), with all IDs kept, so a leaderboard never splits one payee into two rows (Task 3).
- Payments under $25,000 per vendor are unpublished: coverage % must be shown next to every total and never described as total spending (Task 6 smoke test).
- The PDFs print no totals: a whole missing page must still be caught, by the page-count check and by the vendor-total-vs-City-spending band (Tasks 2 and 3).
- Layout drift between years (zero-padded IDs, `$` and cents, blank rows, wider column gaps, a wrapped vendor name) must parse correctly or fail loudly, never produce a wrong amount (Task 2).
- Search text containing regex characters (`(`, `.*`, `\`) or only spaces must not throw and must match literally; no match shows a message (Task 5, Task 6).
- A very large payment to a pass-through payee (pension system, water wholesaler, bond trustee) must not be presented as waste: the page says why (Task 6).

## File Structure

```
scripts/fetch_sd_vendor_payments.py   5 PDFs -> data/raw/sandiego/vendor_payments_fy20NN.pdf.gz
scripts/build_vendors.py              raw PDFs -> data/processed/vendor_payments.csv + site/data/vendors.json
src/sd_spend/vendors.py               parse/validate PDF text, merge identities, coverage checks, pdf_to_text
src/sd_spend/export.py                (modify) add vendors_payload
site/vendors.html                     Who gets paid
site/js/vendors-model.js              pure functions: ranking, concentration, search, hash state (+ .test.js)
site/js/vendors.js                    DOM wiring + Plot
site/js/format.js                     (modify) add truncate (+ test)
site/index.html, site/methods.html    (modify) nav link, vendor section on methods
site/css/site.css                     (modify) search/table-button styles
tests/test_manifest.py                (modify) require the vendor PDFs
tests/test_vendors.py, test_real_vendors.py, test_export.py (modify), test_site_smoke.py (modify)
README.md                             (modify) sources, poppler, commands
```

---

### Task 1: Fetch and commit the vendor PDFs

**Files:**
- Create: `scripts/fetch_sd_vendor_payments.py`
- Modify: `tests/test_manifest.py` (REQUIRED set)
- Create (by running): `data/raw/sandiego/vendor_payments_fy2022.pdf.gz` ... `fy2026.pdf.gz`, and five new `MANIFEST.csv` rows

**Interfaces:**
- Consumes: `sd_spend.io.get_with_retry`, `save_raw`.
- Produces: raw files `data/raw/sandiego/vendor_payments_fy{2022..2026}.pdf.gz`.

- [ ] **Step 1: Write the failing test change**

In `tests/test_manifest.py`, replace the `REQUIRED` set with:
```python
REQUIRED = {
    "sandiego/actuals_operating.csv.gz",
    "sandiego/budget_operating.csv.gz",
    "sandiego/accounts.csv.gz",
    "sandiego/depts.csv.gz",
    "sco/san_diego_population.csv.gz",
    *{f"sandiego/vendor_payments_fy{fy}.pdf.gz" for fy in range(2022, 2027)},
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_manifest.py -q`
Expected: FAIL in `test_required_sources_are_in_manifest` (vendor PDF paths missing).

- [ ] **Step 3: Write the fetch script**

`scripts/fetch_sd_vendor_payments.py`:
```python
"""City of San Diego 'Cumulative Amounts Paid to Vendors - $25,000 or more', one PDF per fiscal year
(sandiego.gov; the City publishes no CSV of these).

FY2026 is the report covering July 2025 to June 2026. A separate file in the same series
(2025-10/cumulative-paid-fy26.pdf) covers only July-September 2025 and is deliberately not used.
"""
from sd_spend.io import get_with_retry, save_raw

BASE = "https://www.sandiego.gov/sites/default/files"
REPORTS = {
    2022: "2024-10/fy2022-cumulative-amounts-paid-1.pdf",
    2023: "2024-10/fy2023-cumulative-amounts-paid-2.pdf",
    2024: "2024-10/fy2024-cumulative-amounts-paid.pdf",
    2025: "2025-07/cumulative-paid-fy25.pdf",
    2026: "2026-04/cumulative-paid-fy26.pdf",
}


def main() -> None:
    for fy, path in REPORTS.items():
        url = f"{BASE}/{path}"
        print("fetching", url, flush=True)
        save_raw(get_with_retry(url).content, f"sandiego/vendor_payments_fy{fy}.pdf", url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run it and the tests**

Run: `uv run python scripts/fetch_sd_vendor_payments.py && uv run pytest tests/test_manifest.py -q && du -sh data/raw`
Expected: five "fetching" lines, 3 manifest tests pass, `data/raw` grows by under 5 MB. If any new file exceeds 50 MB, stop and ask.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_sd_vendor_payments.py data/raw tests/test_manifest.py
git commit -m "Fetch and commit yearly vendor-payment PDFs (FY2022-FY2026)"
```

---

### Task 2: Parse and validate one report's text

**Files:**
- Create: `src/sd_spend/vendors.py`
- Test: `tests/test_vendors.py`

**Interfaces:**
- Produces (in `sd_spend.vendors`):
  - `class ExtractionError(AssertionError)`
  - `MIN_AMOUNT = 25000`
  - `parse_report(text: str) -> tuple[int, pd.DataFrame, dict]`; the frame has columns `vendor_id` (leading zeros stripped, str), `vendor_name` (whitespace collapsed), `amount` (float); the dict has `unmatched: list[str]`, `pages_declared: int`, `pages_seen: int`
  - `parse_and_validate(text: str) -> tuple[int, pd.DataFrame]` (raises `ExtractionError` on any unmatched line, page mismatch, zero rows, duplicate vendor id, or amount below `MIN_AMOUNT`)
  - `pdf_to_text(gz_path) -> str` (gunzips to a temp file, runs `pdftotext -layout`; raises `ExtractionError` if `pdftotext` is not installed)

- [ ] **Step 1: Write the failing tests**

`tests/test_vendors.py`:
```python
import pytest

from sd_spend import vendors as v

FY22 = """City of San Diego
Cumulative Amounts Paid to Vendors - $25,000 or more
Fiscal Year 2022 (July 2021 to June 2022)



Vendor      Vendor Name                                   Amount
 10020828   SDCERS                                         841,366,616
 10007317   San Diego County Water Authority               260,209,475
Page 1 of 1
"""

FY23 = """City of San Diego
Cumulative Amounts Paid to Vendors - $25,000 or more
Fiscal Year 2023 (July 2022 to June 2023)

     Vendor          Vendor Name                                         Payment Amount

         0010007317 San Diego County Water Authority                        $276,824,244.78

         0010005357 US Bank National Association                            $241,794,510.35
Page 1 of 1
"""

FY24 = """City of San Diego
Cumulative Amounts Paid to Vendors - $ 25,000 or more
Fiscal Year 2024 (July 2023 to June 2024 Only)

Vendor         Vendor Name                                       Payment Amount

   0010007317 San Diego County Water Authority                      $252,567,610.88
Page 1 of 2
City of San Diego
Cumulative Amounts Paid to Vendors - $ 25,000 or more
Fiscal Year 2024 (July 2023 to June 2024 Only)

Vendor         Vendor Name                                       Payment Amount
   0010099999 Acme 2000 Inc                                          $25,000.00
Page 2 of 2
"""


def test_parses_fy22_layout_without_cents():
    fy, df, info = v.parse_report(FY22)
    assert fy == 2022
    assert list(df["vendor_id"]) == ["10020828", "10007317"]
    assert list(df["vendor_name"]) == ["SDCERS", "San Diego County Water Authority"]
    assert list(df["amount"]) == [841366616.0, 260209475.0]
    assert info == {"unmatched": [], "pages_declared": 1, "pages_seen": 1}


def test_parses_fy23_layout_with_padded_ids_dollar_sign_cents_and_blank_rows():
    fy, df, _ = v.parse_report(FY23)
    assert fy == 2023
    assert list(df["vendor_id"]) == ["10007317", "10005357"]
    assert list(df["amount"]) == [276824244.78, 241794510.35]


def test_parses_fy24_two_pages_and_names_ending_in_digits():
    fy, df = v.parse_and_validate(FY24)
    assert fy == 2024
    assert list(df["vendor_name"]) == ["San Diego County Water Authority", "Acme 2000 Inc"]
    assert df["amount"].min() == 25000.0


def test_an_unrecognised_line_fails_loudly():
    wrapped = FY22.replace("Page 1 of 1", "   Construction Inc\nPage 1 of 1")
    with pytest.raises(v.ExtractionError, match="Construction Inc"):
        v.parse_and_validate(wrapped)


def test_a_missing_page_fails_loudly():
    missing = FY24.replace("Page 2 of 2", "")
    with pytest.raises(v.ExtractionError, match="pages"):
        v.parse_and_validate(missing)


def test_duplicate_vendor_ids_fail_loudly():
    dup = FY22.replace("10007317   San Diego County Water Authority", "10020828   Some Other Name")
    with pytest.raises(v.ExtractionError, match="duplicate"):
        v.parse_and_validate(dup)


def test_amounts_below_the_published_threshold_fail_loudly():
    small = FY22.replace("841,366,616", "841")
    with pytest.raises(v.ExtractionError, match="25,000"):
        v.parse_and_validate(small)


def test_empty_report_fails_loudly():
    with pytest.raises(v.ExtractionError, match="no rows"):
        v.parse_and_validate("City of San Diego\nFiscal Year 2024 (x)\nPage 1 of 1\n")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_vendors.py -q`
Expected: FAIL (`ImportError: cannot import name 'vendors'`).

- [ ] **Step 3: Implement `src/sd_spend/vendors.py` (parsing part)**

```python
"""Turn the City's yearly 'Cumulative Amounts Paid to Vendors' PDFs into tidy rows.

The PDFs print no totals, so correctness rests on strictness: any line that is not a header, a page
footer or a payment row raises ExtractionError instead of being skipped.
"""
import gzip
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

MIN_AMOUNT = 25000


class ExtractionError(AssertionError):
    pass


ROW = re.compile(r"^\s*(\d{8,10})\s+(.+?)\s+(-?\$?\s?[\d,]+(?:\.\d{1,2})?)\s*$")
HEADER = re.compile(r"^(City of San Diego|Cumulative Amounts Paid|Fiscal Year \d{4}|Vendor\s+Vendor Name)")
FISCAL_YEAR = re.compile(r"Fiscal Year (\d{4})")
PAGE = re.compile(r"^Page \d+ of (\d+)$")


def parse_report(text: str) -> tuple[int, pd.DataFrame, dict]:
    match = FISCAL_YEAR.search(text)
    if match is None:
        raise ExtractionError("no 'Fiscal Year' line found")
    rows, unmatched, page_totals = [], [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or HEADER.match(stripped):
            continue
        page = PAGE.match(stripped)
        if page:
            page_totals.append(int(page.group(1)))
            continue
        row = ROW.match(line)
        if row:
            rows.append((row.group(1).lstrip("0"), " ".join(row.group(2).split()),
                         float(re.sub(r"[^\d.\-]", "", row.group(3)))))
        else:
            unmatched.append(stripped)
    frame = pd.DataFrame(rows, columns=["vendor_id", "vendor_name", "amount"])
    info = {"unmatched": unmatched, "pages_declared": max(page_totals, default=0),
            "pages_seen": len(page_totals)}
    return int(match.group(1)), frame, info


def parse_and_validate(text: str) -> tuple[int, pd.DataFrame]:
    fy, df, info = parse_report(text)
    if info["unmatched"]:
        raise ExtractionError(f"FY{fy}: {len(info['unmatched'])} unrecognised lines, first: {info['unmatched'][:3]}")
    if info["pages_seen"] == 0 or info["pages_seen"] != info["pages_declared"]:
        raise ExtractionError(f"FY{fy}: saw {info['pages_seen']} page footers but the report declares "
                              f"{info['pages_declared']} pages")
    if df.empty:
        raise ExtractionError(f"FY{fy}: no rows parsed")
    dup = df.loc[df["vendor_id"].duplicated(), "vendor_id"].tolist()
    if dup:
        raise ExtractionError(f"FY{fy}: duplicate vendor ids {dup[:5]}")
    small = df[df["amount"] < MIN_AMOUNT]
    if len(small):
        raise ExtractionError(f"FY{fy}: {len(small)} amounts below $25,000 (the report's threshold), "
                              f"first: {small.iloc[0].to_dict()}")
    return fy, df


def pdf_to_text(gz_path) -> str:
    """Text of a gzipped PDF via `pdftotext -layout` (poppler). The PDF is untrusted input: it is only
    ever passed to pdftotext as a file argument."""
    if shutil.which("pdftotext") is None:
        raise ExtractionError("pdftotext is required: `brew install poppler` or `apt install poppler-utils`")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "report.pdf"
        pdf.write_bytes(gzip.decompress(Path(gz_path).read_bytes()))
        result = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                                capture_output=True, text=True)
    return result.stdout
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_vendors.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sd_spend/vendors.py tests/test_vendors.py
git commit -m "Parse and strictly validate vendor-payment report text"
```

---

### Task 3: Merge vendor identities and sanity-check coverage

**Files:**
- Modify: `src/sd_spend/vendors.py`
- Test: `tests/test_vendors.py` (append)

**Interfaces:**
- Consumes: `parse_and_validate` frames (`vendor_id, vendor_name, amount`).
- Produces (in `sd_spend.vendors`):
  - `name_key(name: str) -> str` (lowercase, `&` -> `and`, only `[a-z0-9]` kept)
  - `combine(reports: dict[int, pd.DataFrame]) -> pd.DataFrame` with columns `fy, vendor_key, vendor_name, vendor_ids, amount`; one row per (fy, vendor_key); `vendor_ids` is the sorted unique ids joined by `"; "`; `vendor_name` is the spelling from the latest year the vendor appears (largest payment that year); sorted by fy ascending then amount descending
  - `coverage(vendor_totals: pd.Series, spending: pd.DataFrame) -> dict[int, dict]`: `vendor_totals` is indexed by fy; `spending` has `basis, fy, amount`; returns `{fy: {"vendors_total": float, "reference_total": float, "reference_basis": "actual"|"adopted"}}`, preferring actuals; raises `ExtractionError` if a year has neither
  - `check_coverage(cov: dict, low: float = 0.4, high: float = 1.1) -> None` raises `ExtractionError` naming each year whose ratio is outside the band

- [ ] **Step 1: Write the failing tests (append to `tests/test_vendors.py`)**

```python
import pandas as pd


def report(*rows):
    return pd.DataFrame(rows, columns=["vendor_id", "vendor_name", "amount"])


def test_name_key_ignores_case_punctuation_and_ampersand():
    assert v.name_key("CGI Technologies & Solutions Inc.") == v.name_key("cgi technologies and solutions inc")
    assert v.name_key("San Diego Gas And Electric") == v.name_key("San Diego Gas and Electric")


def test_combine_merges_ids_and_spellings_and_uses_the_latest_name():
    out = v.combine({
        2024: report(("A", "San Diego Gas and Electric", 60.0), ("B", "San Diego Gas And Electric", 15.0),
                     ("C", "CGI Technologies & Solutions", 5.0)),
        2025: report(("D", "CGI Technologies and Solutions", 6.0)),
    })
    sdge = out[out["vendor_key"] == v.name_key("San Diego Gas and Electric")]
    assert list(sdge["amount"]) == [75.0]
    assert list(sdge["vendor_ids"]) == ["A; B"]
    assert list(sdge["vendor_name"]) == ["San Diego Gas and Electric"]
    cgi = out[out["vendor_key"] == v.name_key("CGI Technologies and Solutions")]
    assert list(cgi["fy"]) == [2024, 2025]
    assert set(cgi["vendor_name"]) == {"CGI Technologies and Solutions"}
    assert list(out["fy"]) == sorted(out["fy"])
    assert list(out[out["fy"] == 2024]["amount"]) == [75.0, 5.0]


def test_combine_never_merges_vendors_whose_names_have_no_letters_or_digits():
    out = v.combine({2024: report(("1001", "---", 30000.0), ("1002", "...", 40000.0))})
    assert len(out) == 2


def spending(rows):
    return pd.DataFrame(rows, columns=["basis", "fy", "amount"])


def test_coverage_prefers_actuals_and_falls_back_to_adopted():
    cov = v.coverage(pd.Series({2023: 60.0, 2026: 30.0}),
                     spending([("actual", 2023, 100.0), ("adopted", 2023, 90.0), ("adopted", 2026, 50.0)]))
    assert cov[2023] == {"vendors_total": 60.0, "reference_total": 100.0, "reference_basis": "actual"}
    assert cov[2026] == {"vendors_total": 30.0, "reference_total": 50.0, "reference_basis": "adopted"}


def test_coverage_requires_a_reference_year():
    with pytest.raises(v.ExtractionError, match="2030"):
        v.coverage(pd.Series({2030: 1.0}), spending([("actual", 2023, 100.0)]))


def test_check_coverage_catches_a_lost_chunk_of_pages_and_double_counting():
    ok = {2023: {"vendors_total": 60.0, "reference_total": 100.0, "reference_basis": "actual"}}
    v.check_coverage(ok)
    for paid in (10.0, 150.0):
        bad = {2023: {"vendors_total": paid, "reference_total": 100.0, "reference_basis": "actual"}}
        with pytest.raises(v.ExtractionError, match="2023"):
            v.check_coverage(bad)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_vendors.py -q`
Expected: the new tests FAIL with `AttributeError: module 'sd_spend.vendors' has no attribute 'name_key'`.

- [ ] **Step 3: Implement (append to `src/sd_spend/vendors.py`)**

```python
def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))


def combine(reports: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """One row per (fiscal year, vendor). Vendors are the same when their names match ignoring case,
    punctuation and '&' vs 'and' (the City sometimes lists one company under several vendor ids)."""
    rows = pd.concat([df.assign(fy=fy) for fy, df in reports.items()], ignore_index=True)
    key = rows["vendor_name"].map(name_key)
    rows["vendor_key"] = key.where(key != "", "id" + rows["vendor_id"])
    latest_name = (rows.sort_values(["fy", "amount"]).groupby("vendor_key").tail(1)
                   .set_index("vendor_key")["vendor_name"])
    grouped = rows.groupby(["fy", "vendor_key"], as_index=False).agg(
        vendor_ids=("vendor_id", lambda s: "; ".join(sorted(set(s)))), amount=("amount", "sum"))
    grouped["vendor_name"] = grouped["vendor_key"].map(latest_name)
    return (grouped[["fy", "vendor_key", "vendor_name", "vendor_ids", "amount"]]
            .sort_values(["fy", "amount"], ascending=[True, False]).reset_index(drop=True))


def coverage(vendor_totals: pd.Series, spending: pd.DataFrame) -> dict[int, dict]:
    totals = spending.groupby(["basis", "fy"])["amount"].sum()
    out = {}
    for fy, paid in vendor_totals.items():
        basis = next((b for b in ("actual", "adopted") if (b, fy) in totals.index), None)
        if basis is None:
            raise ExtractionError(f"no City spending total for FY{fy} to compare vendor payments against")
        out[int(fy)] = {"vendors_total": float(paid), "reference_total": float(totals[(basis, fy)]),
                        "reference_basis": basis}
    return out


def check_coverage(cov: dict, low: float = 0.4, high: float = 1.1) -> None:
    """Vendor payments cannot be reconciled to a printed total (the PDFs have none), so require that
    they land in a plausible share of the City's own spending. A dropped page or a double count falls
    outside the band."""
    bad = {fy: round(c["vendors_total"] / c["reference_total"], 2) for fy, c in cov.items()
           if not low <= c["vendors_total"] / c["reference_total"] <= high}
    if bad:
        raise ExtractionError(f"vendor payments are outside {low:.0%}-{high:.0%} of City spending: {bad}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_vendors.py -q`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sd_spend/vendors.py tests/test_vendors.py
git commit -m "Merge vendor identities and check vendor totals against City spending"
```

---

### Task 4: Build the vendor tables and site JSON from the real PDFs

**Files:**
- Modify: `src/sd_spend/export.py`
- Create: `scripts/build_vendors.py`
- Create (by running): `data/processed/vendor_payments.csv`, `site/data/vendors.json`
- Test: `tests/test_export.py` (append), `tests/test_real_vendors.py`

**Interfaces:**
- Consumes: `vendors.pdf_to_text`, `parse_and_validate`, `combine`, `coverage`, `check_coverage`; `data/processed/spending.csv` (columns include `basis, fy, amount`).
- Produces: `export.vendors_payload(vendors: DataFrame, cov: dict) -> dict` shaped
  `{"years": [2022, ...], "coverage": {"2022": {"vendors_total": int, "reference_total": int, "reference_basis": str}}, "vendors": [{"name": str, "ids": str, "amounts": {"2022": int, ...}}]}`
  with vendors sorted by total across years descending (ties by name) and amounts in whole dollars; `ids` is the union of that vendor's ids across years joined by `"; "`. File `site/data/vendors.json` has this shape; `data/processed/vendor_payments.csv` has columns `fy, vendor_key, vendor_name, vendor_ids, amount`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_export.py`:
```python
def test_vendors_payload_shapes_years_coverage_and_sorted_vendors():
    vendors = pd.DataFrame([
        (2024, "a", "Alpha Inc", "1; 2", 100.4),
        (2025, "a", "Alpha Inc", "1; 3", 50.4),
        (2024, "b", "Beta LLC", "9", 500.0),
    ], columns=["fy", "vendor_key", "vendor_name", "vendor_ids", "amount"])
    cov = {2024: {"vendors_total": 600.4, "reference_total": 1000.0, "reference_basis": "actual"},
           2025: {"vendors_total": 50.4, "reference_total": 90.0, "reference_basis": "adopted"}}
    payload = export.vendors_payload(vendors, cov)
    assert payload["years"] == [2024, 2025]
    assert payload["coverage"]["2025"] == {"vendors_total": 50, "reference_total": 90, "reference_basis": "adopted"}
    assert [v["name"] for v in payload["vendors"]] == ["Beta LLC", "Alpha Inc"]  # 500 > 150.8
    assert payload["vendors"][1] == {"name": "Alpha Inc", "ids": "1; 2; 3", "amounts": {"2024": 100, "2025": 50}}
```

`tests/test_real_vendors.py`:
```python
"""Checks against the committed processed vendor data and the raw PDFs."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sd_spend import vendors as v

ROOT = Path(__file__).resolve().parents[1]
table = pd.read_csv(ROOT / "data/processed/vendor_payments.csv", dtype={"vendor_ids": str})
site = json.loads((ROOT / "site/data/vendors.json").read_text())


def test_every_year_is_present_with_plausible_row_counts():
    counts = table.groupby("fy").size()
    assert list(counts.index) == [2022, 2023, 2024, 2025, 2026]
    assert counts.loc[2025] <= 1626 and counts.loc[2025] >= 1600  # 1,626 PDF rows, a few merged
    assert counts.loc[2022] >= 1500


def test_known_top_payees():
    top25 = table[table["fy"] == 2025].nlargest(1, "amount").iloc[0]
    assert top25["vendor_name"] == "San Diego County Water Authority"
    assert abs(top25["amount"] - 284_136_895.86) < 1
    top22 = table[table["fy"] == 2022].nlargest(1, "amount").iloc[0]
    assert "SDCERS" in top22["vendor_name"]


def test_one_company_under_two_vendor_ids_is_one_row():
    sdge = table[(table["fy"] == 2025) & (table["vendor_key"] == v.name_key("San Diego Gas and Electric"))]
    assert len(sdge) == 1
    assert "10019640" in sdge.iloc[0]["vendor_ids"] and "10010990" in sdge.iloc[0]["vendor_ids"]
    assert 78e6 < sdge.iloc[0]["amount"] < 79e6


def test_coverage_is_in_the_plausible_band_for_every_year():
    cov = {int(fy): c for fy, c in site["coverage"].items()}
    v.check_coverage(cov)
    assert sorted(cov) == [2022, 2023, 2024, 2025, 2026]


def test_site_json_matches_the_csv():
    assert site["years"] == [2022, 2023, 2024, 2025, 2026]
    for fy in site["years"]:
        json_total = sum(x["amounts"].get(str(fy), 0) for x in site["vendors"])
        csv_total = table.loc[table["fy"] == fy, "amount"].sum()
        assert abs(json_total - csv_total) <= 0.5 * len(site["vendors"]) + 1, fy


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
def test_re_extracting_a_raw_pdf_reproduces_the_processed_total():
    fy, df = v.parse_and_validate(v.pdf_to_text(ROOT / "data/raw/sandiego/vendor_payments_fy2025.pdf.gz"))
    assert fy == 2025
    assert abs(df["amount"].sum() - table.loc[table["fy"] == 2025, "amount"].sum()) < 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_export.py tests/test_real_vendors.py -q`
Expected: FAIL (`AttributeError ... vendors_payload`; `test_real_vendors.py` errors at collection because `vendor_payments.csv` does not exist).

- [ ] **Step 3: Implement `vendors_payload` (append to `src/sd_spend/export.py`)**

```python
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
```

- [ ] **Step 4: Write `scripts/build_vendors.py`**

```python
"""Raw vendor-payment PDFs -> data/processed/vendor_payments.csv and site/data/vendors.json.

Needs poppler's `pdftotext` (brew install poppler / apt install poppler-utils). Fails
(ExtractionError) rather than writing numbers that do not look right; do not loosen the checks in
sd_spend.vendors to make it pass, investigate the PDFs and tell the user.
"""
import json

import pandas as pd

from sd_spend import export, vendors
from sd_spend.io import RAW, ROOT

YEARS = range(2022, 2027)
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"


def main() -> None:
    reports = {}
    for fy in YEARS:
        got_fy, df = vendors.parse_and_validate(
            vendors.pdf_to_text(RAW / "sandiego" / f"vendor_payments_fy{fy}.pdf.gz"))
        if got_fy != fy:
            raise vendors.ExtractionError(f"vendor_payments_fy{fy}.pdf.gz is a report for FY{got_fy}")
        reports[fy] = df
        print(f"FY{fy}: {len(df):>5} rows  ${df['amount'].sum() / 1e6:>8,.1f}M")
    table = vendors.combine(reports)
    spending = pd.read_csv(PROCESSED / "spending.csv")
    cov = vendors.coverage(table.groupby("fy")["amount"].sum(), spending)
    vendors.check_coverage(cov)
    table.to_csv(PROCESSED / "vendor_payments.csv", index=False)
    (SITE_DATA / "vendors.json").write_text(
        json.dumps(export.vendors_payload(table, cov), separators=(",", ":")) + "\n")
    for fy, c in cov.items():
        print(f"FY{fy}: vendor payments are {c['vendors_total'] / c['reference_total']:.0%} of {c['reference_basis']} spending")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the build and the tests**

Run: `uv run python scripts/build_vendors.py && uv run pytest -q`
Expected: five `FY20NN: ... rows` lines matching the Facts section (1,532 / 1,492 / 1,587 / 1,626 / 1,530 rows) and five coverage lines between 58% and 86%; all tests pass. If an `ExtractionError` fires, stop, do not loosen checks, and report the output.

- [ ] **Step 6: Check output size and commit**

Run: `ls -la site/data/vendors.json data/processed/vendor_payments.csv`
Expected: `vendors.json` under about 1.5 MB.

```bash
git add src/sd_spend/export.py scripts/build_vendors.py data/processed site/data tests/test_export.py tests/test_real_vendors.py
git commit -m "Extract vendor payments from the PDFs into a tidy table and site JSON"
```

---

### Task 5: Pure JS model for the vendors page

**Files:**
- Create: `site/js/vendors-model.js`
- Modify: `site/js/format.js` (add `truncate`)
- Test: `site/js/vendors-model.test.js`, `site/js/format.test.js` (append)

**Interfaces:**
- Produces:
  - `format.js`: `truncate(text: string, maxChars: number): string` (appends `…` when cut; never returns more than `maxChars` characters; `maxChars < 1` returns `""`)
  - `vendors-model.js`: `topVendors(vendors, fy, n = 25) -> {name, ids, amount}[]` (only vendors with an amount in `fy`, largest first); `concentration(vendors, fy, n = 10) -> {count, total, topTotal, share}` (share of the listed total; `0` when empty); `searchVendors(vendors, query, fy, limit = 50) -> vendor[]` (case-insensitive, whitespace-normalised LITERAL substring match on the name; empty or whitespace-only query returns `[]`; sorted by the amount in `fy` descending, then total across years descending, then name); `parseVendorHash(hash, years) -> {fy, q}` (invalid or missing `fy` -> latest year; `q` trimmed, at most 80 characters); `serializeVendorHash({fy, q}) -> string` (`#fy=2025&q=water%20authority`; omits `q` when empty)
  - A vendor is `{name: string, ids: string, amounts: {[fy: string]: number}}` (the shape in `site/data/vendors.json`).

- [ ] **Step 1: Write the failing tests**

Append to `site/js/format.test.js` (and add `truncate` to its import line: `import { formatMoney, formatPerResident, truncate } from "./format.js";`):
```js
test("truncate cuts with an ellipsis and respects the limit", () => {
  assert.equal(truncate("Police", 10), "Police");
  assert.equal(truncate("Department of Information Technology", 12), "Department …");
  assert.equal(truncate("abcdef", 3), "ab…");
  assert.equal(truncate("abc", 0), "");
});
```

`site/js/vendors-model.test.js`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { topVendors, concentration, searchVendors, parseVendorHash, serializeVendorHash } from "./vendors-model.js";

const vendors = [
  { name: "Water Authority", ids: "1", amounts: { 2024: 500, 2025: 300 } },
  { name: "Acme (West) Inc", ids: "2", amounts: { 2024: 100 } },
  { name: "Beta Construction", ids: "3", amounts: { 2025: 200 } },
  { name: "Gamma Water Works", ids: "4", amounts: { 2025: 50, 2024: 60 } },
];

test("topVendors lists only vendors paid that year, largest first", () => {
  assert.deepEqual(topVendors(vendors, 2025, 2), [
    { name: "Water Authority", ids: "1", amount: 300 }, { name: "Beta Construction", ids: "3", amount: 200 }]);
  assert.deepEqual(topVendors(vendors, 2024).map((v) => v.name), ["Water Authority", "Acme (West) Inc", "Gamma Water Works"]);
  assert.deepEqual(topVendors(vendors, 1999), []);
});

test("concentration reports the share of the listed total held by the top n", () => {
  assert.deepEqual(concentration(vendors, 2025, 1), { count: 3, total: 550, topTotal: 300, share: 300 / 550 });
  assert.deepEqual(concentration(vendors, 1999), { count: 0, total: 0, topTotal: 0, share: 0 });
});

test("searchVendors matches names literally, case-insensitively, and ranks by the selected year", () => {
  assert.deepEqual(searchVendors(vendors, "water", 2025).map((v) => v.name), ["Water Authority", "Gamma Water Works"]);
  assert.deepEqual(searchVendors(vendors, "  WATER   works ", 2025).map((v) => v.name), ["Gamma Water Works"]);
});

test("searchVendors never treats the query as a regular expression", () => {
  assert.deepEqual(searchVendors(vendors, "(west)", 2024).map((v) => v.name), ["Acme (West) Inc"]);
  for (const q of ["(", ".*", "\\", "[", "a**", "?"]) assert.deepEqual(searchVendors(vendors, q, 2025), []);
});

test("searchVendors returns nothing for an empty or blank query and honours the limit", () => {
  assert.deepEqual(searchVendors(vendors, "", 2025), []);
  assert.deepEqual(searchVendors(vendors, "   ", 2025), []);
  assert.equal(searchVendors(vendors, "a", 2025, 2).length, 2);
});

test("parseVendorHash validates the year and trims the query", () => {
  const years = [2022, 2023, 2024, 2025, 2026];
  assert.deepEqual(parseVendorHash("#fy=2024&q=%20water%20", years), { fy: 2024, q: "water" });
  assert.deepEqual(parseVendorHash("#fy=1999", years), { fy: 2026, q: "" });
  assert.deepEqual(parseVendorHash("#fy=abc&q=" + "x".repeat(200), years), { fy: 2026, q: "x".repeat(80) });
  assert.deepEqual(parseVendorHash("", years), { fy: 2026, q: "" });
});

test("serializeVendorHash round-trips and omits an empty query", () => {
  const years = [2022, 2023, 2024, 2025, 2026];
  assert.equal(serializeVendorHash({ fy: 2025, q: "" }), "#fy=2025");
  const state = { fy: 2025, q: "water authority & co" };
  assert.deepEqual(parseVendorHash(serializeVendorHash(state), years), state);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test`
Expected: FAIL (`truncate` is not exported from `./format.js`; `./vendors-model.js` not found).

- [ ] **Step 3: Implement**

Append to `site/js/format.js`:
```js
export function truncate(text, maxChars) {
  if (maxChars < 1) return "";
  return text.length <= maxChars ? text : `${text.slice(0, maxChars - 1)}…`;
}
```

`site/js/vendors-model.js`:
```js
const normalise = (text) => text.toLowerCase().replace(/\s+/g, " ").trim();

export function topVendors(vendors, fy, n = 25) {
  return vendors
    .filter((v) => v.amounts[fy] !== undefined)
    .map((v) => ({ name: v.name, ids: v.ids, amount: v.amounts[fy] }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, n);
}

export function concentration(vendors, fy, n = 10) {
  const all = topVendors(vendors, fy, Infinity);
  const total = all.reduce((sum, v) => sum + v.amount, 0);
  const topTotal = all.slice(0, n).reduce((sum, v) => sum + v.amount, 0);
  return { count: all.length, total, topTotal, share: total === 0 ? 0 : topTotal / total };
}

const sumAmounts = (v) => Object.values(v.amounts).reduce((sum, a) => sum + a, 0);

// Literal substring match on purpose: the query is never turned into a regular expression.
export function searchVendors(vendors, query, fy, limit = 50) {
  const needle = normalise(query);
  if (needle === "") return [];
  return vendors
    .filter((v) => normalise(v.name).includes(needle))
    .sort((a, b) => (b.amounts[fy] ?? 0) - (a.amounts[fy] ?? 0) || sumAmounts(b) - sumAmounts(a) || a.name.localeCompare(b.name))
    .slice(0, limit);
}

export function parseVendorHash(hash, years) {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const wanted = Number.parseInt(params.get("fy"), 10);
  const fy = years.includes(wanted) ? wanted : years.at(-1);
  const q = (params.get("q") ?? "").trim().slice(0, 80);
  return { fy, q };
}

export function serializeVendorHash({ fy, q }) {
  return q ? `#fy=${fy}&q=${encodeURIComponent(q)}` : `#fy=${fy}`;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test`
Expected: all pass (the earlier 21 plus 1 truncate and 7 vendors tests).

- [ ] **Step 5: Commit**

```bash
git add site/js
git commit -m "Add tested JS model for vendor ranking, concentration, search and URL state"
```

---

### Task 6: The "Who gets paid" page

**Files:**
- Create: `site/vendors.html`, `site/js/vendors.js`
- Modify: `site/index.html`, `site/methods.html` (nav link; vendor section on methods), `site/css/site.css`, `site/js/main.js` (import `truncate` from `format.js` instead of its local copy)
- Test: `tests/test_site_smoke.py` (append)

**Interfaces:**
- Consumes: `site/data/vendors.json` (Task 4), `vendors-model.js` and `format.js` (Task 5).
- Produces DOM ids for the smoke tests: `#vhead`, `#vcoverage`, `#passthrough-note`, `#fy` (range), `#fy-label`, `#q` (search input), `#leaders` (Plot chart), `#leader-table tbody tr`, `#search-table tbody tr`, `#search-empty`, `#vendor-trend`, and `details.method` inside every `figure`.

- [ ] **Step 1: Write the failing smoke tests (append to `tests/test_site_smoke.py`)**

```python
def open_vendors(page, site_url, hash_=""):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/vendors.html{hash_}")
    page.wait_for_selector("#leader-table tbody tr")
    return errors


def test_vendors_page_shows_leaders_headline_and_honest_coverage(page, site_url):
    errors = open_vendors(page, site_url)
    assert page.locator("#leader-table tbody tr").count() == 25
    head = page.locator("#vhead").inner_text()
    assert "FY2026" in head and "vendors" in head and "$" in head
    coverage = page.locator("#vcoverage").inner_text()
    assert "%" in coverage and "not total spending" in coverage.lower()
    assert "pass-through" in page.locator("#passthrough-note").inner_text().lower()
    assert errors == []


def test_every_vendor_figure_has_a_method_drawer(page, site_url):
    open_vendors(page, site_url)
    assert page.locator("figure").count() == page.locator("figure details.method").count() >= 1


def test_vendor_search_finds_a_payee_and_shows_its_trend(page, site_url):
    open_vendors(page, site_url)
    page.locator("#q").press_sequentially("water authority")  # real keystrokes: the space must survive
    page.wait_for_selector("#search-table tbody tr")
    assert page.input_value("#q") == "water authority"
    assert "San Diego County Water Authority" in page.locator("#search-table").inner_text()
    assert "q=water%20authority" in page.url
    page.click("#search-table tbody tr button")
    page.wait_for_selector("#vendor-trend svg")
    assert page.locator("#vendor-trend rect").count() == 5


def test_vendor_search_with_regex_characters_is_literal_and_safe(page, site_url):
    errors = open_vendors(page, site_url)
    page.fill("#q", "(.*")
    page.wait_for_function("document.getElementById('search-empty').hidden === false")
    assert "no vendors" in page.locator("#search-empty").inner_text().lower()
    assert errors == []


def test_vendors_deep_link_restores_year_and_search(page, site_url):
    open_vendors(page, site_url, "#fy=2022&q=sdcers")
    assert page.input_value("#fy") == "2022"
    assert page.input_value("#q") == "sdcers"
    assert "SDCERS" in page.locator("#search-table").inner_text()
    assert "FY2022" in page.locator("#vhead").inner_text()


def test_vendors_page_has_no_horizontal_scroll_on_a_phone(page, site_url):
    page.set_viewport_size({"width": 390, "height": 800})
    open_vendors(page, site_url)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_nav_links_to_the_vendors_page_from_every_page(page, site_url):
    for path in ("/", "/methods.html"):
        page.goto(site_url + path)
        assert page.locator("nav a[href='vendors.html']").count() == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_site_smoke.py -q -k "vendor or nav_links" -x`
Expected: FAIL (the vendors page does not exist; `wait_for_selector` times out).

- [ ] **Step 3: Write `site/vendors.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Who gets paid · San Diego Spending</title>
  <meta name="description" content="The vendors the City of San Diego paid $25,000 or more each year, FY2022 to FY2026.">
  <link rel="stylesheet" href="css/site.css">
</head>
<body>
  <header class="site-header">
    <nav>
      <strong>San Diego Spending</strong>
      <a href="index.html">Where your dollar goes</a>
      <a href="vendors.html" aria-current="page">Who gets paid</a>
      <a href="methods.html">Data &amp; methods</a>
    </nav>
  </header>
  <main>
    <h1>Who gets paid</h1>
    <p id="vhead" class="headline" aria-live="polite">Loading…</p>
    <p id="vcoverage" class="note"></p>
    <p id="passthrough-note" class="note">The City publishes no purpose or category for these payments, so a large
      payment is not necessarily a purchase of services: it can be a pass-through, for example to the pension system
      or a regional water wholesaler. Nothing here says a payment was too high.</p>

    <form class="controls" aria-label="Year" onsubmit="return false">
      <div class="year-control">
        <label for="fy">Fiscal year: <strong id="fy-label"></strong></label>
        <input type="range" id="fy" min="2022" max="2026" step="1" value="2026">
      </div>
    </form>

    <h2>Largest payees</h2>
    <figure>
      <div id="leaders" role="img" aria-label="Bar chart of the 25 vendors paid the most in the selected year"></div>
      <details class="method">
        <summary>Method</summary>
        <p>Source: the City's yearly "Cumulative Amounts Paid to Vendors - $25,000 or more" reports (PDF), read with
          <code>pdftotext</code>. Only vendors paid $25,000 or more in the year are listed. A company that appears
          under several vendor IDs or spellings is combined into one row. Fiscal years are named by the year they end;
          the FY2026 report covers July 2025 to June 2026. See <a href="methods.html">Data &amp; methods</a>.</p>
      </details>
    </figure>
    <div class="table-wrap">
      <table id="leader-table">
        <caption class="note">The same 25 payees, largest first.</caption>
        <thead><tr><th scope="col">Vendor</th><th scope="col">Paid</th><th scope="col">Share of listed payments</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>

    <h2>Find a vendor</h2>
    <div class="vendor-search">
      <label for="q">Search by name</label>
      <input type="search" id="q" autocomplete="off" placeholder="e.g. water, construction, SDCERS">
    </div>
    <p id="search-empty" class="note" hidden>No vendors match that name.</p>
    <div class="table-wrap">
      <table id="search-table" hidden>
        <caption class="note">Matches, largest in the selected year first. A dash means no payment of $25,000 or more that year.</caption>
        <thead><tr><th scope="col">Vendor</th><th scope="col">FY2022</th><th scope="col">FY2023</th><th scope="col">FY2024</th><th scope="col">FY2025</th><th scope="col">FY2026</th><th scope="col"><span class="visually-hidden">Trend</span></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <figure id="trend-figure" hidden>
      <h3 id="trend-title"></h3>
      <div id="vendor-trend" role="img" aria-label="Bar chart of one vendor's payments by fiscal year"></div>
      <details class="method">
        <summary>Method</summary>
        <p>Years with no bar had no payment of $25,000 or more to this vendor (they may have been paid less, which the
          City does not publish).</p>
      </details>
    </figure>
  </main>
  <script type="module" src="js/vendors.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write `site/js/vendors.js`**

```js
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { formatMoney, truncate } from "./format.js";
import { topVendors, concentration, searchVendors, parseVendorHash, serializeVendorHash } from "./vendors-model.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const money = (n) => `$${Math.round(n).toLocaleString("en-US")}`;

let data;
try {
  const response = await fetch("data/vendors.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
} catch (error) {
  $("vhead").textContent = "Sorry, the vendor data could not be loaded. Please try again later.";
  throw error;
}

let state = parseVendorHash(location.hash, data.years);
let selected = null; // vendor whose trend is shown

function update(patch) {
  state = parseVendorHash(serializeVendorHash({ ...state, ...patch }), data.years);
  history.replaceState(null, "", serializeVendorHash(state));
  render();
}

function fillTable(tableId, lines) {
  $(tableId).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) {
      const td = document.createElement("td");
      if (cell instanceof Node) td.append(cell);
      else td.textContent = cell;
      tr.append(td);
    }
    return tr;
  }));
}

function drawLeaders(leaders) {
  const width = Math.max(300, $("leaders").clientWidth);
  const marginLeft = Math.round(Math.min(240, Math.max(110, width * 0.34)));
  $("leaders").replaceChildren(Plot.plot({
    width, height: 24 * leaders.length + 40, marginLeft, marginRight: 64,
    x: { label: null, grid: true, ticks: width < 500 ? 3 : 8, tickFormat: (v) => formatMoney(v) },
    y: { label: null, domain: leaders.map((l) => l.name), tickFormat: (n) => truncate(n, Math.floor(marginLeft / 6.6)) },
    marks: [
      Plot.barX(leaders, { y: "name", x: "amount", fill: css("--accent"), title: (d) => `${d.name}: ${money(d.amount)}` }),
      Plot.text(leaders, { y: "name", x: "amount", text: (d) => formatMoney(d.amount), dx: 4, textAnchor: "start" }),
      Plot.ruleX([0]),
    ],
  }));
}

function drawTrend(vendor) {
  const points = data.years.filter((y) => vendor.amounts[y] !== undefined)
    .map((y) => ({ fy: y, amount: vendor.amounts[y] }));
  $("trend-title").textContent = vendor.name;
  $("trend-figure").hidden = false;
  $("vendor-trend").replaceChildren(Plot.plot({
    width: Math.max(300, $("vendor-trend").clientWidth), height: 200, marginLeft: 56,
    x: { tickFormat: "d", label: null, tickSize: 0, domain: data.years },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [Plot.barY(points, { x: "fy", y: "amount", fill: css("--accent"), title: (d) => `FY${d.fy}: ${money(d.amount)}` }), Plot.ruleY([0])],
  }));
}

function drawSearch() {
  const matches = searchVendors(data.vendors, state.q, state.fy);
  // only rewrite the box when it differs after trimming, or typing a space would be erased
  if ($("q").value.trim() !== state.q) $("q").value = state.q;
  $("search-table").hidden = matches.length === 0;
  $("search-empty").hidden = state.q === "" || matches.length > 0;
  fillTable("search-table", matches.map((vendor) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Show trend";
    button.addEventListener("click", () => { selected = vendor; drawTrend(vendor); });
    return [vendor.name, ...data.years.map((y) => (vendor.amounts[y] === undefined ? "—" : formatMoney(vendor.amounts[y]))), button];
  }));
  if (selected && !matches.includes(selected)) {
    selected = null;
    $("trend-figure").hidden = true;
  }
}

function render() {
  $("fy").value = state.fy;
  $("fy-label").textContent = `FY${state.fy}`;
  const conc = concentration(data.vendors, state.fy, 10);
  const cov = data.coverage[state.fy];
  $("vhead").textContent =
    `FY${state.fy}: the City paid ${conc.count.toLocaleString("en-US")} vendors $25,000 or more, ${formatMoney(conc.total)} in total. The 10 largest received ${Math.round(conc.share * 100)}% of that.`;
  const basis = cov.reference_basis === "actual" ? "actual spending" : "adopted budget";
  $("vcoverage").textContent =
    `These payments equal ${Math.round((100 * cov.vendors_total) / cov.reference_total)}% of the City's FY${state.fy} ${basis} (${formatMoney(cov.reference_total)}). Vendors paid less than $25,000 in the year are not published, so this is not total spending.`;
  const leaders = topVendors(data.vendors, state.fy, 25);
  drawLeaders(leaders);
  fillTable("leader-table", leaders.map((l) => [l.name, money(l.amount), `${((100 * l.amount) / conc.total).toFixed(1)}%`]));
  drawSearch();
  if (selected) drawTrend(selected);
}

$("fy").addEventListener("input", (e) => update({ fy: Number(e.target.value) }));
$("q").addEventListener("input", (e) => update({ q: e.target.value }));
window.addEventListener("hashchange", () => { state = parseVendorHash(location.hash, data.years); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("leaders").clientWidth;
new ResizeObserver(() => {
  const width = $("leaders").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("leaders"));

render();
```

- [ ] **Step 5: Wire navigation, styles and the shared helper**

1. In `site/index.html` and `site/methods.html`, replace the `<a href="methods.html"...>Data &amp; methods</a>` nav link by itself preceded by `<a href="vendors.html">Who gets paid</a>` (so the nav reads: Where your dollar goes, Who gets paid, Data & methods; keep each page's own `aria-current="page"`).
2. Append to `site/css/site.css`:
```css
.vendor-search label { display: block; font-size: .8rem; color: var(--muted); }
.vendor-search input { width: 100%; max-width: 28rem; font: inherit; padding: .4rem .6rem;
  color: var(--text); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; }
table button { font: inherit; font-size: .85rem; cursor: pointer; color: var(--accent);
  background: none; border: 1px solid var(--line); border-radius: 6px; padding: .15rem .5rem; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
h3 { font-size: 1rem; margin: 1.25rem 0 .25rem; }
```
3. In `site/js/main.js`: add `truncate` to the `format.js` import (`import { formatMoney, formatPerResident, truncate } from "./format.js";`) and delete the local `function truncate(text, maxChars) {...}` (3 lines).
4. In `site/methods.html`, add before "Checks that run on every build" this section:
```html
    <h2>Who gets paid (vendor payments)</h2>
    <ul>
      <li><strong>Source:</strong> the City's yearly "Cumulative Amounts Paid to Vendors - $25,000 or more" reports
        (PDF), FY2022 to FY2026, read with <code>pdftotext</code>. The FY2026 report covers July 2025 to June 2026.</li>
      <li><strong>Only payments of $25,000 or more</strong> to a vendor in the year are published, so the totals are
        a share of City spending, not all of it. The page states that share next to every total.</li>
      <li><strong>No purpose or category</strong> is published, so a large payee can be a pass-through (for example to
        the pension system or a regional water wholesaler). The page makes no judgement about whether a payment was
        too high.</li>
      <li><strong>One company, several IDs.</strong> Vendors whose names match ignoring case, punctuation and
        "&amp;" vs "and" are combined, and all their vendor IDs are kept in
        <code>data/processed/vendor_payments.csv</code>.</li>
      <li><strong>Checks:</strong> the extractor fails on any line it does not recognise, a page-count mismatch, a
        duplicate vendor ID or an amount under $25,000. The reports print no totals, so the build also requires each
        year's vendor payments to be between 40% and 110% of the City's own spending for that year (they are
        58%-86% today).</li>
    </ul>
```
(Place `<h2>` and `<ul>` as written; the closing `</ul>` above ends that list.)

- [ ] **Step 6: Run to verify the smoke tests pass, then everything**

Run: `uv run pytest -q && npm test`
Expected: all Python tests (including the new smoke tests) pass and all JS tests pass.

- [ ] **Step 7: Look at it**

Write the script below to `/private/tmp/claude-501/-Users-mckornfield-gov-transparency/6264a5b2-e34c-43a4-ba0c-c8f2b3f809b8/scratchpad/shot_vendors.py`, run it with `uv run python <that path>`, then open `vendors_desktop.png` and `vendors_phone.png` (same directory) with the Read tool. Confirm that on the 390px view the payee labels are readable and nothing is clipped; fix `drawLeaders` margins if not.
```python
import subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).parent
server = subprocess.Popen([sys.executable, "-m", "http.server", "8768", "--bind", "127.0.0.1",
                           "--directory", "site"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, width in (("vendors_desktop", 1100), ("vendors_phone", 390)):
            page = browser.new_page(viewport={"width": width, "height": 1500})
            page.goto("http://127.0.0.1:8768/vendors.html#fy=2025&q=water")
            page.wait_for_selector("#leader-table tbody tr")
            page.screenshot(path=str(out / f"{name}.png"))
        browser.close()
finally:
    server.terminate()
```
(Run from the repo root so `--directory site` resolves.)

- [ ] **Step 8: Commit**

```bash
git add site tests/test_site_smoke.py
git commit -m "Add Who gets paid page: leaders, concentration, search and vendor trend"
```

---

### Task 7: Docs and final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the README**

In the "Reproduce everything" block, after the `fetch_sco_population.py` line add:
```bash
uv run python scripts/fetch_sd_vendor_payments.py   # 5 PDFs -> data/raw/sandiego/vendor_payments_fy20NN.pdf.gz
```
and after the `build_processed.py` line add:
```bash
uv run python scripts/build_vendors.py          # needs poppler: brew install poppler (or apt install poppler-utils)
```
Add this row to the "Data sources" table:
```
| Vendor payments of $25,000 or more, FY2022-FY2026 (PDF, one per year) | City of San Diego, sandiego.gov "Cumulative Amounts Paid to Vendors" | `fetch_sd_vendor_payments.py`, `build_vendors.py` |
```
Append to "Data-quality notes":
```
- Vendor payments: the PDFs list only vendors paid $25,000 or more in the year, with no purpose or category, and print no totals. `build_vendors.py` fails on any unrecognised line, page-count mismatch, duplicate vendor ID or amount under $25,000, and requires each year's vendor total to be 40%-110% of the City's own spending (currently 58%-86%).
- The same company can appear under several vendor IDs and spellings (e.g. San Diego Gas and Electric); vendors are merged when names match ignoring case, punctuation and "&" vs "and", and all IDs are kept in `data/processed/vendor_payments.csv`.
- The FY2026 vendor report covers July 2025 to June 2026; the quarterly file in the same series (July-September 2025 only) is not used.
```

- [ ] **Step 2: Run the whole verification**

Run: `uv run pytest -q && npm test`
Expected: everything passes (Python incl. smoke; JS).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document vendor-payment sources, checks and the poppler requirement"
```

- [ ] **Step 4: Ask before anything outward-facing**

Do NOT push. Tell the user the page is built and verified locally and ask whether to push `main`.
