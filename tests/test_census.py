import io
import zipfile

import pytest

from sd_spend.census import (CensusError, build_peer_spending, parse_items, parse_units, read_zip_member)

HOME, PEER = "062073207598", "482113187649"
PEERS = {"home": HOME, "peers": [{"id": PEER, "name": "Dallas", "state": "TX", "region": "South"}]}
FUNCS = {"groups": [
    {"key": "police", "label": "Police", "kind": "core", "codes": ["E62", "F62"]},
    {"key": "water", "label": "Water utility", "kind": "utility", "codes": ["E91"]},
]}


def unit_line(uid, name, pop, fy="0630"):
    # id 12, name 64, county 35, FIPS place 5, population 9, pop year 2, enrollment 7, enroll yr 2,
    # function 2, school level 2, fiscal year end 4, survey year 2
    return f"{uid}{name:<64}{'County':<35}{'66000':<5}{pop:>9}24{'':>7}{'':>2}{'':>2}{'':>2}{fy}24"


def item_line(uid, code, thousands):
    return f"{uid}{code}{thousands:>12}2024R "


def units_text(pop_home=100_000, pop_peer=100_000):
    return "\n".join([unit_line(HOME, "SAN DIEGO CITY", pop_home), unit_line(PEER, "DALLAS CITY", pop_peer, "0930")])


def items_text(rows):
    return "\n".join(item_line(u, c, v) for u, c, v in rows)


def test_parse_units_reads_fixed_columns():
    u = parse_units(units_text())
    assert list(u["unit_id"]) == [HOME, PEER]
    assert list(u["population"]) == [100_000, 100_000]
    assert list(u["fy_end"]) == ["0630", "0930"]
    assert u.loc[0, "name"] == "SAN DIEGO CITY"


def test_parse_items_converts_thousands_to_dollars():
    i = parse_items(items_text([(HOME, "E62", 5)]))
    assert i.loc[0, "amount_usd"] == 5000 and i.loc[0, "item"] == "E62"


def good_items():
    return parse_items(items_text([(HOME, "E62", 200_000), (HOME, "F62", 50_000), (HOME, "E91", 100_000),
                                   (PEER, "E62", 300_000), (PEER, "E91", 80_000), (HOME, "A01", 999)]))


def test_build_sums_codes_per_group_and_per_resident():
    t = build_peer_spending(parse_units(units_text()), good_items(), PEERS, FUNCS)
    home_police = t[(t.is_home) & (t.group == "police")].iloc[0]
    assert home_police.amount_usd == 250_000_000 and home_police.per_resident == 2500
    assert t[(~t.is_home) & (t.group == "police")].iloc[0].city == "Dallas"
    assert set(t.columns) >= {"city", "region", "fy_end", "kind", "label", "per_resident"}


def test_missing_function_is_zero_row_not_absent():
    items = parse_items(items_text([(HOME, "E62", 200_000), (PEER, "E62", 300_000), (HOME, "E91", 100_000)]))
    t = build_peer_spending(parse_units(units_text()), items, PEERS, FUNCS)
    assert t[(~t.is_home) & (t.group == "water")].iloc[0].amount_usd == 0


def test_revenue_codes_are_ignored():
    t = build_peer_spending(parse_units(units_text()), good_items(), PEERS, FUNCS)
    assert "A01" not in set(t["group"])


def test_unmapped_expenditure_code_fails():
    items = parse_items(items_text([(HOME, "E62", 200_000), (PEER, "E62", 300_000), (HOME, "E77", 5)]))
    with pytest.raises(CensusError, match="E77"):
        build_peer_spending(parse_units(units_text()), items, PEERS, FUNCS)


def test_missing_city_fails():
    units = parse_units(unit_line(HOME, "SAN DIEGO CITY", 100_000))
    with pytest.raises(CensusError, match=PEER):
        build_peer_spending(units, good_items(), PEERS, FUNCS)


def test_implausible_total_per_resident_fails():
    with pytest.raises(CensusError, match="per resident"):
        build_peer_spending(parse_units(units_text(pop_home=1_000)), good_items(), PEERS, FUNCS)


def test_read_zip_member_finds_by_suffix():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2024_Individual_Unit_Files/Fin_PID_2024.txt", "hello")
    assert read_zip_member(buf.getvalue(), "Fin_PID_2024.txt") == "hello"
    with pytest.raises(CensusError):
        read_zip_member(buf.getvalue(), "missing.txt")
