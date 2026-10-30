"""Checks against the committed processed vendor data and the raw PDFs."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sd_spend import vendors as v

ROOT = Path(__file__).resolve().parents[1]
table = pd.read_csv(ROOT / "data/processed/vendor_payments.csv", dtype={"vendor_ids": str})
site = json.loads((ROOT / "site/data/vendors.json").read_text())


def test_every_year_is_present_with_plausible_row_counts():
    counts = table.groupby("fy").size()
    assert list(counts.index) == [2022, 2023, 2024, 2025, 2026]
    assert counts.loc[2025] <= 1626 and counts.loc[2025] >= 1600  # 1,626 PDF rows, a few merged
    assert counts.loc[2022] >= 1500


def test_known_top_payees():
    top25 = table[table["fy"] == 2025].nlargest(1, "amount").iloc[0]
    assert top25["vendor_name"] == "San Diego County Water Authority"
    assert abs(top25["amount"] - 284_136_895.86) < 1
    top22 = table[table["fy"] == 2022].nlargest(1, "amount").iloc[0]
    assert "SDCERS" in top22["vendor_name"]


def test_one_company_under_two_vendor_ids_is_one_row():
    sdge = table[(table["fy"] == 2025) & (table["vendor_key"] == v.name_key("San Diego Gas and Electric"))]
    assert len(sdge) == 1
    assert "10019640" in sdge.iloc[0]["vendor_ids"] and "10010990" in sdge.iloc[0]["vendor_ids"]
    assert 78e6 < sdge.iloc[0]["amount"] < 79e6


def test_coverage_is_in_the_plausible_band_for_every_year():
    cov = {int(fy): c for fy, c in site["coverage"].items()}
    v.check_coverage(cov)
    assert sorted(cov) == [2022, 2023, 2024, 2025, 2026]


def test_site_json_matches_the_csv():
    assert site["years"] == [2022, 2023, 2024, 2025, 2026]
    for fy in site["years"]:
        json_total = sum(x["amounts"].get(str(fy), 0) for x in site["vendors"])
        csv_total = table.loc[table["fy"] == fy, "amount"].sum()
        assert abs(json_total - csv_total) <= 0.5 * len(site["vendors"]) + 1, fy


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
def test_re_extracting_a_raw_pdf_reproduces_the_processed_total():
    fy, df = v.parse_and_validate(v.pdf_to_text(ROOT / "data/raw/sandiego/vendor_payments_fy2025.pdf.gz"))
    assert fy == 2025
    assert abs(df["amount"].sum() - table.loc[table["fy"] == 2025, "amount"].sum()) < 1
