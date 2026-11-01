# San Diego Spending

Interactive charts of City of San Diego spending, published with GitHub Pages from `site/`.
Goal: make public spending data legible, and later measure how much is spent above a private-sector
equivalent ("margin"). See `docs/superpowers/specs/` for the design.

## Reproduce everything
```bash
uv sync
uv run python scripts/fetch_sd_budget.py        # ~130 MB download -> data/raw/sandiego/*.csv.gz
uv run python scripts/fetch_sco_population.py   # -> data/raw/sco/
uv run python scripts/fetch_sd_vendor_payments.py   # 5 PDFs -> data/raw/sandiego/vendor_payments_fy20NN.pdf.gz
uv run python scripts/build_processed.py        # -> data/processed/, site/data/
uv run python scripts/fetch_census_finances.py   # Census city finances FY2019-FY2024 -> data/raw/census/
uv run python scripts/fetch_bea_rpp.py           # BEA regional price parities -> data/raw/bea/
uv run python scripts/build_peers.py            # -> data/processed/peer_spending.csv, site/data/peers.json
uv run python scripts/build_vendors.py          # needs poppler: brew install poppler (or apt install poppler-utils)
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
| City finances for San Diego and 11 peer cities, FY2019-FY2024 (Census individual unit files; fixed-width text in a zip) | Census Bureau, Annual Survey of State and Local Government Finances | `fetch_census_finances.py`, `build_peers.py`; peers in `config/peers.json`, service mapping in `config/census_functions.json` |
| Regional price parities by metro area, 2008-2024 (zip of CSV) | Bureau of Economic Analysis, table MARPP | `fetch_bea_rpp.py`; used by `build_peers.py` |
| Vendor payments of $25,000 or more, FY2022-FY2026 (PDF, one per year) | City of San Diego, sandiego.gov "Cumulative Amounts Paid to Vendors" | `fetch_sd_vendor_payments.py`, `build_vendors.py` |

## Data-quality notes
- Fiscal years are named by the year they end (FY2023 = July 2022 to June 2023). Dollars are nominal.
- The budget file contains `adopted` and `proposed` rows for FY2024-25; only adopted rows are used (summing both double-counts).
- FY2026 budget rows have a blank `budget_cycle` and are treated as adopted. The City's actuals file stops at FY2023.
- Expense = account numbers starting with 5. 12 FY2026 budget rows have a blank account number and are excluded; their total is in `data/processed/build_report.json`.
- `Transfers Out` (~13% of FY2023 spending) is hidden by default in the UI because it moves money between city funds.
- The build fails if aggregation changes a total, if adopted budget differs from actuals by more than 25%, or if any year's total jumps more than 40%.
- SCO population is missing for 2006, 2010 and 2026; the build interpolates or carries forward and flags those years.
- Vendor payments: the PDFs list only vendors paid $25,000 or more in the year, with no purpose or category, and print no totals. `build_vendors.py` fails on any unrecognised line, page footers that are not exactly 1..N, a page count that differs from `pdfinfo`, a duplicate vendor ID or an amount under $25,000, and on a year-over-year change of more than 35% in vendor count. It also requires each year's vendor total to be 40%-110% of the City's own spending (currently 58%-86%), which is only a coarse sanity band; vendor payments and City spending are not directly comparable (spending includes payroll; the vendor list includes capital and pass-through payments).
- The same company can appear under several vendor IDs and spellings (e.g. San Diego Gas and Electric); vendors are merged when names match ignoring case, punctuation, "&" vs "and" and endings like Inc/LLC/Co/"The", or when a vendor ID is renamed to a name starting with the same word, and all IDs are kept in `data/processed/vendor_payments.csv`.
- Peer cities: consolidated city-counties are excluded; $0 for a service means the city does not report it and is left out of the median and rank; `build_peers.py` fails on an unmapped spending code, a missing or duplicate city, or a total outside $500-$8,000 per resident (schools, health and welfare excluded). Administration is a Census catch-all category, so gaps there may reflect reporting. Older survey years list equipment/land (`G`) and transfers by service (`L`/`M`/`S`); `G` is ignored and transfers roll up by prefix so the years are comparable. The optional price adjustment divides each city by its metro's BEA Regional Price Parity (all items), blended over the city's fiscal year (`config/peers.json` has each metro; `src/sd_spend/prices.py`).
- The FY2026 vendor report covers July 2025 to June 2026; the quarterly file in the same series (July-September 2025 only) is not used.
