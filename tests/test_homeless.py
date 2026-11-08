import pandas as pd
import pytest

from sd_spend.homeless import HomelessError, parse_budget, parse_hhap, parse_spm, pit_rows

SPM = """﻿Location,Metric,Jan 2020 - Dec 2020,Jan 2021 - Dec 2021,April 2025 - March 2026
California,M1a,289823,306390,423541
CA-601 San Diego City & County CoC,M1a,27370,28481,33668
CA-601 San Diego City & County CoC,PIT Count,7638,N/A,N/A
CA-601 San Diego City & County CoC,M5,0.118,0.086,0.091
"""


def test_spm_keeps_na_as_missing_not_zero_and_extracts_coc_id():
    t = parse_spm(SPM)
    pit = t[(t.metric == "PIT Count") & (t.coc_id == "CA-601")].set_index("period")["value"]
    assert pit["Jan 2020 - Dec 2020"] == 7638 and pd.isna(pit["Jan 2021 - Dec 2021"])
    assert t[t.location == "California"].coc_id.isna().all()


def test_spm_blank_cells_are_missing_too():
    t = parse_spm(SPM + "CA-509 Mendocino County CoC,M6,,5,6\n")
    assert t[t.coc_id == "CA-509"].value.isna().sum() == 1


def test_spm_rejects_unknown_metric_and_garbage_values():
    with pytest.raises(HomelessError, match="M9"):
        parse_spm(SPM + "California,M9,1,2,3\n")
    with pytest.raises(HomelessError, match="abc"):
        parse_spm(SPM + "California,M2,abc,2,3\n")


HHAP = """
                                       ROUND 5 ALLOCATIONS
CONTINUUM OF CARE                              ALLOCATION        CITY            ALLOCATION        COUNTY            ALLOCATION
Glendale CoC                                  $280,408.11        San Diego       $29,918,593.27    Fresno            $5,259,127.81
San Diego City and County CoC                $14,759,532.30      San Francisco   $22,100,815.88    San Diego         $14,160,463.76
Redding/Shasta, Siskiyou, Lassen
                                              $3,625,173.51
Counties CoC                                                                                       Alpine            $          -
"""


def test_hhap_assigns_amounts_to_the_coc_city_and_county_columns():
    t = parse_hhap(HHAP, "Round 5")
    sd = t[t.name == "San Diego"].set_index("kind")["amount"]
    assert sd["city"] == 29918593.27 and sd["county"] == 14160463.76
    assert t[(t.kind == "coc") & (t.name == "San Diego City and County CoC")].amount.iloc[0] == 14759532.30
    assert t[(t.kind == "county") & (t.name == "Alpine")].amount.iloc[0] == 0


def test_hhap_requires_san_diego_in_every_column():
    with pytest.raises(HomelessError, match="county"):
        parse_hhap(HHAP.replace("San Diego         $14,160,463.76", "Other             $14,160,463.76"), "Round 5")


BUDGET = """
                                                  FY2024                FY2025           FY2026         FY2025-2026
                                                   Actual               Budget          Adopted             Change
Personnel Expenditures                     $    2,492,663 $       2,689,193 $      3,205,362 $       516,169
Total Department Expenditures              $   42,114,403 $      53,916,571 $     53,821,132 $       (95,439)
Total Department Revenue                   $   34,561,306 $      40,837,415 $     53,189,289 $    12,351,874
"""


def test_budget_reads_actual_budget_and_adopted_columns_by_header_year():
    b = parse_budget(BUDGET)
    assert b["expenditures"] == {2024: 42114403, 2025: 53916571, 2026: 53821132}
    assert b["revenue"][2024] == 34561306
    assert b["actual_year"] == 2024


def test_budget_without_the_totals_fails():
    with pytest.raises(HomelessError):
        parse_budget("nothing here")


def test_waived_counts_are_missing_but_carried_over_unsheltered_counts_are_kept_and_flagged():
    rows = {2021: [("CA-601", "Sheltered-Only Count", 4143.0, 4143.0, 0.0),
                   ("CA-600", "Sheltered and Unsheltered Count", 70000.0, 20000.0, 50000.0),
                   ("CA-500", "Sheltered and Partial Unsheltered Count", 9000.0, 3000.0, 6000.0),
                   ("CA-501", "Sheltered-Only Count", 8124.0, 2944.0, 5180.0)]}
    t = pit_rows(rows, ["CA-601", "CA-600", "CA-500", "CA-501"]).set_index("coc_id")
    assert pd.isna(t.loc["CA-601", "total"]) and pd.isna(t.loc["CA-500", "total"])  # no unsheltered count at all
    assert t.loc["CA-600", "total"] == 70000 and not t.loc["CA-600", "carried"]
    # HUD reuses the last unsheltered count in a year the CoC only counted shelters
    assert t.loc["CA-501", "total"] == 8124 and t.loc["CA-501", "carried"]


def test_pit_rows_names_a_missing_coc():
    with pytest.raises(HomelessError, match="CA-999"):
        pit_rows({2024: [("CA-601", "Sheltered and Unsheltered Count", 1.0, 1.0, 0.0)]}, ["CA-601", "CA-999"])
