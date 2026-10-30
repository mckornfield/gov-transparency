import csv
import gzip
import hashlib

from sd_spend.io import RAW

REQUIRED = {
    "sandiego/actuals_operating.csv.gz",
    "sandiego/budget_operating.csv.gz",
    "sandiego/accounts.csv.gz",
    "sandiego/depts.csv.gz",
    "sco/san_diego_population.csv.gz",
    "census/2024_Individual_Unit_Files.zip.gz",
    "census/2024_methodology.pdf.gz",
    *{f"sandiego/vendor_payments_fy{fy}.pdf.gz" for fy in range(2022, 2027)},
}


def manifest_rows():
    with (RAW / "MANIFEST.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_required_sources_are_in_manifest():
    assert REQUIRED <= {r["path"] for r in manifest_rows()}


def test_every_manifest_file_exists_and_matches_hash():
    for row in manifest_rows():
        data = gzip.decompress((RAW / row["path"]).read_bytes())
        assert hashlib.sha256(data).hexdigest() == row["sha256_original"], row["path"]
        assert str(len(data)) == row["bytes_original"], row["path"]
        assert row["url"].startswith("https://"), row["path"]


def test_no_raw_file_is_missing_from_manifest():
    listed = {r["path"] for r in manifest_rows()}
    on_disk = {p.relative_to(RAW).as_posix() for p in RAW.rglob("*.gz")}
    assert on_disk == listed
