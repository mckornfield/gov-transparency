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
    *{f"census/{y}_Individual_Unit_Files.zip.gz" for y in range(2019, 2025)},
    "bea/MARPP.zip.gz",
    "census/2024_methodology.pdf.gz",
    *{f"sandiego/vendor_payments_fy{fy}.pdf.gz" for fy in range(2022, 2027)},
    "treasury/mts_table9_fy2024_sep.json.gz",
    "census/nc-est2024-agesex-res.csv.gz",
    "cms/age_and_sex_csv_files.zip.gz",
    "cms/nhe_tables.zip.gz",
    "fns/snap_characteristics_fy2023.pdf.gz",
    "hud/US_2024_2020census.xlsx.gz",
    "irs/22in25ic.xls.gz",
    "irs/22in33ar.xls.gz",
    "cdc/nvsr75_02_births_final_2024.pdf.gz",
    "fns/keydata_jan2025_fy2024.pdf.gz",
    "ssa/statcomps_2025_5a.pdf.gz",
    "ssa/ssi_asr25.xlsx.gz",
    "dol/ar203_eta203.csv.gz",
    "ca/schedule9_2025_26_gb.pdf.gz",
    "ca/dss_5180_2025_26_gb.pdf.gz",
    "ca/ihss_program_data_jan2024.xlsx.gz",
    "ca/ca237cw_fy2023_24.xlsx.gz",
    "ca/dds_consumers_by_age_gender.csv.gz",
    "census/sc-est2024-agesex-civ.csv.gz",
    "ca/dds_pos_statewide_fy2023_24.xlsx.gz",
    "ca/medi_cal_eligibles_age_sex.csv.gz",
    "macpac/exhibit21_fy2023.xlsx.gz",
    "omb/hist_fy2027.zip.gz",
    "va/va_compensation_by_age_fy2024.csv.gz",
    "va/va_pension_by_age_fy2024.csv.gz",
    "calich/ca_spms.csv.gz",
    "calich/ca_spms_dictionary.csv.gz",
    *{f"hcd/{n}.pdf.gz" for n in ("hhap_r1_redir", "hhap_r2", "hhap_r3", "hhap_r4", "hhap_r5")},
    *{f"sandiego/hssd_budget_fy{fy}.pdf.gz" for fy in range(2023, 2027)},
    "hud/2007-2024-PIT-Counts-by-CoC.xlsb.gz",
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
