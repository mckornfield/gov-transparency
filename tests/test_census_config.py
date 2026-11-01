import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "config" / name).read_text())


def test_peers_config_shape():
    cfg = load("peers.json")
    ids = [cfg["home"]] + [p["id"] for p in cfg["peers"]]
    assert len(ids) == 14 and len(set(ids)) == 14
    assert all(len(i) == 12 for i in ids)
    assert {p["region"] for p in cfg["peers"]} >= {"West", "South", "Northeast", "Pacific Northwest"}


def test_function_codes_unique_and_kinds_known():
    groups = load("census_functions.json")["groups"]
    codes = [c for g in groups for c in g["codes"]]
    assert len(codes) == len(set(codes)), "an item code is mapped to two groups"
    assert {g["kind"] for g in groups} <= {"core", "utility", "outside", "debt", "other"}
    assert all(c[0] in "EFGIJLMS" for c in codes)


def test_every_city_has_a_five_digit_metro_code():
    cfg = load("peers.json")
    codes = [cfg["home_msa"]] + [p["msa"] for p in cfg["peers"]]
    assert all(len(c) == 5 and c.isdigit() for c in codes)


def test_exactly_two_reference_cities_and_eleven_real_peers():
    peers = load("peers.json")["peers"]
    assert sorted(p["name"] for p in peers if p.get("reference")) == ["Arlington County, VA", "Vancouver, WA"]
    assert sum(1 for p in peers if not p.get("reference")) == 11
