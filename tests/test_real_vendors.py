"""Checks against the committed vendor data (built from the City's accounts-payable payments, PRA 26-11538) and the
City's published yearly vendor PDFs, which it must agree with."""
import gzip
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sd_spend import vendors as v
from sd_spend.payments import parse_payments

ROOT = Path(__file__).resolve().parents[1]
table = pd.read_csv(ROOT / "data/processed/vendor_payments.csv", dtype={"vendor_ids": str})
site = json.loads((ROOT / "site/data/vendors.json").read_text())


@pytest.fixture(scope="module")
def payments():
    return parse_payments(gzip.decompress((ROOT / "data/raw/sandiego/pra_26_11538_ap_detail.tsv.gz").read_bytes()).decode())


def test_every_year_is_present_with_plausible_counts_of_named_vendors():
    counts = table.groupby("fy").size()
    assert list(counts.index) == [2022, 2023, 2024, 2025, 2026, 2027]
    assert all(1200 < counts.loc[fy] < 1700 for fy in range(2022, 2027))
    assert site["partial"] == {"2027": "July to September 2026"} and site["full_years"] == [2022, 2023, 2024, 2025, 2026]


def test_known_top_payee():
    top = table[table["fy"] == 2025].nlargest(1, "amount").iloc[0]
    assert top["vendor_name"] == "San Diego County Water Authority"
    assert abs(top["amount"] - 284_136_895.86) < 1


def test_one_company_under_two_vendor_ids_is_one_row():
    sdge = table[(table["fy"] == 2025) & (table["vendor_key"] == v.loose_key("San Diego Gas and Electric"))]
    assert len(sdge) == 1
    assert "10019640" in sdge.iloc[0]["vendor_ids"] and "10010990" in sdge.iloc[0]["vendor_ids"]


def test_a_vendor_id_renamed_across_years_is_one_vendor():
    hits = table[table["vendor_ids"].str.contains("10036157")]  # "Shimmick Construction Inc" / "... Company Inc"
    assert hits["vendor_key"].nunique() == 1 and hits["fy"].nunique() >= 3


def test_only_vendors_paid_25000_in_a_year_are_named():
    assert (table["amount"] >= 25_000).all() and (table["vendor_name"].str.strip() != "").all()
    for e in site["vendors"]:
        assert e["name"] and all(a >= 25_000 for a in e["amounts"].values())


def test_the_stored_copy_names_a_payee_only_in_years_it_was_paid_25000(payments):
    per_year = payments.groupby(["vendor_id", "fy"]).agg(amount=("amount", "sum"), named=("vendor_name", lambda s: (s != "").all()),
                                                          blank=("vendor_name", lambda s: (s == "").all()))
    assert (per_year["named"] | per_year["blank"]).all()  # never named on some lines and blank on others
    assert (per_year.loc[per_year["named"], "amount"] >= 25_000).all()
    assert (per_year.loc[per_year["blank"], "amount"] < 25_000).all() and per_year["blank"].sum() > 3000


def test_department_and_type_detail_holds_only_named_vendor_years():
    detail = pd.read_csv(ROOT / "data/processed/vendor_payments_by_department.csv")
    named = set(zip(table["fy"], table["vendor_key"]))
    assert set(zip(detail["fy"], detail["vendor_key"])) <= named
    for e in site["vendors"]:
        assert set(e["by_dept"]) == set(e["by_type"]) == set(e["amounts"])


def test_named_and_unnamed_add_up_to_every_payment(payments):
    for fy in site["years"]:
        year = site["totals"][str(fy)]["all"]
        assert year["total"] == pytest.approx(payments.loc[payments["fy"] == fy, "amount"].sum(), abs=1)
        named = sum(e["amounts"].get(str(fy), 0) for e in site["vendors"])
        assert named + year["unnamed"]["amount"] == pytest.approx(year["total"], abs=len(site["vendors"]))
        departments = sum(d["total"] for d in site["totals"][str(fy)]["departments"].values())
        assert departments == pytest.approx(year["total"], abs=len(site["departments"]))
        assert sum(year["types"].values()) == pytest.approx(year["total"], abs=50)
        assert sum(year["funds"].values()) == pytest.approx(year["total"], abs=10)


def test_each_named_vendors_departments_and_types_add_up():
    for e in site["vendors"][:300]:
        for fy, amount in e["amounts"].items():
            assert sum(a for _, a in e["by_dept"][fy]) == pytest.approx(amount, abs=len(e["by_dept"][fy]))
            assert sum(a for _, a in e["by_type"][fy]) == pytest.approx(amount, abs=len(e["by_type"][fy]))


def test_monthly_totals_add_up_to_the_years():
    months, values = site["monthly"]["months"], site["monthly"]["all"]
    assert months[0] == "2021-07" and months[-1] == "2026-09" and len(months) == 63
    fy = lambda m: int(m[:4]) + (1 if int(m[5:]) >= 7 else 0)  # noqa: E731
    for year in site["years"]:
        assert sum(x for m, x in zip(months, values) if fy(m) == year) == pytest.approx(site["totals"][str(year)]["all"]["total"], abs=63)


def test_coverage_is_in_the_plausible_band_for_every_full_year():
    cov = {int(fy): c for fy, c in site["coverage"].items()}
    v.check_coverage(cov)
    assert sorted(cov) == [2022, 2023, 2024, 2025, 2026]


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
def test_payments_agree_with_the_citys_published_vendor_pdfs():
    """FY2023-FY2026: the City's yearly $25,000-or-more vendor lists add up to within 1% of the named payments here.
    FY2022's list also carried pension, health-plan and union payments that the later lists and this file leave out."""
    for fy in range(2022, 2027):
        _, df = v.parse_and_validate(v.pdf_to_text(ROOT / f"data/raw/sandiego/vendor_payments_fy{fy}.pdf.gz"))
        ours = table.loc[table["fy"] == fy, "amount"].sum()
        if fy == 2022:
            assert 0.9e9 < df["amount"].sum() - ours < 1.1e9
            assert df.loc[df["vendor_name"] == "SDCERS", "amount"].sum() > 8e8
        else:
            assert ours == pytest.approx(df["amount"].sum(), rel=0.01)


@pytest.mark.skipif(shutil.which("pdfinfo") is None, reason="needs poppler's pdfinfo")
def test_pdf_page_counts_match_what_the_reports_declare():
    expected = {2022: 38, 2023: 42, 2024: 46, 2025: 46, 2026: 43}
    for fy, pages in expected.items():
        assert v.pdf_page_count(ROOT / f"data/raw/sandiego/vendor_payments_fy{fy}.pdf.gz") == pages
