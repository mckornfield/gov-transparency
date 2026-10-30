import pandas as pd

from sd_spend.spending import build_population


def raw(pairs):
    return pd.DataFrame({
        "entity_name": "San Diego",
        "fiscal_year": [str(y) for y, _ in pairs],
        "estimated_population": [str(p) for _, p in pairs],
    })


def test_interpolates_gaps_and_carries_forward():
    out = build_population(raw([(2011, 100), (2013, 300), (2014, 400)]), first_fy=2011, last_fy=2015)
    assert list(out["fy"]) == [2011, 2012, 2013, 2014, 2015]
    assert list(out["population"]) == [100, 200, 300, 400, 400]
    assert list(out["source"]) == ["reported", "interpolated", "reported", "reported", "carried_forward"]
