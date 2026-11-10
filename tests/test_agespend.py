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


from sd_spend.agespend import parse_fns_costs, parse_snap_ages

SNAP = """Table A.23. SNAP participants by sex and selected demographic characteristics

                                      Total participants         Female participants     Male participants
 Participant characteristic          (000)      Column %hh       (000)       Row %hh    (000)       Row %hh
 Total                              40,065         100.0        22,952        57.3     17,113        42.7
 Age
  Child                             15,575          38.9         7,671        19.1      7,904        19.7
    Preschool-age                    4,464          11.1         2,216         5.5      2,248         5.6
    School-age                      11,111          27.7         5,455        13.6      5,656        14.1
  Non-elderly adult                 16,684          41.6        10,442        26.1      6,242        15.6
    18–35 years                      7,843          19.6         5,144        12.8      2,699         6.7
    36–59 years                      8,840          22.1         5,297        13.2      3,543         8.8
  Elderly individual                 7,807          19.5         4,840        12.1      2,967         7.4
 Citizenship
"""


def test_snap_ages_read_children_two_adult_groups_and_elderly_in_thousands():
    assert parse_snap_ages(SNAP) == {"0-17": 15_575_000, "18-35": 7_843_000, "36-59": 8_840_000, "60+": 7_807_000}


def test_snap_ages_must_add_to_the_total():
    with pytest.raises(AgeSpendError, match="participants"):
        parse_snap_ages(SNAP.replace("7,807 ", "9,807 "))


FNS = """Table 1: Total FNS Cost -- All Programs 1/
FY 2024
 Oct 2023 7 3 1 1 1 1 1 1 -- 15
Total 100,339,677,729 28,983,954,219 4,691,793 7,315,132,348 384,025,547 2,594,600,944 168,739,228 3,007,343,776 -- 142,798,165,584
Total 4 Months 1 2 3 4 5 6 7 8 -- 9
"""


def test_fns_costs_read_snap_child_nutrition_and_wic_for_the_year():
    assert parse_fns_costs(FNS, "FY 2024") == {"SNAP": 100_339_677_729.0, "Child nutrition": 28_983_954_219.0, "WIC": 7_315_132_348.0, "Total": 142_798_165_584.0}


def test_fns_costs_fail_when_columns_do_not_add_to_the_total():
    with pytest.raises(AgeSpendError, match="add up"):
        parse_fns_costs(FNS.replace("142,798,165,584", "152,798,165,584"), "FY 2024")


def test_hud_housing_reads_units_spending_and_head_age_shares():
    import io, openpyxl
    from sd_spend.agespend import parse_hud_housing
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["program", "program_label", "total_units", "spending_per_month", "pct_lt24_head", "pct_age25_50", "pct_age51_61", "pct_age62plus", "pct_age85plus"])
    ws.append([1, "Summary of All HUD Programs", 1000, 1000, 10, 40, 20, 30, 5])
    ws.append([2, "Public Housing", 1, 1, 1, 1, 1, 1, 1])
    buf = io.BytesIO(); wb.save(buf)
    got = parse_hud_housing(buf.getvalue())
    assert got == {"dollars": 12_000_000.0, "heads": {"24 and under": 10, "25-50": 40, "51-61": 20, "62-84": 25, "85 and over": 5}}
    ws["H2"] = 90
    buf = io.BytesIO(); wb.save(buf)
    with pytest.raises(AgeSpendError, match="head ages"):
        parse_hud_housing(buf.getvalue())


from sd_spend.agespend import parse_births_by_mother, parse_irs_credits

BIRTHS = """Table 3. Births, by age of mother, live-birth order, and race and Hispanic origin of mother: United States, 2024
    Race and Hispanic origin of                                 Younger
    mother and live-birth order                     All ages    than 15    Total    15        16           17        18      19      20–24     25–29      30–34      35–39     40–44     45–49   50–54

        All races and origins1
Total . . . . . . . . . . . . . . . . . . . . . . . 3,628,934    1,727    137,273   4,136   10,087     20,242      37,460   65,348   611,800   990,817   1,112,409   622,517   141,515   9,688   1,188
  1st child . . . . . . . . . . . . . . . . . . 1,427,020        1,698    118,128   4,019    9,564     18,475      32,699   53,371   354,230   404,955     362,002   151,974    30,846   2,768     419
"""


def test_births_by_mother_age_groups_add_to_all_ages():
    got = parse_births_by_mother(BIRTHS)
    assert got[0] == (10, 14, 1727) and got[1] == (15, 19, 137273) and got[-1] == (50, 54, 1188)
    assert sum(n for _, _, n in got) == 3_628_934


def test_births_fail_when_groups_do_not_add_up():
    with pytest.raises(AgeSpendError, match="births"):
        parse_births_by_mother(BIRTHS.replace("611,800", "711,800"))


class Sheet:
    def __init__(self, cells):
        self.cells = cells
        self.nrows = max(r for r, _ in cells) + 1
        self.ncols = max(c for _, c in cells) + 1

    def cell_value(self, r, c):
        return self.cells.get((r, c), "")


