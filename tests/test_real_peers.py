from pathlib import Path

import pandas as pd

CSV = Path(__file__).resolve().parents[1] / "data" / "processed" / "peer_spending.csv"


def test_twelve_cities_all_groups():
    t = pd.read_csv(CSV)
    assert t["city"].nunique() == 12 and t["group"].nunique() == 15
    assert t.groupby("city")["group"].nunique().eq(15).all()


def test_san_diego_police_is_plausible():
    t = pd.read_csv(CSV)
    sd = t[(t.city == "San Diego") & (t.group == "police")].iloc[0]
    assert 300 <= sd.per_resident <= 700
    assert sd.population == 1_381_162


def test_san_diego_has_no_school_services_but_boston_does():
    t = pd.read_csv(CSV)
    boston = t[(t.city == "Boston") & (t.group == "county")].iloc[0]
    assert boston.per_resident > 2000  # city-run schools
    assert t[(t.city == "San Diego") & (t.group == "county")].iloc[0].per_resident < 200
