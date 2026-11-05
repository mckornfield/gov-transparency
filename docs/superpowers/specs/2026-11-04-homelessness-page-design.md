# Homelessness: dollars per person and reported outcomes

## Intent
Show what the City of San Diego and the State of California spend on homelessness per person counted, next to the outcomes the state reports, for San Diego against LA, San Francisco and San José, and (if the data can be fetched) similar US cities. Outcomes are labelled "reported", never "effective": nothing here shows cause and effect.

## Sources (all raw files go in `data/raw` with MANIFEST entries, like the existing sources)
| Source | Use | Status |
|---|---|---|
| Cal ICH "CA System Performance Measures, Statewide and by CoC" CSV + data dictionary (data.ca.gov API, CKAN `package_search`) | People served (M1a), first-time (M2), exits to permanent housing (M3), days homeless (M4), returns within 6 months (M5), outreach placements (M6), point-in-time count, 2020-2025 | Fetched OK |
| HCD HHAP allocation PDFs, rounds 1 (redirected), 2, 3, 4, 5 | State grant dollars awarded to the San Diego CoC, city and county, and to the comparison regions | Fetched OK |
| City of San Diego adopted budgets, Homelessness Strategies and Solutions Department | City dollars, FY2024 actual and FY2025/26 budget | Fetched OK |
| HUD AHAR point-in-time counts by CoC (2007-2024/25) | Counts for out-of-state peer cities | **Blocked** (bot check); needs a manual download by the user |
| State Auditor report 2023-102.2 | Caveat text only (the city cannot total its own homelessness spending) | Linked, not parsed |

## What the page shows
1. Dollars per person counted and per resident, by year: city (one department line, a floor) and state (HHAP awards, a floor), kept separate, never summed with other programs.
2. Point-in-time count trend, San Diego against LA, San Francisco, San José, and the state.
3. Reported outcomes 2020-2025: exits to permanent housing as a share of people served, days homeless, returns to homelessness.
4. Peer US cities (counts per 1,000 residents only) once the HUD file is supplied. Peer dollars are not shown: Census finance data has no homelessness function, so spending is not comparable.

## Rules
- HHAP figures are awards, not spending; labelled as such. Rounds overlap in time, so they are shown per round, not per fiscal year.
- 2021 counts are blank (waived); the page shows the gap, not an interpolation.
- Builds fail on unparseable PDFs, a missing region, or an implausible value, like the existing pipeline.
- The Auditor's finding goes in the methods text. Outcome text states the data cannot show cause and effect.

## Out of scope
Homekey and encampment grants, county and nonprofit spending, peer-city dollars, any ranking of "effectiveness".

## Open dependency
The peer-city view needs the HUD "2007-2024 Point-in-Time Estimates by CoC" workbook, downloaded by the user in a browser. Without it the page ships with California regions only.
