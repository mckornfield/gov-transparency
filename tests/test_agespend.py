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
