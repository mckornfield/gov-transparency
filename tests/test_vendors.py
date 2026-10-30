import pytest

from sd_spend import vendors as v

FY22 = """City of San Diego
Cumulative Amounts Paid to Vendors - $25,000 or more
Fiscal Year 2022 (July 2021 to June 2022)



Vendor      Vendor Name                                   Amount
 10020828   SDCERS                                         841,366,616
 10007317   San Diego County Water Authority               260,209,475
Page 1 of 1
"""

FY23 = """City of San Diego
Cumulative Amounts Paid to Vendors - $25,000 or more
Fiscal Year 2023 (July 2022 to June 2023)

     Vendor          Vendor Name                                         Payment Amount

         0010007317 San Diego County Water Authority                        $276,824,244.78

         0010005357 US Bank National Association                            $241,794,510.35
Page 1 of 1
"""

FY24 = """City of San Diego
Cumulative Amounts Paid to Vendors - $ 25,000 or more
Fiscal Year 2024 (July 2023 to June 2024 Only)

Vendor         Vendor Name                                       Payment Amount

   0010007317 San Diego County Water Authority                      $252,567,610.88
Page 1 of 2
City of San Diego
Cumulative Amounts Paid to Vendors - $ 25,000 or more
Fiscal Year 2024 (July 2023 to June 2024 Only)

Vendor         Vendor Name                                       Payment Amount
   0010099999 Acme 2000 Inc                                          $25,000.00
Page 2 of 2
"""


def test_parses_fy22_layout_without_cents():
    fy, df, info = v.parse_report(FY22)
    assert fy == 2022
    assert list(df["vendor_id"]) == ["10020828", "10007317"]
    assert list(df["vendor_name"]) == ["SDCERS", "San Diego County Water Authority"]
    assert list(df["amount"]) == [841366616.0, 260209475.0]
    assert info == {"unmatched": [], "pages_declared": 1, "pages_seen": 1, "page_numbers": [1]}


def test_parses_fy23_layout_with_padded_ids_dollar_sign_cents_and_blank_rows():
    fy, df, _ = v.parse_report(FY23)
    assert fy == 2023
    assert list(df["vendor_id"]) == ["10007317", "10005357"]
    assert list(df["amount"]) == [276824244.78, 241794510.35]


def test_parses_fy24_two_pages_and_names_ending_in_digits():
    fy, df = v.parse_and_validate(FY24)
    assert fy == 2024
    assert list(df["vendor_name"]) == ["San Diego County Water Authority", "Acme 2000 Inc"]
    assert df["amount"].min() == 25000.0


def test_an_unrecognised_line_fails_loudly():
    wrapped = FY22.replace("Page 1 of 1", "   Construction Inc\nPage 1 of 1")
    with pytest.raises(v.ExtractionError, match="Construction Inc"):
        v.parse_and_validate(wrapped)


def test_a_missing_page_fails_loudly():
    missing = FY24.replace("Page 2 of 2", "")
    with pytest.raises(v.ExtractionError, match="pages"):
        v.parse_and_validate(missing)


def test_duplicate_vendor_ids_fail_loudly():
    dup = FY22.replace("10007317   San Diego County Water Authority", "10020828   Some Other Name")
    with pytest.raises(v.ExtractionError, match="duplicate"):
        v.parse_and_validate(dup)


def test_amounts_below_the_published_threshold_fail_loudly():
    small = FY22.replace("841,366,616", "841")
    with pytest.raises(v.ExtractionError, match="25,000"):
        v.parse_and_validate(small)


def test_empty_report_fails_loudly():
    with pytest.raises(v.ExtractionError, match="no rows"):
        v.parse_and_validate("City of San Diego\nFiscal Year 2024 (x)\nPage 1 of 1\n")


import pandas as pd


def report(*rows):
    return pd.DataFrame(rows, columns=["vendor_id", "vendor_name", "amount"])


def test_name_key_ignores_case_punctuation_and_ampersand():
    assert v.name_key("CGI Technologies & Solutions Inc.") == v.name_key("cgi technologies and solutions inc")
    assert v.name_key("San Diego Gas And Electric") == v.name_key("San Diego Gas and Electric")


