import io
import zipfile

import pytest

from sd_spend.census import CensusError
from sd_spend.prices import fiscal_year_rpp, parse_rpp

CSV = (
    "GeoFIPS,GeoName,Region,TableName,LineCode,IndustryClassification,Description,Unit,2022,2023,2024\n"
    ' "41740","San Diego-Chula Vista-Carlsbad, CA (Metropolitan Statistical Area)", ,MARPP,1,"...","RPPs: All items ","Index",110.0,112.0,114.0\n'
    ' "41740","San Diego-Chula Vista-Carlsbad, CA (Metropolitan Statistical Area)", ,MARPP,2,"...","RPPs: Goods ","Index",100.0,100.0,100.0\n'
    ' "19100","Dallas-Fort Worth-Arlington, TX (Metropolitan Statistical Area)", ,MARPP,1,"...","RPPs: All items ","Index",100.0,102.0,104.0\n'
)


def zipped(csv_text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("MARPP_MSA_2008_2024.csv", csv_text)
        z.writestr("MARPP__definition.xml", "<x/>")
    return buf.getvalue()


def test_parse_keeps_only_all_items_by_metro_and_year():
    rpp = parse_rpp(zipped(CSV))
    assert rpp[("41740", 2023)] == 112.0
    assert rpp[("19100", 2024)] == 104.0
    assert len(rpp) == 6  # 2 metros x 3 years, goods line dropped


def test_parse_rejects_a_zip_without_the_csv():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("other.txt", "x")
    with pytest.raises(CensusError):
        parse_rpp(buf.getvalue())


def test_fiscal_year_ending_december_uses_that_calendar_year():
    rpp = parse_rpp(zipped(CSV))
    assert fiscal_year_rpp(rpp, "41740", "1231", 2024) == 112.0  # survey 2024 covers FYs ended Jul 2023 - Jun 2024


def test_fiscal_year_ending_june_blends_two_calendar_years_by_months():
    rpp = parse_rpp(zipped(CSV))
    # FY ended June 2023 = 6 months of 2022 + 6 months of 2023
    assert fiscal_year_rpp(rpp, "41740", "0630", 2023) == pytest.approx(111.0)


def test_fiscal_year_end_in_september_belongs_to_previous_survey_year():
    rpp = parse_rpp(zipped(CSV))
    # Survey 2024, FY ended Sep 2023: 9 months of 2023, 3 months of 2022
    assert fiscal_year_rpp(rpp, "41740", "0930", 2024) == pytest.approx(0.75 * 112.0 + 0.25 * 110.0)


def test_missing_metro_or_year_is_an_error_not_a_guess():
    rpp = parse_rpp(zipped(CSV))
    with pytest.raises(CensusError):
        fiscal_year_rpp(rpp, "99999", "0630", 2023)
    with pytest.raises(CensusError):
        fiscal_year_rpp(rpp, "41740", "0630", 2030)


def test_add_price_levels_gives_each_city_its_metro_rpp_for_its_fiscal_year():
    import pandas as pd
    from sd_spend.prices import add_price_levels
    tidy = pd.DataFrame([
        {"unit_id": "A", "city": "San Diego", "fy_end": "0630", "group": "police"},
        {"unit_id": "A", "city": "San Diego", "fy_end": "0630", "group": "fire"},
        {"unit_id": "B", "city": "Dallas", "fy_end": "1231", "group": "police"},
    ])
    cfg = {"home": "A", "home_msa": "41740", "peers": [{"id": "B", "name": "Dallas", "msa": "19100"}]}
    out = add_price_levels(tidy, cfg, parse_rpp(zipped(CSV)), 2023)
    assert list(out["rpp"].round(1)) == [111.0, 111.0, 100.0]  # Dallas FY ended Dec 2022 -> survey 2023 -> 2022 RPP


def test_add_price_levels_needs_a_metro_for_every_city():
    import pandas as pd
    from sd_spend.prices import add_price_levels
    tidy = pd.DataFrame([{"unit_id": "A", "city": "San Diego", "fy_end": "0630", "group": "police"}])
    with pytest.raises(CensusError, match="metro"):
        add_price_levels(tidy, {"home": "A", "peers": []}, parse_rpp(zipped(CSV)), 2023)


def test_parse_ignores_the_footnote_rows_at_the_end_of_the_real_file():
    rpp = parse_rpp(zipped(CSV + '\n"Note: See the included footnote file."\n"U.S. Bureau of Economic Analysis"\n'))
    assert len(rpp) == 6
