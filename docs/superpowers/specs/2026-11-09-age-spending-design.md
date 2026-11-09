# Who receives federal dollars, by age and generation

## Intent
Show, for one recent fiscal year, how federal spending on people is spread across age brackets, in dollars per person and in totals, with each bracket labelled by the generation(s) in it. Rough estimates are fine; every number says how it was split. This is national and federal only. It describes who receives money, not who pays, and says nothing about fairness or effectiveness.

## Year
FY2024 (Oct 2023 to Sep 2024). It is the latest year where the age sources line up: VA compensation and pension by age (FY2024), SSA Annual Statistical Supplement (December 2024 data), Census July 2024 population estimates, and the Urban Institute Kids' Share FY2024 cross-check. If a source is missing for FY2024 the fetch step fails; the year is a config value.

## Brackets and generations
- Brackets: 0-17, 18-24, 25-44, 45-64, 65-79, 80+.
- Generations (Pew birth years): Silent up to 1945, Baby Boomers 1946-64, Gen X 1965-80, Millennials 1981-96, Gen Z 1997-2012, Gen Alpha 2013 on.
- A bracket's labels are the generations with at least 10% of the bracket's people born in them. A bracket may carry two labels; no dollar figure is ever split between generations.

## Dollar totals
Each program's total is federal outlays for the year from the Treasury's Monthly Treasury Statement (Fiscal Data API, outlays by budget function and subfunction), so every program ties to the budget. Age sources only decide the split of that total. Medicare and Medicaid are federal share only; Medicaid's federal share is taken from the budget outlay, not from total Medicaid spending.

## Programs, groups and split method
Every program row has `method`: `published` (agency gives dollars or beneficiaries by age), `proxy` (total spread by a stated population), or `study` (split taken from a cited study).

| Group | Program | Split |
|---|---|---|
| Retirement | Social Security (OASDI) | published: SSA beneficiaries and average benefit by age, weighted to the budget total |
| Health | Medicare | published: CMS NHE age and sex shape (2020, latest) applied to the FY2024 total |
| Health | Medicaid and CHIP | published: CMS NHE age shape, as above |
| Veterans | VA compensation and pension | published: VA expenditures by age group, FY2024 |
| Veterans | VA health care and other | proxy: veteran population by age (VA) |
| Kids and education | School meals, Head Start, Title I and IDEA grants | proxy: population aged 3-17 (school-age shares by bracket) |
| Kids and education | Pell grants and student loan subsidies | proxy: enrolment by age (Census CPS school enrolment) |
| Work and family | SNAP, child tax credit, EITC, housing aid | study/proxy as the fetch step finds them; Kids' Share is used where it gives the child share |

A program that cannot be sourced in the fetch step is left out of the page and listed as "not allocated"; it is never guessed silently. Spending not tied to an age (defense, interest, infrastructure, general government) is not allocated.

## Page (site/age.html, nav "Who receives")
1. Headline: per person by bracket, stacked by group, with generation labels under each bracket.
2. Toggle per person / total dollars, group filter, both in the URL hash (`measure=person|total`, `groups=`).
3. Coverage bar: share of total FY2024 federal outlays allocated to an age vs not allocated.
4. Table of the same figures plus a program table with the `method` of each row.
5. Cross-check line: the Kids' Share figures (about $6,860 per child, about $40,050 per person 65+) next to the page's own, to show the estimate is in the same range. Differences are expected: programs and definitions differ.

## Rules
- Words: "received" and "estimated"; the word "effective" appears nowhere on the page; no ranking of fairness.
- Each program's age split sums to its budget total within rounding or the build fails.
- Coverage share must be between 0 and 100%; every bracket population must be positive; per-person values must be plausible (below $100,000) or the build fails.
- CMS shape is from 2020 and is labelled as such.
- Raw files go in `data/raw` with MANIFEST entries; the fetch step uses an honest user agent and never works around a bot check (blocked sources are downloaded by the user).
- CI has no poppler: tests that need `pdftotext` skip, and the data tests read the committed `site/data/age-spending.json`.

## Out of scope
State spending and state differences, taxes paid or net benefits, lifetime or cohort views, county or San Diego slices, other years, and any ranking of fairness or effectiveness.

## Risks the build must handle
- A source file changes layout: parsers fail loudly rather than return partial tables.
- SSA discontinued some tables: the build uses the retired-worker, disabled-worker and survivor tables that exist and states what is missing.
- Medicaid federal share varies by state; the national outlay is used and disclosed.
