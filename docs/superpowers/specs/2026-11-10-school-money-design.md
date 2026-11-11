# Where school money goes (San Diego County school districts)

## Intent
Show what the school districts in San Diego County spend each general-fund dollar on (teacher pay, other staff pay, pensions, health benefits, supplies, services), per student and by district, and where the money comes from (state aid, local property tax, federal). It describes spending; it says nothing about whether any amount is too much or too little.

## Source
California Department of Education, SACS unaudited actual data for 2023-24 (`sacs2324.exe`, a zip holding a Microsoft Access database). The fetch step unzips it and exports tables with `mdbtools`; only San Diego County (county code 37) rows of the ledger, the district list with average daily attendance, and the code-title tables are stored in `data/raw/cde/` with MANIFEST entries pointing at the state's file. The 480MB database is not stored.

## Scope
- All 42 school districts in San Diego County plus the County Office of Education, 2023-24 (July 2023 to June 2024).
- Headline: the general fund (fund 01), expenditures only (object codes 1000-7499; transfers between a district's own funds are left out).
- Other funds (building, bond repayment, cafeteria, child development, adult education and so on) are listed with their totals, not mixed into the headline, because construction and debt would distort the operating picture.
- Charter schools that file their own reports are not in district ledgers; charter money that passes through a district shows as a property-tax transfer.

## Views
1. Each dollar by category: salaries (teachers; pupil support; certificated administrators; other certificated; classroom aides; classified support; classified supervisors; office and technical; other classified), benefits (teacher pensions paid by the district; teacher pensions paid by the state on the district's behalf; staff pensions; Social Security and Medicare; health and welfare; unemployment and workers' compensation; retiree health; other), and everything else (books and supplies; contracted services; other services and operating costs; capital outlay; tuition, transfers to other agencies and debt service).
2. By purpose (SACS function): classroom instruction, special education instruction, instructional support, school administration, pupil services, pupil transportation, district administration, buildings and maintenance, other.
3. Where the money comes from (general-fund revenue): state aid, local property taxes, property-tax transfers to charter schools, federal, other state, other local.
4. Every district: students (average daily attendance), general-fund spending per student, share on salaries and on benefits.
A district picker (in the URL hash) switches views 1-3 between the county and one district. Dollars, share and dollars per student are all shown.

## Rules
- Every general-fund expenditure row falls in exactly one category and one purpose or the build fails; categories add up to the district total.
- The build fails if the county general-fund total is outside $6-10 billion, if salaries plus benefits are outside 70-92% of it, or if fewer than 40 districts have data.
- Per-student figures use the state's K-12 average daily attendance, which leaves out charter students reported in a charter's own funds; the County Office of Education has no attendance figure and shows no per-student number.
- Words: "spent", "went to"; never "waste", "effective" or "deserve".
- CI has neither `mdbtools` nor the database: tests run on the stored extracts and the committed JSON.

## Out of scope
Other counties, other years, school-site level spending, salaries per employee or headcounts (the ledger has dollars only), and outcomes.
