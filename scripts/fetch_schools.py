"""School district ledgers for San Diego County from the state's SACS unaudited actual data (2023-24).

The state publishes one self-extracting zip holding a 480MB Microsoft Access database. This script downloads it, exports
the tables with mdbtools (brew install mdbtools) and stores only the San Diego County rows and the code-title tables.

    uv run python scripts/fetch_schools.py
"""
import csv
import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from sd_spend.io import get_with_retry, save_raw

URL = "https://www3.cde.ca.gov/fiscal-downloads/sacs_data/2023-24/sacs2324.exe"
HEADERS = {"User-Agent": "gov-transparency/0.1 (open civic-data project; github.com/mckornfield/gov-transparency)"}
COUNTY = "37"  # San Diego
COUNTY_TABLES = {"UserGL": "ledger", "LEAs": "districts", "Charters": "charters"}
CODE_TABLES = {"Object": "objects", "Fund": "funds", "Function": "functions", "Resource": "resources", "Goal": "goals"}


def export(database: Path, table: str) -> str:
    return subprocess.run(["mdb-export", str(database), table], check=True, capture_output=True, text=True).stdout


def county_rows(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows([rows[0], *[[c.strip() for c in r] for r in rows[1:] if r[0].strip() == COUNTY]])
    return out.getvalue()


def main() -> None:
    if not shutil.which("mdb-export"):
        raise SystemExit("mdb-export (mdbtools) is needed to read the state's Access database: brew install mdbtools")
    archive = get_with_retry(URL, headers=HEADERS).content
    print("fetched", URL, len(archive), flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".mdb"))
            database = Path(z.extract(name, tmp))
        for table, label in COUNTY_TABLES.items():
            text = county_rows(export(database, table))
            save_raw(text.encode(), f"cde/sacs2324_san_diego_{label}.csv", URL)
            print("stored", label, text.count("\n") - 1, "rows")
        for table, label in CODE_TABLES.items():
            save_raw(export(database, table).encode(), f"cde/sacs2324_{label}.csv", URL)
            print("stored", label)


if __name__ == "__main__":
    main()
