import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "config" / name).read_text())


def test_peers_config_shape():
    cfg = load("peers.json")
    ids = [cfg["home"]] + [p["id"] for p in cfg["peers"]]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert all(len(i) == 12 for i in ids)
    assert {p["region"] for p in cfg["peers"]} >= {"West", "South", "Northeast", "Pacific Northwest"}


def test_function_codes_unique_and_kinds_known():
    groups = load("census_functions.json")["groups"]
    codes = [c for g in groups for c in g["codes"]]
    assert len(codes) == len(set(codes)), "an item code is mapped to two groups"
    assert {g["kind"] for g in groups} <= {"core", "utility", "outside", "debt", "other"}
    assert all(c[0] in "EFGIJLMS" for c in codes)
