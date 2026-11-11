import pytest

from sd_spend.schools import SchoolsError, category_of, parse_districts, parse_ledger, purpose_of, revenue_group_of, summarize

HEAD = "Ccode,Dcode,SchoolCode,Fiscalyear,Period,Colcode,Account,Fund,Resource,Projectyear,Goal,Function,Object,Value\n"


def ledger(*rows):
    return HEAD + "".join(f'"37","{d}","0000000","2023","A","BA","x","{fund}","{res}","0","0000","{fn}","{obj}",{value}\n'
                          for d, fund, res, fn, obj, value in rows)


def test_objects_map_to_one_category_each():
    assert category_of("1100", "0000") == "Teacher salaries"
    assert category_of("1300", "0000") == "Principals and certificated administrators"
    assert category_of("2100", "0000") == "Classroom aides"
    assert category_of("3101", "0000") == "Teacher pensions (CalSTRS), paid by the district"
    assert category_of("3101", "7690") == "Teacher pensions (CalSTRS), paid by the state on the district's behalf"
    assert category_of("3202", "0000") == "Staff pensions (CalPERS)"
    assert category_of("3401", "0000") == "Health and welfare benefits"
    assert category_of("3701", "0000") == "Retiree health benefits"
    assert category_of("5100", "0000") == "Contracted services (subagreements)"
    assert category_of("5800", "0000") == "Other services and operating costs"
    assert category_of("7439", "0000") == "Tuition, payments to other agencies and debt service"


def test_transfers_between_funds_and_revenue_are_not_spending():
    for obj in ("7612", "7619", "8011", "9110"):
        assert category_of(obj, "0000") is None


def test_an_unknown_spending_object_fails_loudly():
    with pytest.raises(SchoolsError, match="0999"):
        category_of("0999", "0000", strict=True)


def test_purposes_and_revenue_groups():
    assert purpose_of("1000") == "Classroom instruction"
    assert purpose_of("1120") == "Special education instruction"
    assert purpose_of("2700") == "School administration"
    assert purpose_of("3600") == "Pupil transportation"
    assert purpose_of("3110") == "Pupil services (counseling, health, psychology)"
    assert purpose_of("7200") == "District administration"
    assert purpose_of("8100") == "Buildings, maintenance and operations"
    assert purpose_of("9100") == "Other (community, enterprise, debt, transfers to agencies)"
    assert revenue_group_of("8011") == "State aid (funding formula and Education Protection Account)"
    assert revenue_group_of("8041") == "Local property taxes"
    assert revenue_group_of("8096") == "Property taxes passed to charter schools"
    assert revenue_group_of("8290") == "Federal"
    assert revenue_group_of("8590") == "Other state"
    assert revenue_group_of("8699") == "Other local"
    assert revenue_group_of("8919") is None


def test_districts_keep_name_type_and_attendance():
    text = 'Ccode,Dcode,Dname,Dtype,K12ADA\n37,68338,San Diego Unified,Unified School District,87342.88\n37,10371,County Office,County Office of Education,0\n'
    assert parse_districts(text) == {"68338": {"name": "San Diego Unified", "type": "Unified School District", "ada": 87342.88},
                                     "10371": {"name": "County Office", "type": "County Office of Education", "ada": 0.0}}


def test_summary_splits_general_fund_spending_revenue_and_other_funds():
    rows = parse_ledger(ledger(("68338", "01", "0000", "1000", "1100", 600.0), ("68338", "01", "7690", "1000", "3101", 50.0),
                               ("68338", "01", "0000", "8100", "5800", 150.0), ("68338", "01", "0000", "9300", "7619", 999.0),
                               ("68338", "01", "0000", "0000", "8041", 700.0), ("68338", "01", "0000", "0000", "8011", 300.0),
                               ("68338", "21", "0000", "8500", "6200", 400.0), ("68338", "01", "0000", "0000", "9110", 5.0)))
    got = summarize(rows, {"21": "Building Fund"})["68338"]
    assert got["spending"] == {"Teacher salaries": 600.0, "Teacher pensions (CalSTRS), paid by the state on the district's behalf": 50.0,
                               "Other services and operating costs": 150.0}
    assert got["purpose"] == {"Classroom instruction": 650.0, "Buildings, maintenance and operations": 150.0}
    assert got["revenue"] == {"Local property taxes": 700.0, "State aid (funding formula and Education Protection Account)": 300.0}
    assert got["other_funds"] == {"Building Fund": 400.0}


def test_ledger_fails_on_a_missing_column_or_a_bad_amount():
    with pytest.raises(SchoolsError, match="Object"):
        parse_ledger("Ccode,Dcode,Fund,Resource,Function,Value\n37,1,01,0000,1000,5\n")
    with pytest.raises(SchoolsError, match="amount"):
        parse_ledger(ledger(("68338", "01", "0000", "1000", "1100", "abc")))
