import io

import pytest

from sd_spend.caspend import (CaSpendError, parse_calworks_persons, parse_dds_ages, parse_department_programs, parse_ihss_ages,
                              parse_schedule9, parse_ssi_state_ages, parse_state_population, state_funds)

SCH9 = """
                                                                 Actual 2023-24                                   Estimated 2024-25
                                           General        Special       Selected       Budget        Federal        General
HEALTH AND HUMAN SERVICES
  4260-State Department of Health Care Services
     State Operations                          100             50             --          150             10            999
  Totals,4260-State Department of Health Care Services   $38,000        $22,000             --      $60,000        $96,000        $38,479
  6305-Retirement Costs for Community Colleges
  Totals, 6305-Retirement Costs for Community Colleges     - $295               --               --      - $295              --      - $314
TOTALS, HEALTH AND HUMAN
                                              $70,000        $38,000             --     $108,000       $111,000        $75,000
SERVICES
TOTALS, EDUCATION                             $91,000           $500         $1,500      $93,000        $14,000       $107,000
GRAND TOTAL                                  $207,000        $92,000         $5,000     $304,000       $150,000       $232,000
"""


def test_schedule9_reads_department_and_section_totals_for_the_actual_year():
    got = parse_schedule9(SCH9)
    assert got["4260"] == {"name": "State Department of Health Care Services", "general": 38_000_000.0, "special": 22_000_000.0,
                           "bond": 0.0, "total": 60_000_000.0, "federal": 96_000_000.0}
    assert got["6305"]["general"] == -295_000.0 and got["6305"]["federal"] == 0.0
    assert got["TOTALS, HEALTH AND HUMAN SERVICES"]["total"] == 108_000_000.0
    assert got["TOTALS, EDUCATION"]["bond"] == 1_500_000.0
    assert got["GRAND TOTAL"]["total"] == 304_000_000.0


def test_schedule9_fails_when_a_total_is_not_the_sum_of_its_funds():
    with pytest.raises(CaSpendError, match="add up"):
        parse_schedule9(SCH9.replace("$60,000 ", "$61,000 "))


def test_schedule9_fails_without_a_grand_total():
    with pytest.raises(CaSpendError, match="GRAND TOTAL"):
        parse_schedule9(SCH9.replace("GRAND TOTAL", "SOME TOTAL"))


DEPT = """
DETAILED EXPENDITURES BY PROGRAM
                                                                 2023-24*       2024-25*       2025-26*
             PROGRAM REQUIREMENTS
  4270       WELFARE PROGRAMS
             State Operations:
  0001       General Fund                                          $999            $1             $1
             SUBPROGRAM REQUIREMENTS
  4270010    CalWORKs
             State Operations:
  0001       General Fund                                           $20            $28            $25
  0890       Federal Trust Fund                                      41             41             42
  0995       Reimbursements                                         -10            846            846
                 Totals, State Operations                           $51            $70            $69
             Local Assistance:
  0001       General Fund                                        $1,480         $1,304         $1,442
  0890       Federal Trust Fund                                   3,027          3,707          3,165
* Dollars in thousands, except in Salary Range.
2025-26 GOVERNOR'S BUDGET - HHS 8                                  HEALTH AND HUMAN SERVICES
                           5180 Department of Social Services - Continued
                                                                 2023-24*       2024-25*       2025-26*
  8075       School Supplies Fund                                     7              -              -
                 Totals, Local Assistance                        $4,514         $5,012         $4,608
             SUBPROGRAM REQUIREMENTS
  4270028    SSI/SSP
             Local Assistance:
  0001       General Fund                                        $3,545         $3,587         $3,581
             TOTALS, EXPENDITURES
             State Operations                                       955          1,076          1,083
"""


def test_department_programs_sum_funds_per_subprogram_across_page_breaks():
    got = parse_department_programs(DEPT)
    assert got["CalWORKs"] == {"0001": 1_500_000.0, "0890": 3_068_000.0, "0995": -10_000.0, "8075": 7_000.0}
    assert got["SSI/SSP"] == {"0001": 3_545_000.0}
    assert "WELFARE PROGRAMS" not in got


def test_state_funds_leave_out_federal_money_and_reimbursements():
    assert state_funds({"0001": 1_500.0, "0890": 3_068.0, "0995": -10.0, "8075": 7.0}) == 1_507.0


def test_department_programs_fail_without_the_program_table():
    with pytest.raises(CaSpendError, match="DETAILED EXPENDITURES"):
        parse_department_programs("nothing here")


POP = "SUMLEV,REGION,DIVISION,STATE,NAME,SEX,AGE,POPEST2024_CIV\n" + "".join(
    f"040,4,9,6,California,0,{a},{100 + a}\n" for a in range(86)) + "040,4,9,6,California,0,999,99999\n040,4,9,6,California,1,0,5\n040,3,5,12,Florida,0,0,7\n"


