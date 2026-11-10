import pytest

from sd_spend.agespend import AgeSpendError, parse_cms_shares, parse_mts_outlays, parse_population, parse_va_ages


def mts(rows):
    return {"data": [{"classification_id": cid, "parent_id": pid, "classification_desc": desc,
                      "current_fytd_rcpt_outly_amt": amt} for cid, pid, desc, amt in rows]}


OUTLAYS = [("9", "null", "Net Outlays", "null"), ("1", "9", "Social Security", "60.0"),
           ("2", "9", "Medicare", "30.0"), ("3", "9", "Net Interest", "10.0"), ("4", "9", "Total", "100.0"),
           ("5", "8", "Individual Income Taxes", "999.0")]


def test_mts_outlays_take_only_the_net_outlays_children():
    assert parse_mts_outlays(mts(OUTLAYS)) == {"Social Security": 60.0, "Medicare": 30.0, "Net Interest": 10.0, "Total": 100.0}


def test_mts_outlays_fail_when_lines_do_not_add_to_total():
    rows = [r if r[2] != "Total" else (r[0], r[1], r[2], "150.0") for r in OUTLAYS]
    with pytest.raises(AgeSpendError, match="add up"):
        parse_mts_outlays(mts(rows))


def test_mts_outlays_fail_without_net_outlays():
    with pytest.raises(AgeSpendError, match="Net Outlays"):
        parse_mts_outlays(mts(OUTLAYS[1:]))


POP = "SEX,AGE,POPESTIMATE2023,POPESTIMATE2024\n0,0,10,11\n0,1,20,22\n0,2,5,6\n1,0,5,6\n2,0,5,5\n"


def test_population_uses_both_sexes_rows_for_the_year():
    assert parse_population(POP, 2024, max_age=2) == {0: 11, 1: 22, 2: 6}


def test_population_fails_for_a_missing_age_or_year():
    with pytest.raises(AgeSpendError, match="age 3"):
        parse_population(POP, 2024, max_age=3)
    with pytest.raises(AgeSpendError, match="2019"):
        parse_population(POP, 2019, max_age=2)


CMS = ("Payer,Service,Age Group,Sex,2018,2020\n"
       "Medicare,Total Personal Health Care,Total,Total,100,100\n"
       "Medicare,Total Personal Health Care,0-18,Total,0,10\n"
       "Medicare,Total Personal Health Care,19-44,Total,0,30\n"
       "Medicare,Total Personal Health Care,45-64,Total,0,60\n"
       "Medicare,Hospital Care,0-18,Total,1,1\n")


def test_cms_shares_sum_to_one_per_payer():
    groups = ("0-18", "19-44", "45-64")
    assert parse_cms_shares(CMS, "2020", ("Medicare",), groups) == {"Medicare": {"0-18": 0.1, "19-44": 0.3, "45-64": 0.6}}


def test_cms_shares_fail_when_groups_do_not_match_total():
    bad = CMS.replace("Total,Total,100,100", "Total,Total,100,500")
    with pytest.raises(AgeSpendError, match="do not add up"):
        parse_cms_shares(bad, "2020", ("Medicare",), ("0-18", "19-44", "45-64"))


VA = ("State & Foreign,Compensation Recipients,Estimated Monthly Compensation Costs,Estimated Annual Compensation Costs,"
      "Compensation Veterans Age 34 and under,Compensation Veterans Age 35 - 54,Compensation Veterans Age 55-74,"
      "Compensation Veterans Age 75 and over,Compensation Veterans Age Unknown\n"
      "Alabama,10,\"[$$]1,000\",\"[$$]12,000\",1,2,3,4,0\n"
      "Grand Total,20,\"[$$]2,000\",\"[$$]24,000\",2,4,6,7,1\n")


def test_va_ages_read_the_grand_total_row():
    got = parse_va_ages(VA, "Compensation")
    assert got == {"recipients": 20, "dollars": 24000.0, "bands": {"34 and under": 2, "35-54": 4, "55-74": 6, "75 and over": 7}, "unknown": 1}


def test_va_ages_fail_when_bands_do_not_match_recipients():
    with pytest.raises(AgeSpendError, match="recipients"):
        parse_va_ages(VA.replace("2,4,6,7,1", "2,4,6,70,1"), "Compensation")


from sd_spend.agespend import parse_omb_line, parse_ssa_ages, ssa_annual_dollars

SSA = """Table 5.A1.2—Disabled-worker beneficiaries: Number and average monthly benefit, by age and sex,
December 2024
Age                                    Number          benefit (dollars)
      Total                          7,231,147                1,580.79
Under 20                                   667                  689.37
20–24                                   24,897                  891.62
  20                                     1,335                  751.96
  21                                     2,633                  802.01
65–66                                  922,518                1,757.61
  65                                   552,383                1,756.39
SOURCE: Social Security Administration.
Table 5.A1.3—Spousal
  20                                   999                  1.00
"""


def test_ssa_rows_are_read_until_the_source_line_and_exclude_the_total():
    rows = parse_ssa_ages(SSA, "Table 5.A1.2")
    assert [(r["lo"], r["hi"]) for r in rows] == [(19, 19), (20, 24), (20, 20), (21, 21), (65, 66), (65, 65)]
    assert rows[0]["number"] == 667 and rows[0]["avg"] == 689.37


def test_ssa_dollars_use_single_years_and_groups_only_where_no_single_year_follows():
    dollars = ssa_annual_dollars(parse_ssa_ages(SSA, "Table 5.A1.2"))
    assert dollars == [(19, 667 * 689.37 * 12), (20, 1335 * 751.96 * 12), (21, 2633 * 802.01 * 12), (65, 552383 * 1756.39 * 12)]


def test_ssa_table_must_be_found():
    with pytest.raises(AgeSpendError, match="Table 9.9"):
        parse_ssa_ages(SSA, "Table 9.9")


def test_omb_line_reads_the_requested_year():
    import io, openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Table 3.2"]); ws.append(["(in millions of dollars)"])
    ws.append(["Function and Subfunction", "2023", "2024"])
    ws.append(["501 Elementary, secondary, and vocational education", 100.0, 105.0])
    buf = io.BytesIO(); wb.save(buf)
    assert parse_omb_line(buf.getvalue(), "501 Elementary", 2024) == 105.0e6
    with pytest.raises(AgeSpendError, match="999 Missing"):
        parse_omb_line(buf.getvalue(), "999 Missing", 2024)


def test_nhe_federal_medicaid_is_read_in_billions():
    import io, openpyxl
    from sd_spend.agespend import parse_nhe_federal_medicaid
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Table 5-3"]); ws.append([" ", 2023, 2024])
    ws.append(["     Federal Portion of Medicaid Payments", 592.6, 596.7])
    ws.append(["     Federal Portion of Medicare Buy-in Premiums", 1.0, 2.0])
    buf = io.BytesIO(); wb.save(buf)
    assert parse_nhe_federal_medicaid(buf.getvalue(), 2024) == 596.7e9
    with pytest.raises(AgeSpendError, match="2019"):
        parse_nhe_federal_medicaid(buf.getvalue(), 2019)
