"""BEA Regional Price Parities (RPP) by metropolitan area, used to put cities' spending on a common price level.

MARPP_MSA_2008_2024.csv: GeoFIPS (metro code), calendar-year columns, LineCode 1 = all items, US average = 100.
"""
import csv
import io
import zipfile

from sd_spend.census import CensusError

ALL_ITEMS = "1"


def parse_rpp(zip_bytes: bytes) -> dict[tuple[str, int], float]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = [n for n in z.namelist() if n.endswith("MARPP_MSA_2008_2024.csv")]
        if not names:
            raise CensusError("MARPP_MSA_2008_2024.csv not found in the BEA zip")
        text = z.read(names[0]).decode("latin-1")
    rpp = {}
    for row in csv.DictReader(io.StringIO(text)):
        if (row["LineCode"] or "").strip() != ALL_ITEMS:  # the footnote rows at the end have no columns
            continue
        fips = row["GeoFIPS"].strip().strip('"')
        for column, value in row.items():
            if column and column.strip().isdigit() and value and value.strip() not in ("", "(NA)"):
                rpp[(fips, int(column))] = float(value)
    return rpp


def fiscal_year_rpp(rpp: dict[tuple[str, int], float], msa: str, fy_end: str, survey_year: int) -> float:
    """The metro's price level over the fiscal year that ended on fy_end (MMDD) in survey year `survey_year`.

    Census survey year N covers fiscal years ending July N-1 .. June N. A fiscal year ending in month m of
    calendar year E has m months in E and 12-m in E-1, so the two calendar-year RPPs are blended by months.
    """
    month = int(fy_end[:2])
    end_year = survey_year - 1 if month >= 7 else survey_year
    try:
        late = rpp[(msa, end_year)]
        early = rpp[(msa, end_year - 1)] if month < 12 else late
    except KeyError as error:
        raise CensusError(f"no BEA price level for metro {msa} in {error.args[0][1]}") from None
    return (month * late + (12 - month) * early) / 12


def add_price_levels(tidy, peers_cfg: dict, rpp: dict[tuple[str, int], float], survey_year: int):
    """Add an `rpp` column: each city's metro price level over its own fiscal year."""
    msa = {peers_cfg["home"]: peers_cfg.get("home_msa")} | {p["id"]: p.get("msa") for p in peers_cfg["peers"]}
    out = tidy.copy()
    levels = {}
    for unit_id, fy_end in out[["unit_id", "fy_end"]].drop_duplicates().itertuples(index=False):
        if not msa.get(unit_id):
            raise CensusError(f"no metro (msa) configured for city {unit_id}")
        levels[unit_id] = fiscal_year_rpp(rpp, msa[unit_id], fy_end, survey_year)
    out["rpp"] = out["unit_id"].map(levels)
    return out
