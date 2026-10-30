"""Fetch helpers: retrying GET, gzip raw copies, and the MANIFEST.csv of what was fetched."""
import csv
import gzip
import hashlib
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
FIELDS = ["path", "url", "retrieved", "sha256_original", "bytes_original"]


def get_with_retry(url: str, retries: int = 4, backoff: float = 2.0, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 300)
    for attempt in range(retries):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(backoff**attempt)


def save_raw(content: bytes, rel_path: str, url: str, raw_dir: Path = RAW,
             retrieved: str | None = None) -> Path:
    """Write content gzip-compressed to raw_dir/rel_path + '.gz' and upsert its MANIFEST row.

    The manifest hashes the ORIGINAL bytes, so a re-fetch can be compared without decompressing.
    """
    target = raw_dir / (rel_path + ".gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(target, "wb", mtime=0) as f:
        f.write(content)
    _upsert_manifest(raw_dir / "MANIFEST.csv", {
        "path": rel_path + ".gz",
        "url": url,
        "retrieved": retrieved or date.today().isoformat(),
        "sha256_original": hashlib.sha256(content).hexdigest(),
        "bytes_original": str(len(content)),
    })
    return target


def _upsert_manifest(path: Path, row: dict) -> None:
    rows = {}
    if path.exists():
        with path.open(newline="") as f:
            rows = {r["path"]: r for r in csv.DictReader(f)}
    rows[row["path"]] = row
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[k] for k in sorted(rows))
