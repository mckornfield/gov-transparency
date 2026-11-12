import pytest

from sd_spend.sdage import (SdAgeError, city_departments, funded_shares, parse_bhs_ages, parse_county_budget, parse_county_population,
                            parse_county_revenue, school_totals, source_of)


def population_csv(ages=range(86), county="073", year="6"):
    lines = ["SUMLEV,STATE,COUNTY,STNAME,CTYNAME,YEAR,AGE,TOT_POP,TOT_MALE,TOT_FEMALE"]
    lines += [f"050,06,{county},California,San Diego County,{year},{a},{1000 + a},500,500" for a in ages]
    lines += [f"050,06,001,California,Alameda County,{year},{a},7,3,4" for a in ages]
    return "\n".join(lines)


def test_county_population_picks_one_county_and_year():
    pop = parse_county_population(population_csv(), "073", "6")
    assert pop[0] == 1000 and pop[85] == 1085 and len(pop) == 86


def test_county_population_fails_on_a_missing_age():
    with pytest.raises(SdAgeError):
        parse_county_population(population_csv(ages=range(80)), "073", "6")
    with pytest.raises(SdAgeError):
        parse_county_population(population_csv(), "073", "5")


BUDGET = """fiscal_year,group,department,program,expense_type,amount2
2025,Health,Aging,In-Home,Salaries,100
2025,Health,Aging,In-Home,Services,50.5
2025,Safety,Sheriff,Jails,Salaries,10
2026,Health,Aging,In-Home,Salaries,999
"""


def test_county_budget_adds_rows_by_program_for_one_year():
    table = parse_county_budget(BUDGET, "2025")
    assert table == {("Health", "Aging", "In-Home"): 150.5, ("Safety", "Sheriff", "Jails"): 10.0}


def test_county_budget_fails_on_missing_year_or_columns():
    with pytest.raises(SdAgeError):
        parse_county_budget(BUDGET, "2024")
    with pytest.raises(SdAgeError):
        parse_county_budget("a,b\n1,2\n", "2025")


def test_source_of_classifies_who_paid():
    assert source_of("Intergovernmental Revenues", "State Realignment 2011") == "state"
    assert source_of("Intergovernmental Revenues", "St Aid California Children") == "state"
    assert source_of("Intergovernmental Revenues", "Other State - Health") == "state"
    assert source_of("Intergovernmental Revenues", "Federal Other") == "federal"
    assert source_of("Intergovernmental Revenues", "Aid From Other Governmental Agencies") == "other"
    assert source_of("General Purpose Revenue Allocation", "General Purpose Revenue Allocation") == "county"
    assert source_of("Charges For Current Services", "State Trial Courts") == "other"


def test_county_revenue_by_program_and_source():
    text = """fiscal_year,drilldown_1_group,department,program,expense_type,amount2,revenue_object
2025,Health,Aging,In-Home,State Aid Other,60,Intergovernmental Revenues
2025,Health,Aging,In-Home,Federal Other,30,Intergovernmental Revenues
2025,Health,Aging,In-Home,General Purpose Revenue Allocation,10,General Purpose Revenue Allocation
2026,Health,Aging,In-Home,Federal Other,500,Intergovernmental Revenues
"""
    revenue = parse_county_revenue(text, "2025")
    assert revenue[("Aging", "In-Home")] == {"state": 60.0, "federal": 30.0, "county": 10.0, "other": 0.0}
    assert funded_shares(revenue[("Aging", "In-Home")])["state"] == pytest.approx(0.6)


def test_funded_shares_rejects_nonsense():
    with pytest.raises(SdAgeError):
        funded_shares({"state": 0.0, "federal": 0.0})
    with pytest.raises(SdAgeError):
        funded_shares({"state": 100.0, "federal": -50.0})


DATABOOK = """
   Substance Use Disorder Services, FY 2024-25
                         Total Unique Episodes           160              Total Unique Clients               100
   Age                                                                     Living Situation
                 Age 9 to 15        20     1.8%      10     10.0%          Dependent Living      6,638        19.5%
                Age 16 to 17        20     1.4%      10     10.0%                  Homeless      10,323       30.3%
                Age 18 to 25        40     6.9%      20     20.0%
                Age 26 to 59        60    82.3%      50     50.0%
                    Age 60+         20     7.5%      10     10.0%
    Mental Health Services for Children & Youth, FY 2024-25*
       Clients Receiving County-funded     Unique Clients
                 Mental Health Services           1,100                                        7,113
                                Age     Unique Clients                 %            Race/Ethnicity Unique Clients   %
                         Age 0 to 5              100                   14%                 Hispanic    7,846     66%
                        Age 6 to 11              300                   31%                 NH White     1,451     12%
                       Age 12 to 15              400                   30%
                       Age 16 to 17              200                   19%
                           Age 18+               100                     6%
                Adult Behavioral Health Services Fiscal Year 2024-25
                                        Clients Receiving Services         4,000
                                     Age     Unique Clients    %                    Diagnosis      Unique Clients   % **
                              Age <18-25         1,000        18%             Schizophrenia       17,201        44%
                               Age 26-59         2,500        66%                 Bipolar Disorders        7,946        20%
                                 Age 60+           500        15%              Depressive Disorders         8,241        21%
"""


def test_bhs_ages_reads_three_blocks():
    ages = parse_bhs_ages(DATABOOK)
    assert ages["substance"] == {"9-15": 10, "16-17": 10, "18-25": 20, "26-59": 50, "60+": 10}
    assert ages["children"] == {"0-5": 100, "6-11": 300, "12-15": 400, "16-17": 200, "18+": 100}
    assert ages["adults"] == {"<18-25": 1000, "26-59": 2500, "60+": 500}


def test_bhs_ages_fails_when_a_block_does_not_add_up():
    with pytest.raises(SdAgeError, match="add up"):
        parse_bhs_ages(DATABOOK.replace("Clients Receiving Services         4,000", "Clients Receiving Services         4,100"))
    with pytest.raises(SdAgeError):
        parse_bhs_ages(DATABOOK.replace("Adult Behavioral Health Services Fiscal Year", "Something else"))


def test_school_totals_adds_spending_and_sorts_revenue():
    schools = {"revenues": ["State aid (funding formula and Education Protection Account)", "Other state", "Federal", "Local property taxes",
                            "Passed on by other school agencies (mostly state special-education money)"],
               "districts": [{"spending": {"Teacher salaries": 60.0, "Books": 40.0},
                              "revenue": {"State aid (funding formula and Education Protection Account)": 40.0, "Federal": 10.0, "Local property taxes": 50.0}},
                             {"spending": {"Teacher salaries": 100.0}, "revenue": {"Other state": 100.0}}]}
    dollars, sources = school_totals(schools)
    assert dollars == 200.0
    assert sources == {"state": 140.0, "federal": 10.0, "local": 50.0}


def test_school_totals_fails_when_a_revenue_group_is_renamed():
    schools = {"revenues": ["Federal"], "districts": [{"spending": {"x": 1.0}, "revenue": {"Federal": 1.0}}]}
    with pytest.raises(SdAgeError):
        school_totals(schools)


def test_city_departments_filters_basis_and_year():
    text = "basis,fy,dept_group,dept_name,account_type,account_class,amount\nadopted,2025,Library,Library,P,x,10\nadopted,2025,Library,Library,N,y,5\nactual,2025,Library,Library,P,x,99\nadopted,2024,Police,Police,P,x,7\n"
    assert city_departments(text, "adopted", "2025") == {"Library": 15.0}
    with pytest.raises(SdAgeError):
        city_departments(text, "actual", "2030")