def test_state_population_reads_one_state_both_sexes_and_stops_at_85():
    got = parse_state_population(POP, "6", 2024)
    assert got[0] == 100 and got[85] == 185 and len(got) == 86


def test_state_population_fails_when_an_age_is_missing():
    with pytest.raises(CaSpendError, match="age 40"):
        parse_state_population(POP.replace("California,0,40,140\n", ""), "6", 2024)


def test_dds_ages_average_the_months_and_add_the_genders():
    text = "Period,Age,gender,Population\n" + "".join(
        f"{m},{age},{g},{n}\n" for m in ("2023-07", "2023-08") for age in ("Ages 00-02", "Ages 62-99")
        for g, n in (("Female", 10), ("Male", 30), ("Unknown", "*"))) + "2022-01,Ages 00-02,Male,999\n"
    assert parse_dds_ages(text, ["2023-07", "2023-08"]) == {"0-2": 40.0, "62-99": 40.0}


def test_dds_ages_fail_when_a_month_is_missing():
    with pytest.raises(CaSpendError, match="2023-09"):
        parse_dds_ages("Period,Age,gender,Population\n2023-07,Ages 00-02,Male,5\n", ["2023-07", "2023-09"])


def book(sheets):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


IHSS_HEAD = ["Table 1", "0-17 yrs  (Minors)", None, "18-44 yrs", None, "45 to 64 yrs", None, "65 to 74 yrs", None, "75 to 84 yrs", None, "85+ yrs", None]


def test_ihss_ages_read_the_statewide_row():
    data = book({"Age Gender": [["Age Groups"], [None, *IHSS_HEAD], [], [None, "Statewide", 70, .1, 110, .1, 150, .2, 160, .2, 150, .2, 110, .1]]})
    assert parse_ihss_ages(data) == {"0-17": 70, "18-44": 110, "45-64": 150, "65-74": 160, "75-84": 150, "85+": 110}


def test_ihss_ages_fail_without_a_statewide_row():
    with pytest.raises(CaSpendError, match="Statewide"):
        parse_ihss_ages(book({"Age Gender": [[None, *IHSS_HEAD], [None, "Alameda", 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]]}))


def calworks_book(children=(10, 20, 30, 40, 50), adults=(10, 2, 30), months=12):
    head = ["Date", "County Name", " ", "County Code", "SFY", "FFY", "Report Month", *[str(n) for n in range(1, 82)]]
    rows = [["x"], ["x"], ["x"], ["x"], head]
    for m in range(months):
        cells = [0] * 81
        cells[68:73] = children
        cells[73:76] = adults
        cells[76:81] = ["*"] * 5  # total persons are suppressed in places, so they are not used
        rows.append([f"m{m}", "Statewide", None, 0, "2023-24", 2023, f"m{m}", *cells])
        rows.append([f"m{m}", "Alameda", None, 1, "2023-24", 2023, f"m{m}", *["*"] * 81])
    return book({"Data_External": rows})


def test_calworks_persons_sum_children_and_adults_over_the_year():
    assert parse_calworks_persons(calworks_book(), "Statewide") == {"children": 150 * 12, "adults": 42 * 12}


def test_calworks_persons_skip_a_month_with_a_suppressed_cell():
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(calworks_book()))
    wb["Data_External"].cell(row=6, column=7 + 69).value = "*"
    buf = io.BytesIO()
    wb.save(buf)
    assert parse_calworks_persons(buf.getvalue(), "Statewide") == {"children": 150 * 11, "adults": 42 * 11}


def test_calworks_persons_fail_on_a_missing_month_a_suppressed_count_or_too_many_adults():
    with pytest.raises(CaSpendError, match="12 months"):
        parse_calworks_persons(calworks_book(months=11), "Statewide")
    with pytest.raises(CaSpendError, match="fully reported"):
        parse_calworks_persons(calworks_book(), "Alameda")
    with pytest.raises(CaSpendError, match="fewer adults"):
        parse_calworks_persons(calworks_book(adults=(500, 2, 30)), "Statewide")


def test_ssi_state_ages_read_one_state():
    data = book({"Table 10": [["x"], ["State or area", "Total", "Category", "Age"], ["Aged", "Blind", "Disabled", "Under 18", "18–64", "65 or older"],
                              ["California", 1000, 300, 10, 690, 100, 400, 500], ["Nevada", 10, 1, 1, 8, 1, 5, 4]]})
    assert parse_ssi_state_ages(data, "California") == {"0-17": 100, "18-64": 400, "65+": 500}
    with pytest.raises(CaSpendError, match="Oregon"):
        parse_ssi_state_ages(data, "Oregon")
