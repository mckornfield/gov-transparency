# Government Transparency: San Diego Spending Explorer (v1 Design)

Date: 2026-10-29

## Purpose

An interactive GitHub Pages site that makes San Diego city spending legible to residents and measures how much is spent
above a private-sector equivalent ("margin"). A deeper explorer for journalists and advocates may follow, but v1 is
resident-first. The pipeline follows the conventions of `~/california-taxes`: committed raw data, one fetch script per
source, reproducible processed tables.

## Scope

**In v1:** City of San Diego only.
**Deferred:** State of California spending; contract-PDF unit-price extraction; vendor/contract drill-down for journalists.
**Out of scope:** Claiming "waste" or fraud. The metric is margin over a benchmark, with stated confidence.

## Terminology

- **Margin:** city spend minus the estimated private-sector equivalent cost. Shown as a low-high range with a confidence tier.
- **Peer gap:** difference between San Diego's per-resident spend and the median of similarly sized US cities. This is
  not a private-sector claim (peers share the same inefficiencies) and is never blended with margin.

## Data sources (v1)

| Data | Source | Format |
|---|---|---|
| Operating budget and actuals; accounts, departments, funds | data.sandiego.gov | CSV |
| CIP budget and actuals (by fiscal year, project to date); projects | data.sandiego.gov | CSV |
| Vendor payments ($25,000 or more), FY2022 on, quarterly cumulative | sandiego.gov cumulative-paid reports | PDF (extracted with pdftotext) |
| Peer-city finances by function | Census Annual Survey of State and Local Government Finances | CSV/Excel |
| Regional price parities | BEA | CSV |
| Private wages by occupation, San Diego area | BLS OEWS | CSV/Excel |
| Private retirement/benefit cost as % of compensation, West region | BLS Employer Costs for Employee Compensation | CSV |
| City pay by position | California State Controller public pay data (to verify availability) | CSV |
| City pension normal cost, retiree health, unfunded liability payments | City actuarial reports / ACFR | PDF/CSV (verify) |
| Construction/paving unit costs | Caltrans contract cost data, state/GSA contract prices (to verify) | CSV |

The city portal has no vendor, contract, purchase-order, or payroll dataset. Vendor PDFs list only vendor ID, name, and
total paid (no purpose or category). A California Public Records Act request for the full transaction-level checkbook is
filed in parallel; if fulfilled, it upgrades the vendor and margin pages later.

## Architecture

```
scripts/fetch_*.py   -> data/raw/ (+ MANIFEST.csv: url, retrieved date, sha256)
scripts/extract_*.py -> PDF -> CSV (vendor payments)
scripts/build_*.py   -> data/processed/*.csv -> site/data/*.json
site/                -> static HTML/JS (Observable Plot, D3 where needed), no build step
.github/workflows/   -> deploy site/ to GitHub Pages
```

- Python (uv, >=3.11) for fetch, extract, and build, matching california-taxes.
- Raw originals (CSV and the vendor PDFs) are committed. Large files get a size check before committing.
- Front end is plain static HTML/JS served from `site/`. No bundler.
- Config files (not code) hold the peer-city list and benchmark mappings, so they are easy to change.

## Margin methodology

Three methods, each result tagged with a confidence tier:

| Tier | Method | Example | Benchmark data |
|---|---|---|---|
| Direct | Same item, unit price vs market price | Paving per ton, vehicles, IT licenses | Caltrans, state/GSA contract prices |
| Occupation-matched | City pay and benefits vs private pay for same job in San Diego area | Engineers, accountants, mechanics | BLS OEWS, State Controller pay data |
| Estimate | Project cost vs comparable completed projects | Pipe replacement per mile | Published bid tabs (weakest tier) |

Rules:
- Margin is a low-high range reflecting benchmark uncertainty.
- Coverage is always stated: "margin measured on X% of spending". Results are never extrapolated to uncovered spending.
- Margin is floored at zero per line item. Items below benchmark are shown as "below market" and do not offset others.
- Missing benchmark means "no benchmark". Never filled in.

### Compensation and benefits

- Wages and total compensation are shown as separate lines, with a benefits on/off toggle.
- Pensions and 401(k)-style matches are both expressed as employer cost as a percentage of pay: city pension normal cost
  (plus retiree health) as a percent of payroll vs BLS ECEC private retirement and savings cost, West region.
- The page labels this an approximation with assumptions visible.
- Unfunded pension liability payments are a separate line. They are a real taxpayer cost but do not fund current
  employees' compensation, so they are excluded from the comparison.

## Peer gap methodology

- Peers: about 8-10 US cities of 0.8-2M people (e.g. Dallas, San Jose, Austin, Columbus, Indianapolis), set in config.
- Per-resident spending by function, adjusted for regional price levels using BEA regional price parities (toggle).
- Display: San Diego rank and distance from peer median, with the peer spread as a band.

## Pages (resident-facing)

Shared nav; each page opens with a plain-language headline.

1. **Where your dollar goes.** Treemap/sunburst by department, function, account. Per-resident and per-household toggle. Fiscal-year slider.
2. **Who gets paid.** Vendor leaderboard from extracted PDFs, search, quarterly trend, top-10 concentration, and a note on why more detail is unavailable.
3. **Margin explorer.** Range chart per category with confidence tier, coverage meter, a Method drawer on every figure (formula, sources, link to the underlying committed data row), benefits toggle.
4. **San Diego vs peers.** Dot plot per function with San Diego highlighted, selectable peer set, cost-of-living toggle.

Cross-cutting: phone layout, keyboard-reachable data table for every chart, light and dark mode, shareable deep links to chart state, and a Data & Methods page listing every source, retrieval date, and data-quality notes (modeled on the california-taxes README).

## Testing and error handling

- Build-time reconciliation, failing the build on mismatch:
  - extracted vendor rows sum to each report's stated total;
  - budget/actuals tables reconcile across department, account, and fund;
  - CIP fiscal-year and project-to-date totals reconcile;
  - peer-city figures match Census published totals.
- Unit tests for normalization (per resident, cost of living), margin range math, the zero floor, and pension-to-percent conversion, using small committed fixtures.
- Extractor tests on committed sample PDFs, including an older-format report.
- Front-end smoke test: each page loads, every chart renders from JSON, every figure has a Method drawer.
- Fetch scripts retry flaky hosts and record hashes in `MANIFEST.csv`; re-runs show a diff when a source changes.
- Missing benchmark renders "no benchmark". Pages show an as-of date and flag data older than the latest fiscal year.

## Build order (each step deployable)

1. Repo scaffold, `MANIFEST.csv` convention, Pages deploy of a placeholder site.
2. Budget/actuals fetch and build, then page 1.
3. Vendor PDF extractor with reconciliation, then page 2.
4. Peer-city data, then page 4.
5. Benchmarks (BLS, ECEC, Caltrans), then page 3. Largest and riskiest step.
6. Methods page, mobile and accessibility pass; records request filed in parallel.

## Risks and open items

- Step 5 depends on public benchmarks existing for San Diego's largest spending categories. Categories without one ship as "no benchmark".
- Availability of State Controller pay data, city actuarial figures, and Caltrans cost data is unverified and must be confirmed during planning.
- Vendor PDF layout may change across fiscal years; extractor tests guard this.
- Margin of a pension-vs-401(k) comparison is inherently approximate and is labeled as such.
