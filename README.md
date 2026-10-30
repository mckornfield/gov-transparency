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
