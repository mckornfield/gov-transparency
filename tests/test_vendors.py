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
    assert info == {"unmatched": [], "pages_declared": 1, "pages_seen": 1}


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
