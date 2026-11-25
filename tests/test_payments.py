from datetime import date

import pytest

from sd_spend.payments import HEADER, NO_TYPE, PaymentsError, fiscal_year, fund_class, parse_payments, unnamed_years


def tsv(*rows):
    return "\n".join(["\t".join(HEADER), *("\t".join(r) for r in rows)]) + "\n"


ROW = ["10000856", "Uline Inc", "2025-09-30", "2001491276", "8342.38", "4000289527", "1912", "Fire-Rescue", "600000", "GRANT FUND-FEDERAL", "Supplies"]


def test_fiscal_year_runs_july_to_june():
    assert fiscal_year(date(2025, 6, 30)) == 2025
    assert fiscal_year(date(2025, 7, 1)) == 2026


def test_parse_payments_reads_a_line_and_names_a_blank_type():
    df = parse_payments(tsv(ROW, ROW[:10] + [""]))
    first = df.iloc[0]
    assert first["vendor_id"] == "10000856" and first["fy"] == 2026 and first["amount"] == 8342.38
    assert first["dept"] == "Fire-Rescue" and first["fund"] == "GRANT FUND-FEDERAL" and first["type"] == "Supplies"
    assert df.iloc[1]["type"] == NO_TYPE


def test_parse_payments_keeps_a_blanked_name():
    df = parse_payments(tsv(["10000001", ""] + ROW[2:]))
    assert df.iloc[0]["vendor_name"] == ""


@pytest.mark.parametrize("bad", [
    ["x"] + ROW[1:],                 # vendor id is not a number
    ROW[:2] + ["30/09/2025"] + ROW[3:],  # not an ISO date
    ROW[:4] + ["12,000"] + ROW[5:],  # amount with a comma
    ROW[:7] + [""] + ROW[8:],        # no department
    ROW[:9],                         # missing fields
])
def test_parse_payments_fails_on_a_bad_line(bad):
    with pytest.raises(PaymentsError):
        parse_payments(tsv(bad))


def test_parse_payments_fails_on_unexpected_columns_or_no_rows():
    with pytest.raises(PaymentsError):
        parse_payments("Vendor\tName\n1\tx\n")
    with pytest.raises(PaymentsError):
        parse_payments(tsv())


def test_unnamed_years_is_per_vendor_and_fiscal_year():
    rows = [
        ["1", "Big Co", "2024-07-01", "", "30000"],     # FY2025: named
        ["1", "Big Co", "2025-07-01", "", "100"],       # FY2026: under $25,000, so not named that year
        ["2", "A Person", "2024-07-01", "", "20000"],
        ["2", "A Person", "2025-07-01", "", "20000"],
        ["4", "Two Bills", "2024-08-01", "", "15000"],
        ["4", "Two Bills", "2025-06-30", "", "10000"],  # 25k in FY2025
    ]
    assert unnamed_years(rows) == {("1", 2026), ("2", 2025), ("2", 2026)}


def test_one_id_with_two_names_fails():
    with pytest.raises(PaymentsError, match="two names"):
        unnamed_years([["1", "Big Co", "2024-07-01", "", "1"], ["1", "Other Co", "2024-07-02", "", "1"]])
    with pytest.raises(PaymentsError, match="two names"):
        parse_payments(tsv(ROW, [ROW[0], "Someone Else"] + ROW[2:]))
    assert len(parse_payments(tsv(ROW, [ROW[0], ""] + ROW[2:]))) == 2  # a blanked year is not a second name


@pytest.mark.parametrize("code,name,expected", [
    ("100000", "GENERAL FUND", "General fund"),
    ("100012", "INFRASTRUCTURE FUND", "General fund"),
    ("700011", "WATER UTILITY OPERAT", "Water and sewer"),
    ("700001", "METRO SEWER UTILITY", "Water and sewer"),
    ("400881", "DEBT FUNDED GF CIP", "Borrowed money (bonds and loans)"),
    ("400884", "GF WIFIA LOAN-CONST", "Borrowed money (bonds and loans)"),
    ("600000", "GRANT FUND-FEDERAL", "Grants"),
    ("710001", "GRANT FUND-ENT-STATE", "Grants"),
    ("200811", "COVID-19 RENT RELIEF", "Grants"),
    ("720000", "FLEET OPERATIONS", "Other city funds"),
    ("200308", "DEPT INFO TECHNOLOGY", "Other city funds"),
    ("200700", "RDA OBLIG RET FUND", "Other city funds"),
    ("400872", "TRANSNET COMM PAPER", "Borrowed money (bonds and loans)"),
])
def test_fund_class(code, name, expected):
    assert fund_class(code, name) == expected