def test_irs_credits_read_the_total_rows_in_thousands():
    t25 = Sheet({(0, 0): "Table 2.5. Returns with Earned Income Credit, Tax Year 2022", (1, 0): "(money amounts are in thousands of dollars)",
                 (8, 0): "Total", (8, 10): 60_000_000.0, (8, 26): 3_000_000.0})
    t33 = Sheet({(0, 0): "Table 3.3. Tax Year 2022", (1, 0): "(money amounts are in thousands of dollars)",
                 (9, 0): "All returns, total", (9, 13): 80_000_000.0, (9, 39): 30_000_000.0})
    assert parse_irs_credits(t25, t33) == {"EITC": 60e9, "EITC childless": 3e9, "Child credit nonrefundable": 80e9, "Child credit refundable": 30e9}


def test_irs_credits_fail_when_not_in_thousands():
    t25 = Sheet({(0, 0): "Table 2.5.", (8, 0): "Total", (8, 10): 1.0, (8, 26): 1.0})
    t33 = Sheet({(0, 0): "Table 3.3.", (9, 0): "All returns, total", (9, 13): 1.0, (9, 39): 1.0})
    with pytest.raises(AgeSpendError, match="thousands"):
        parse_irs_credits(t25, t33)


UI_HEADER = '"st","rptdate","c1","c2","c3","c4","c12","c13","c14","c15","c16","c17","c18","c19","c20"'


def ui_csv(rows):
    return "\n".join([UI_HEADER, *rows]) + "\n"


def test_unemployment_ages_sum_the_fiscal_year_months_and_drop_unknown_ages():
    from sd_spend.agespend import UI_AGE_BANDS, parse_ui_ages
    rows = [f'"AK","2024-{m:02d}-30","P",60,40,0,1,2,30,30,20,10,5,2,0' for m in range(1, 13)]
    rows += ['"AK","2023-08-31","P",999,999,0,1,1,1,1,1,1,1,1,0']  # outside the window
    got = parse_ui_ages(ui_csv(rows), "2024-01-01", "2024-12-31")
    assert list(got) == list(UI_AGE_BANDS)
    assert got["25-34"] == 360 and got["65+"] == 24 and sum(got.values()) == 1200


def test_unemployment_ages_fail_when_ages_do_not_match_the_sex_total():
    from sd_spend.agespend import parse_ui_ages
    rows = [f'"AK","2024-{m:02d}-30","P",60,40,0,1,2,30,30,20,10,5,2,0' for m in range(1, 13)]
    rows[0] = '"AK","2024-01-30","P",60,40,0,1,2,30,30,20,10,5,2,500'
    with pytest.raises(AgeSpendError, match="unknown"):
        parse_ui_ages(ui_csv(rows), "2024-01-01", "2024-12-31")


def test_unemployment_ages_fail_when_a_state_is_missing_months():
    from sd_spend.agespend import parse_ui_ages
    rows = [f'"AK","2024-{m:02d}-30","P",60,40,0,1,2,30,30,20,10,5,2,0' for m in range(1, 12)]
    with pytest.raises(AgeSpendError, match="months"):
        parse_ui_ages(ui_csv(rows), "2024-01-01", "2024-12-31")


def ssi_book(federal=52_000_000, swap_total=False):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    t2 = wb.create_sheet("Table 2")
    t2.append(["Federal Benefit Rates"]); t2.append(["Table 2. Total payments"]); t2.append(["Year", "Total", "Federal SSI", "Federally administered state supplementation"])
    t2.append(["All recipients"]); t2.append([2023, 54_000_000, 51_500_000, 2_500_000]); t2.append([2024, federal + 2_000_000, federal, 2_000_000])
    t2.append(["Disabled"]); t2.append([2024, 1_000, 900, 100])
    t5 = wb.create_sheet("Table 5")
    t5.append(["Federally Administered Payments"]); t5.append(["Table 5. Recipients"]); t5.append(["Type of payment and sex", "Total", "Category", "Age"])
    t5.append(["Aged", "Blind", "Disabled", "Under 18", "18–64", "65 or older"]); t5.append(["Number"])
    t5.append(["Federal SSI", 700, 0, 0, 0, 100, 400, 200])
    t5.append(["Total payments (thousands of dollars)"])
    t5.append(["All payments", 1000, 0, 0, 0, 200, 500, 300])
    t5.append(["Federal SSI", 950 if swap_total else 1000, 0, 0, 0, 200, 600, 200])
    t35 = wb.create_sheet("Table 35")
    t35.append(["Recipients Under Age 65"]); t35.append(["Table 35. Recipients"])
    t35.append(["Diagnostic group", "All ages", "Under 5", "5–12", "13–17", "18–21", "22–25", "26–29", "30–39", "40–49", "50–59", "60–64"])
    t35.append(["Number"]); t35.append(["Total", 500, 10, 20, 70, 20, 20, 20, 100, 100, 100, 40])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_ssi_reads_federal_dollars_age_group_shares_and_fine_ages():
    from sd_spend.agespend import parse_ssi
    got = parse_ssi(ssi_book(), 2024)
    assert got["federal_dollars"] == 52_000_000 * 1000
    assert got["group_shares"] == pytest.approx({"0-17": 0.2, "18-64": 0.6, "65+": 0.2})
    assert got["under18_counts"] == {"0-4": 10, "5-12": 20, "13-17": 70}
    assert got["adult_counts"]["18-21"] == 20 and got["adult_counts"]["60-64"] == 40 and len(got["adult_counts"]) == 7


def test_ssi_fails_when_age_groups_do_not_add_to_the_total():
    from sd_spend.agespend import parse_ssi
    with pytest.raises(AgeSpendError, match="add up"):
        parse_ssi(ssi_book(swap_total=True), 2024)
