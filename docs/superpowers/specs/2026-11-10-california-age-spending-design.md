# Who receives California state dollars, by age

## Intent
Show, for one state fiscal year, how the State of California's own spending on people is spread across age brackets, per person and in total, in the same form as the federal page so the two compare. Rough estimates are fine; every row says how it was split. It describes who receives money, not who pays, and says nothing about fairness or effectiveness. A San Diego page (city, county and school districts, by who spends, with the funding source marked) follows as a separate spec and reuses these sources, several of which are published by county.

## Year, brackets, population
- State fiscal year 2023-24 (July 2023 to June 2024), actuals as printed in the 2025-26 Governor's Budget.
- The same five brackets as the federal page (0-18, 19-44, 45-64, 65-84, 85+) with the same generation labels (labels only; dollars are never cut by generation).
- Population: Census Bureau July 2024 estimate for California by single year of age (civilian population file, ages top-coded at 85).

## Dollars: by who spends, source marked, no double counting
- Counted here: state funds only, as Schedule 9 of the Governor's Budget classifies them (General Fund, special funds, selected bond funds). This includes state money sent to school districts and counties.
- Not counted here: federal funds (they are on the federal page) and reimbursements between departments. The page shows, for information, the federal funds that flow through the same departments.
- Local money (for example the property-tax share of school funding) belongs to the San Diego page, not here.
- Department totals come from Schedule 9. Programs inside the Department of Social Services come from its Governor's Budget page ("Detailed expenditures by program", which lists every fund), using the same fund classification; the build checks that a department's programs do not add up to more than its Schedule 9 state funds.

## Programs and split method
Each row is `published` (the agency gives recipients or dollars by age) or `proxy` (spread by a stated population).

| Group | Program (source of dollars) | Age split |
|---|---|---|
| Schools | K-12 education, Department of Education (Schedule 9) | proxy: ages 4-18 by population (includes transitional kindergarten and state preschool) |
| Higher education | UC, CSU, Student Aid Commission (Schedule 9) | proxy: ages 18-29 by population |
| Higher education | Community colleges (Schedule 9) | proxy: ages 18-39 by population |
| Health | Medi-Cal and other state health care programs, state share (Department of Health Care Services, Schedule 9) | proxy: CMS national age shape of Medicaid spending (2020), as on the federal page. The whole department's state funds are used (it is almost all Medi-Cal). Medi-Cal eligibles by age and county (DHCS) are left for the San Diego page |
| Disability and care | Developmental services (Schedule 9) | published: DDS consumers by age group, spread within groups by population |
| Disability and care | In-Home Supportive Services, state share (CDSS budget page) | published: CDSS recipients in six age groups |
| Income support | SSI state supplement (CDSS budget page) | published: SSA SSI report, California recipients under 18, 18-64, 65 and over |
| Income support | CalWORKs (CDSS budget page) | published: CDSS children and adults in cash-grant cases; children over 0-17, adults over 18-49 by population |
| Children | Child care (CDSS budget page) | proxy: ages 0-12 by population |

Not allocated, each named on the page with its reason: prisons (ages of the incarcerated exist, but they are not recipients in this page's sense), retiree pensions and retiree health (pay for past work), transportation, courts, natural resources, general government, and any people-directed program without a fetchable age source. A program that cannot be sourced is left out and listed, never guessed.

## Page (site/california-age.html, nav "Who receives state dollars")
Same layout and model code as the federal page: stacked per-person chart with generation labels, per person / total toggle, group filter, both in the URL hash, band table and program table with methods. Two coverage figures: against all state-funds spending, and against spending on people (Schedule 9 totals for Health and Human Services plus Education). One extra line: federal funds flowing through the same departments, counted on the federal page.

## Rules
- "Received" and "estimated"; never "effective" or "deserve"; no ranking of fairness.
- Every split sums to its program total or the build fails; parsers fail loudly on an unrecognised layout; per-person values over $100,000 fail the build; allocated must be less than people-directed spending, which must be less than total state funds.
- Raw files go in `data/raw` with MANIFEST entries; honest user agent; no working around bot checks.
- CI has no poppler: data tests read the committed JSON; tests that need `pdftotext` skip.

## Out of scope
Federal funds, local government spending (next spec), taxes paid or net benefits, other years, counties other than as raw material for the San Diego page.

## Known weak points, disclosed on the page
- Medi-Cal uses a national, 2020 age shape and the state share differs by eligibility group.
- Higher-education and child-care rows are population proxies.
- Schedule 9 counts some federally derived special funds (for example the home and community-based services American Rescue Plan fund) as state special funds; the page follows Schedule 9 and says so.
- The population file is civilian residents, so brackets with many service members are slightly undercounted.