def test_combine_merges_ids_and_spellings_and_uses_the_latest_name():
    out = v.combine({
        2024: report(("A", "San Diego Gas and Electric", 60.0), ("B", "San Diego Gas And Electric", 15.0),
                     ("C", "CGI Technologies & Solutions", 5.0)),
        2025: report(("D", "CGI Technologies and Solutions", 6.0)),
    })
    sdge = out[out["vendor_key"] == v.loose_key("San Diego Gas and Electric")]
    assert list(sdge["amount"]) == [75.0]
    assert list(sdge["vendor_ids"]) == ["A; B"]
    assert list(sdge["vendor_name"]) == ["San Diego Gas and Electric"]
    cgi = out[out["vendor_key"] == v.loose_key("CGI Technologies and Solutions")]
    assert list(cgi["fy"]) == [2024, 2025]
    assert set(cgi["vendor_name"]) == {"CGI Technologies and Solutions"}
    assert list(out["fy"]) == sorted(out["fy"])
    assert list(out[out["fy"] == 2024]["amount"]) == [75.0, 5.0]


def test_combine_never_merges_vendors_whose_names_have_no_letters_or_digits():
    out = v.combine({2024: report(("1001", "---", 30000.0), ("1002", "...", 40000.0))})
    assert len(out) == 2


def spending(rows):
    return pd.DataFrame(rows, columns=["basis", "fy", "amount"])


def test_coverage_prefers_actuals_and_falls_back_to_adopted():
    cov = v.coverage(pd.Series({2023: 60.0, 2026: 30.0}),
                     spending([("actual", 2023, 100.0), ("adopted", 2023, 90.0), ("adopted", 2026, 50.0)]))
    assert cov[2023] == {"vendors_total": 60.0, "reference_total": 100.0, "reference_basis": "actual"}
    assert cov[2026] == {"vendors_total": 30.0, "reference_total": 50.0, "reference_basis": "adopted"}


def test_coverage_requires_a_reference_year():
    with pytest.raises(v.ExtractionError, match="2030"):
        v.coverage(pd.Series({2030: 1.0}), spending([("actual", 2023, 100.0)]))


def test_check_coverage_catches_a_lost_chunk_of_pages_and_double_counting():
    ok = {2023: {"vendors_total": 60.0, "reference_total": 100.0, "reference_basis": "actual"}}
    v.check_coverage(ok)
    for paid in (10.0, 150.0):
        bad = {2023: {"vendors_total": paid, "reference_total": 100.0, "reference_basis": "actual"}}
        with pytest.raises(v.ExtractionError, match="2023"):
            v.check_coverage(bad)


def test_combine_merges_a_vendor_id_renamed_with_a_suffix_change():
    out = v.combine({
        2022: report(("10036157", "Shimmick Construction Inc", 364.0)),
        2025: report(("10036157", "Shimmick Construction Company Inc", 70.0)),
    })
    assert out["vendor_key"].nunique() == 1
    assert list(out["fy"]) == [2022, 2025]
    assert set(out["vendor_name"]) == {"Shimmick Construction Company Inc"}


def test_combine_merges_an_id_renamed_to_a_longer_name_with_the_same_first_word():
    out = v.combine({
        2022: report(("10013048", "Flatiron West Inc", 90.0)),
        2025: report(("10013048", "Flatiron Dragados Constructors Inc", 100.0)),
    })
    assert out["vendor_key"].nunique() == 1


def test_combine_does_not_merge_an_id_reused_by_an_unrelated_payee():
    out = v.combine({
        2022: report(("12298", "Accion San Diego", 30000.0)),
        2023: report(("12298", "Accessity", 40000.0)),
    })
    assert out["vendor_key"].nunique() == 2


def test_combine_merges_suffix_variants_within_a_year():
    out = v.combine({2026: report(
        ("1", "Downtown San Diego Partnership Inc", 13.5), ("2", "Downtown San Diego Partnership", 4.0),
        ("3", "AT&T Corp", 1.0), ("4", "AT&T", 2.0),
        ("5", "The Regents of the University of Ca", 5.0), ("6", "Regents of the University of CA", 6.0))})
    assert sorted(out["amount"]) == [3.0, 11.0, 17.5]


def test_page_footers_must_be_exactly_one_to_n_not_just_the_right_count():
    duplicated = FY24.replace("Page 2 of 2", "Page 1 of 2")  # two footers, but page 2 is missing
    with pytest.raises(v.ExtractionError, match="pages"):
        v.parse_and_validate(duplicated)


def test_declared_pages_must_match_the_real_pdf_page_count():
    assert v.parse_and_validate(FY24, expected_pages=2)[0] == 2024
    with pytest.raises(v.ExtractionError, match="PDF has 3 pages"):
        v.parse_and_validate(FY24, expected_pages=3)


def test_check_row_counts_flags_a_year_that_shrinks_or_balloons():
    v.check_row_counts({2024: 1500, 2025: 1600})
    for bad in (700, 2400):
        with pytest.raises(v.ExtractionError, match="2025"):
            v.check_row_counts({2024: 1500, 2025: bad})
