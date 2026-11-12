# Who receives local dollars in San Diego, by age

## Intent
Show how the local governments that serve a resident of the City of San Diego (school districts, the County of San Diego, the City of San Diego) spend on people across age brackets, each government shown separately, in the same form as the federal and California pages. Rough estimates are fine; every row says how it was split. It describes who receives money, not who pays, and says nothing about fairness.

## Counting rule: by who spends, source marked
- Each government's dollars are what that government spends, whoever paid for it. The state and federal money inside those budgets is marked per row ("paid for by"), not removed.
- Consequence, stated on the page: this page overlaps the California and federal pages (state school aid is on the California page as state spending and here as school district spending). The three pages cannot be added together.

## Governments, years, dollars
| Government | Dollars | Year | Source |
|---|---|---|---|
| School districts (the 42 districts and the County Office of Education) | General-fund spending | 2023-24 actuals | `site/data/schools.json` (California Department of Education ledger) |
| County of San Diego | Adopted budget by program | 2024-25 adopted budget (the earliest year in the county's open-budget data; it publishes no actuals as data) | data.sandiegocounty.gov "Open Budget Exp" and "Open Budget Rev" |
| City of San Diego | Adopted budget by department | Fiscal year 2025 adopted budget (city actuals as data stop at 2023) | `data/processed/spending.csv` |

The years differ and the page says so. The county budget total includes transfers between its own funds.

## Brackets and population
Same five brackets and generation labels as the other age pages. Population: Census Bureau July 2024 estimate for San Diego County by single year of age (top-coded at 85). School and county dollars are divided by county residents; city dollars by City of San Diego residents (State Controller figure). The per-person stack therefore describes a resident of the City of San Diego; residents of other cities have their own city's spending, which is not here.

## Programs and split
| Government | Program | Split |
|---|---|---|
| School districts | K-12 general-fund spending | proxy: ages 4-18 by population |
| County | Child welfare, foster care and adoptions (Child and Family Well-Being) | proxy: all to ages 0-17 |
| County | In-Home Supportive Services | proxy: statewide recipients in six age groups (no county figures by age) |
| County | Adult protective and senior services | proxy: ages 60 and over by population |
| County | Cash aid (assistance payments, mostly CalWORKs) | published: children and adults in San Diego County CalWORKs cash-grant cases |
| County | Benefits eligibility offices | proxy: San Diego County Medi-Cal eligibles by age |
| County | Mental health services (including inpatient) | proxy: county behavioral health clients by age, 2024-25, equal cost per client |
| County | Alcohol and drug services | proxy: county substance-use clients by age, 2024-25, equal cost per client |
| County | California Children's Services | proxy: ages 0-20 by population |
| County | County library and parks | proxy: evenly across county residents |
| City | Library; Parks and Recreation | proxy: evenly across city residents |

Not allocated, each listed with a reason: sheriff, jails, courts and probation (as on the California page); public health; homelessness and housing; administration; roads, land use and general government; capital; and for the city police, fire, water and sewer, streets and the rest.

## Page (`site/san-diego-age.html`, nav "Who receives local dollars")
Shared age-page code. The group filter is the government. Per person / total toggle. Tables: brackets; programs (with "paid for by" shares of state, federal, local and other money where the source publishes them); governments (year, total, share placed by age); what is not given an age.

## Rules
- "Received" and "estimated"; never "effective", "deserve" or "waste".
- Every split sums to its program total or the build fails; parsers fail loudly; allocated plus not allocated equals each government's total; per-person values over $100,000 fail the build.
- Raw files in `data/raw` with MANIFEST entries; honest user agent; no working around bot checks.
- CI has no poppler: data tests read the committed JSON.

## Known weak points, disclosed
- Mixed years and budget versus actuals.
- Behavioral health is split by client counts, not cost.
- Independent charter schools are not in the district ledger rows used.
- The city has almost nothing that can be tied to an age; its two rows are spread evenly.
