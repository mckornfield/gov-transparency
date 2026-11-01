from pathlib import Path

import pandas as pd

CSV = Path(__file__).resolve().parents[1] / "data" / "processed" / "peer_spending.csv"


def latest():
    t = pd.read_csv(CSV)
    return t[t.fiscal_year == 2024]


def test_fourteen_cities_all_groups_in_every_survey_year():
    t = pd.read_csv(CSV)
    assert sorted(t["fiscal_year"].unique()) == [2019, 2020, 2021, 2022, 2023, 2024]
    assert t.groupby("fiscal_year")["city"].nunique().eq(14).all()
    assert t.groupby(["fiscal_year", "city"])["group"].nunique().eq(15).all()


def test_price_levels_are_plausible_and_san_diego_is_pricier_than_the_texas_cities():
    t = pd.read_csv(CSV).drop_duplicates(["fiscal_year", "city"]).set_index(["fiscal_year", "city"])["rpp"]
    assert t.between(85, 125).all()
    for year in range(2019, 2025):
        assert t[(year, "San Diego")] > t[(year, "Dallas")] > 95 and t[(year, "San Diego")] > t[(year, "San Antonio")]


def test_the_spending_series_has_no_break_where_the_file_format_changed():
    # FY2019-21 files carry extra codes (equipment, transfers by function) that FY2022+ files do not.
    # City services per resident should move gradually, not jump at the format change.
    t = pd.read_csv(CSV)
    core = t[t.kind == "core"].groupby(["fiscal_year", "city"])["per_resident"].sum().unstack(0)
    growth = core.pct_change(axis=1).drop(columns=2019)
    assert growth.abs().max().max() < 0.45, growth.round(2).to_string()


def test_san_diego_police_is_plausible():
    t = latest()
    sd = t[(t.city == "San Diego") & (t.group == "police")].iloc[0]
    assert 300 <= sd.per_resident <= 700
    assert sd.population == 1_381_162


def test_san_diego_has_no_school_services_but_boston_does():
    t = latest()
    boston = t[(t.city == "Boston") & (t.group == "county")].iloc[0]
    assert boston.per_resident > 2000  # city-run schools
    assert t[(t.city == "San Diego") & (t.group == "county")].iloc[0].per_resident < 200


def test_every_configured_metro_has_a_price_level_for_every_survey_year():
    import gzip
    import json

    from sd_spend.io import RAW, ROOT
    from sd_spend.prices import parse_rpp
    rpp = parse_rpp(gzip.decompress((RAW / "bea" / "MARPP.zip.gz").read_bytes()))
    cfg = json.loads((ROOT / "config" / "peers.json").read_text())
    for msa in [cfg["home_msa"]] + [p["msa"] for p in cfg["peers"]]:
        for year in range(2018, 2025):
            assert (msa, year) in rpp, (msa, year)
    assert 100 < rpp[("41740", 2023)] < 125  # San Diego costs more than the US average


def test_older_years_count_equipment_and_land_with_construction():
    # FY2019-21 files list "other capital outlay" (G) apart from construction (F); FY2022+ fold it into F.
    import gzip

    from sd_spend.census import parse_items, read_survey
    from sd_spend.io import RAW
    phoenix = "042013207536"
    _, items = read_survey(gzip.decompress((RAW / "census" / "2021_Individual_Unit_Files.zip.gz").read_bytes()), 2021)
    it = parse_items(items)
    it = it[it.unit_id == phoenix].set_index("item")["amount_usd"]
    assert it["G24"] > 0  # the raw file really has a separate fire equipment line
    t = pd.read_csv(CSV)
    fire = t[(t.fiscal_year == 2021) & (t.city == "Phoenix") & (t.group == "fire")].iloc[0]
    assert fire.amount_usd == it.get("E24", 0) + it.get("F24", 0) + it["G24"]
