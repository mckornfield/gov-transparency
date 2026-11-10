import pytest

from sd_spend.ageallocate import AllocationError, KEYS, band_of, from_shares, generation_labels, scale, spread_ages, va_bands

POP = {a: 10 for a in range(0, 101)}


def test_band_edges():
    assert [band_of(a) for a in (0, 18, 19, 44, 45, 64, 65, 84, 85, 100)] == ["0-18", "0-18", "19-44", "19-44", "45-64", "45-64", "65-84", "65-84", "85+", "85+"]


def test_spread_ages_follows_population_and_keeps_the_total():
    out = spread_ages(1000.0, 40, 49, POP)
    assert out["19-44"] == pytest.approx(500.0) and out["45-64"] == pytest.approx(500.0)
    assert sum(out.values()) == pytest.approx(1000.0)


def test_spread_ages_fails_without_population():
    with pytest.raises(AllocationError):
        spread_ages(1.0, 200, 210, POP)


def test_scale_keeps_the_shape_and_hits_the_total():
    out = scale({k: float(i + 1) for i, k in enumerate(KEYS)}, 150.0)
    assert sum(out.values()) == pytest.approx(150.0) and out["85+"] == pytest.approx(50.0)


def test_from_shares():
    assert sum(from_shares(100.0, dict(zip(KEYS, (0.1, 0.2, 0.3, 0.3, 0.1)))).values()) == pytest.approx(100.0)


def test_va_bands_split_dollars_by_recipient_counts():
    out = va_bands({"young": 1, "old": 3}, 400.0, POP, {"young": (19, 30), "old": (65, 84)})
    assert out["19-44"] == pytest.approx(100.0) and out["65-84"] == pytest.approx(300.0)


def test_generation_labels_come_after_the_brackets():
    assert generation_labels(("65-84", 65, 84), POP, 2024) == ["Silent", "Baby Boomers"]
    assert generation_labels(("0-18", 0, 18), POP, 2024) == ["Gen Z", "Gen Alpha"]


def test_parent_age_places_the_credit_a_mothers_age_later_and_keeps_the_total():
    from sd_spend.ageallocate import by_parent_age
    pop = {a: 10 for a in range(0, 101)}
    # every mother was 30 at birth: a child of 10 has a 40-year-old parent, a child of 16 a 46-year-old
    out = by_parent_age(1000.0, 10, 16, pop, [(30, 30, 5)])
    assert sum(out.values()) == pytest.approx(1000.0)
    assert out["19-44"] == pytest.approx(1000.0 * 5 / 7) and out["45-64"] == pytest.approx(1000.0 * 2 / 7)
    assert out["0-18"] == 0


def test_parent_age_fails_without_children():
    from sd_spend.ageallocate import by_parent_age
    with pytest.raises(AllocationError):
        by_parent_age(1.0, 10, 16, {a: 0 for a in range(0, 101)}, [(30, 30, 5)])


def test_person_directed_total_counts_only_people_functions():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from sd_spend.agespend import PERSON_FUNCTIONS, person_directed_total
    lines = {name: 10.0 for name in PERSON_FUNCTIONS} | {"National Defense": 500.0, "Net Interest": 400.0, "Total": 9999.0}
    assert person_directed_total(lines) == 10.0 * len(PERSON_FUNCTIONS)
    assert "National Defense" not in PERSON_FUNCTIONS and "Net Interest" not in PERSON_FUNCTIONS
