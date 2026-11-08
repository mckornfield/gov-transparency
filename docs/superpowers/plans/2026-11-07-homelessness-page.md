# Homelessness Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, one fresh opus review at the end). Steps use checkbox syntax.

**Goal:** A `site/homelessness.html` page: city and state homelessness dollars per person counted, point-in-time (PIT) trend for San Diego vs CA regions and US peer cities, and state-reported outcomes, all labelled "reported".

**Architecture:** Same pipeline as peers: `scripts/fetch_homelessness.py` stores raw files (gz + MANIFEST); `src/sd_spend/homeless.py` parses them strictly (build fails on surprises); `scripts/build_homelessness.py` writes `data/processed/*.csv` and `site/data/homelessness.json`; pure-JS `site/js/homelessness-model.js` (node-tested) feeds `homelessness.js` (Observable Plot).

**Tech Stack:** pandas, pyxlsb (new dependency, for HUD's .xlsb), poppler `pdftotext` (already required), Observable Plot 0.6.16, `node --test`, Playwright smoke tests.

**Spec:** `docs/superpowers/specs/2026-11-04-homelessness-page-design.md`

## Spec amendments (rulings made while planning; the spec is otherwise binding)
1. **No per-1,000 for out-of-state peers.** HUD counts are per CoC (usually city + county, e.g. "Phoenix, Mesa/Maricopa County"), while our city populations are city-only; dividing would mislead. Peers show the count change since 2019 (index, 2019 = 100) and sheltered/unsheltered split, which need no population. California regions are shown the same way plus raw counts.
2. **Never sum city and state dollars.** City department revenue ($34.6M of $42.1M FY24 spending) includes grants such as HHAP passing through, so adding the two lines would double count. They are shown as separate series, with the city's grant-funded share (department revenue) displayed beside its expenditures.
3. **HUD file source.** The workbook was downloaded by the user in a browser (HUD blocks automated downloads). It is stored under `data/raw/hud/` with the AHAR Part 1 page as the manifest URL, and the methods page says it was supplied manually.

## Global Constraints
- Dollars are nominal; labels say "awarded" (HHAP) and "budgeted/actual" (city). Never "effective".
- Builds raise on: unparseable PDF line in a table we read, missing region or year, non-numeric count other than the documented "N/A" (2021 waived count), value outside plausibility (PIT per CoC > 0, M5 between 0 and 1).
- UI: existing patterns (URL-hash state, inline legend styles, `css/site.css?v=` bump when CSS changes, no horizontal scroll at phone width).
- Test commands: `uv run pytest`, `npm test`.

## Review Focus
- 2021 PIT is "N/A": lines must break, not drop to 0 or interpolate (Task 2 test, Task 4 test).
- HHAP rounds list the same place under CoC, city and county columns; San Diego City vs San Diego County must not be swapped (Task 2 test pins Round 5 city 29,918,593 / county 14,160,463 / CoC 14,759,532).
- City department revenue vs expenditures shown, no sum (Task 3/4 tests).
- Pass-through of "Los Angeles", "San Francisco", "San Jose" names: CoC names differ from city names ("San Jose/Santa Clara City & County CoC"); mapping is by CoC number from config, never by name matching.
- Sheltered-only count years: 2021 workbook rows carry "Sheltered-Only Count" in `Count Types`; those must not be read as totals (Task 2 test).

## File Structure
- Create `scripts/fetch_homelessness.py`, `scripts/build_homelessness.py`
- Create `src/sd_spend/homeless.py` (parsers + validation), tests `tests/test_homeless.py`, `tests/test_real_homelessness.py`
- Create `config/homelessness.json`
- Modify `src/sd_spend/export.py` (`homelessness_payload`), `tests/test_export.py`, `tests/test_manifest.py`, `pyproject.toml`
- Create `site/homelessness.html`, `site/js/homelessness-model.js` (+`.test.js`), `site/js/homelessness.js`; modify nav in `site/index.html`, `peers.html`, `vendors.html`, `methods.html`; `tests/test_site_smoke.py`
- Modify `site/methods.html`, `README.md`

---

### Task 1: Raw data fetch and manifest

**Files:** Create `scripts/fetch_homelessness.py`; modify `pyproject.toml`, `tests/test_manifest.py`.

**Interfaces:** Produces raw files (all via `sd_spend.io.save_raw(content, relpath, url)`):
`calich/ca_spms.csv`, `calich/ca_spms_dictionary.csv`, `hcd/hhap_r1_redir.pdf`, `hcd/hhap_r2.pdf` … `hcd/hhap_r5.pdf`, `sandiego/hssd_budget_fy{2023,2024,2025,2026}.pdf`, `hud/2007-2024-PIT-Counts-by-CoC.xlsb`.

- [ ] **Step 1: Failing test.** In `tests/test_manifest.py` add to `REQUIRED` the paths above (each with `.gz`). Run `uv run pytest tests/test_manifest.py -q` → FAIL (missing).
- [ ] **Step 2: Implement.** `pyproject.toml` dependencies add `"pyxlsb>=1.0.10"` and run `uv lock`. `fetch_homelessness.py`: CA SPM URL discovered by `GET https://data.ca.gov/api/3/action/package_search?q=system+performance+measures+CoC&rows=5` → the dataset titled exactly "CA System Performance Measures, Statewide and by CoC" → resources named "CA SPMs Prior Years and Last Twelve Months CSV" and "CA SPM Data Dictionary CSV" (raise if not found; requests follows the redirect). HHAP URLs: `https://www.hcd.ca.gov/sites/default/files/docs/grants-and-funding/calich/hhap_r{2,3,4}_allocations.pdf`, `hhap-5-allocations.pdf`, `https://hcd.ca.gov/sites/default/files/docs/grants-and-funding/calich/hhap_r1_redir_allocations.pdf`. City budgets: FY26 `https://www.sandiego.gov/sites/default/files/2025-08/fy26ab_v2hssd.pdf`, FY25 `…/2024-08/fy25ab_v2hssd.pdf`, FY23 `…/fy23ab_v2hsd.pdf`; FY24: find the adopted-budget Homelessness Strategies and Solutions volume URL on sandiego.gov (search "fy24ab" hssd) and record it in the script; fail the task if it cannot be fetched. HUD: `--hud-file PATH` argument copies the user's workbook through `save_raw` with URL `https://www.huduser.gov/portal/datasets/ahar/2024-ahar-part-1-pit-estimates-of-homelessness-in-the-us.html`.
- [ ] **Step 3: Run** `uv run python scripts/fetch_homelessness.py --hud-file "/Users/mckornfield/.claude/uploads/6264a5b2-e34c-43a4-ba0c-c8f2b3f809b8/1812b7e5-2007-2024-PIT-Counts-by-CoC.xlsb"`, then `uv run pytest tests/test_manifest.py -q` → PASS.
- [ ] **Step 4: Commit** `Fetch homelessness sources: Cal ICH measures, HHAP allocations, city budgets, HUD PIT`.

### Task 2: Parsers

**Files:** Create `src/sd_spend/homeless.py`, `tests/test_homeless.py`.

**Interfaces — Produces:**
- `parse_spm(csv_text) -> DataFrame[location, coc_id|None, metric, period, value(float|NaN)]` — periods are the nine column headers; `"N/A"` → NaN; `coc_id` = leading `CA-\d{3}` or None for "California". Raises `HomelessError` on unknown metric or non-numeric non-"N/A".
- `parse_hhap(text, round_label) -> DataFrame[round, kind('coc'|'city'|'county'), name, amount]` — splits the three-column layout of `pdftotext -layout` output. Raises if no San Diego row of each kind, or any dollar figure on a line that is not assigned.
- `parse_budget(text) -> dict{expenditures:{FYxxxx:float}, revenue:{...}, actual_years:[...]}` — reads the "Total Department Expenditures"/"Total Department Revenue" rows under the "FYxxxx Actual / FYxxxx Budget / FYxxxx Adopted" header (first column is the actual).
- `parse_hud_pit(xlsb_bytes, coc_ids) -> DataFrame[coc_id, year, total, sheltered, unsheltered]` — sheets named by year 2007-2024; `Count Types` "Sheltered-Only Count" rows give `unsheltered=NaN`, `total=NaN` (not a total); NaN for years a CoC is missing; raises if a requested CoC is absent from any year ≥2019.
- `class HomelessError(Exception)`.

- [ ] **Step 1: Failing tests** (synthetic text/bytes built in the test): SPM `"N/A"` → NaN not 0 and unknown metric raises; HHAP three-column line `"San Diego City and County CoC   $14,759,532.30   San Diego   $29,918,593.27   San Diego   $14,160,463.76"` parses to coc/city/county; HHAP line with an extra unassigned dollar value raises; budget text fragment (from `b26`: `Total Department Expenditures $ 42,114,403 $ 53,916,571 $ 53,821,132 $ (95,439)`) → FY2024 actual 42114403 given header `FY2024 FY2025 FY2026`; HUD workbook built with a tiny in-memory `.xlsb` is not possible → build the HUD test against the real raw file in Task 3 and here only test `_rows_to_pit(rows_by_year)` (pure function, same logic) for sheltered-only handling and missing-CoC raise.
- [ ] **Step 2:** `uv run pytest tests/test_homeless.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** to pass. Use `pyxlsb.open_workbook(io.BytesIO(...))` in `parse_hud_pit`; find columns by header text (`Overall Homeless`, `Sheltered Total Homeless`, `Unsheltered Homeless`; inspect the real headers and use exact names).
- [ ] **Step 4:** tests PASS. **Step 5: Commit** `Add strict parsers for Cal ICH measures, HHAP allocations, city budgets and HUD counts`.

### Task 3: Config, export and build

**Files:** Create `config/homelessness.json`, `scripts/build_homelessness.py`, `tests/test_real_homelessness.py`; modify `src/sd_spend/export.py`, `tests/test_export.py`.

**Interfaces — Produces:** `export.homelessness_payload(spm, hhap, city, pit, cfg) -> dict`:
`{home:"CA-601", regions:[{coc_id,name,role:'home'|'ca'|'state'|'peer'|'reference'}], years:[2007..2024 PIT years], pit:[{coc_id,year,total,sheltered,unsheltered}] (null for missing), measures:[{coc_id,metric,period,value}] , hhap:[{round,coc_id,coc,city,county}] for San Diego and the CA regions only, city:[{fy,expenditures,revenue,kind:'actual'|'adopted'}], population:[{fy,population}] from data/processed (existing sd population series), labels:{...metric names from the dictionary}}`. Values rounded; NaN → null.

`config/homelessness.json`: home `CA-601`; CA regions CA-600 Los Angeles, CA-501 San Francisco, CA-500 San Jose; peers (role `peer`) AZ-502, TX-500, TX-600, TX-503, TX-601, NC-505, OH-503, WA-500, OR-501, MA-500; references (`reference`) VA-600 Arlington County, WA-508 Vancouver/Clark County; plus HHAP name mapping for the region columns (`{"CA-600":{"city":"Los Angeles","county":"Los Angeles"}, …}`).

- [ ] **Step 1: Failing tests.** `test_export.py`: small payload shape test (NaN→null, roles preserved, hhap restricted to configured regions). `test_real_homelessness.py` (reads raw via manifest paths): SD CoC PIT 2024 = 10,605 and equals Cal ICH `PIT Count` 2024 (cross-check, two sources); 2021 SD PIT is null; every configured CoC has totals for 2019, 2020, 2022-2024; HHAP Round 5 SD city 29,918,593, county 14,160,463, CoC 14,759,532; city FY2024 actual expenditures 42,114,403 and revenue 34,561,306; M3/M1a within (0,1) for all CA regions; every metric has all nine periods.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement export + config + `build_homelessness.py` (writes `data/processed/homeless_pit.csv`, `homeless_measures.csv`, `homeless_hhap.csv`, `homeless_city.csv`, and `site/data/homelessness.json`). **Step 4:** run build, tests PASS, full `uv run pytest -q` green. **Step 5: Commit** `Build homelessness data: PIT counts, state measures, HHAP awards, city budget lines`.

### Task 4: Page model and UI

**Files:** Create `site/js/homelessness-model.js`, `site/js/homelessness-model.test.js`, `site/js/homelessness.js`, `site/homelessness.html`; modify nav in the four existing pages; `tests/test_site_smoke.py`.

**Interfaces — Produces (model):** `dollarsPerCounted(data, fy)` → `{city:{expenditures,revenue,perCounted}, hhap:{awarded,perCounted}}` using the SD CoC PIT count of the calendar year nearest-before FY end (FY2024 ↔ Jan 2024 count); `null` perCounted when the count is null. `pitIndex(data, ids, base=2019)` → series of count/base×100, null for 2021. `outcomeSeries(data, ids, metric)` where `exitRate = M3/M1a`. `parseHash/serializeHash` (`regions`, `metric`) with sanitising like peers-model.

- [ ] **Step 1: Failing node tests** for each function incl. null 2021 (no bridging), exit rate = M3/M1a, hash round trip and garbage hash fallback, HHAP + city never summed (assert result has no `total` key).
- [ ] **Step 2:** `npm test` → FAIL. **Step 3:** implement model. **Step 4:** PASS.
- [ ] **Step 5: Page.** Sections (each a short heading + one-sentence takeaway + chart + `<details>` table): (1) dollars per person counted, city vs HHAP, with the revenue/pass-through note; (2) PIT index since 2019 for SD, CA regions, peers (reference as hollow rings, role legend with inline styles); (3) reported outcomes (exit rate, days homeless M4, returns M5) for SD vs LA/SF/SJ and state; (4) caveat panel quoting the Auditor finding. Phrase: "reported", never "effective".
- [ ] **Step 6: Smoke tests** (pytest/playwright, same style as peers): page loads with no console errors; SD FY2024 city expenditures text "$42.1M"; 2021 gap present in PIT table as "—"; garbage hash recovers; no horizontal scroll at 390px; role legend lists San Diego/CA/Peer/Reference; page contains no "effective" claim beyond the "not proven effective" caveat (assert the exact caveat string exists).
- [ ] **Step 7:** `npm test`, `uv run pytest -q` green. **Step 8: Commit** `Add homelessness page`.

### Task 5: Docs and release

**Files:** `site/methods.html`, `README.md`.

- [ ] **Step 1:** methods: sources table rows (Cal ICH, HCD, City budgets, HUD manual download), what HHAP awards mean, pass-through/double-counting, CoC vs city geography, 2021 waiver, Auditor caveat, "what this cannot show". README: source rows, fetch commands (`--hud-file`).
- [ ] **Step 2:** full suite green. Dispatch one fresh opus reviewer on `git diff <spec commit>..HEAD` with the Review Focus above; fix Critical/Important with RED→GREEN tests.
- [ ] **Step 3:** push with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push https://github.com/mckornfield/gov-transparency.git main` (standing instruction: push to main directly). Commit messages end with the Co-Authored-By and Claude-Session lines.
