import csv
import gzip
import hashlib

import pytest
import requests

from sd_spend import io as sdio


def read_manifest(raw_dir):
    with (raw_dir / "MANIFEST.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_save_raw_writes_gzip_and_manifest(tmp_path):
    content = b"a,b\n1,2\n"
    target = sdio.save_raw(content, "x/data.csv", "http://example.test/data.csv",
                           raw_dir=tmp_path, retrieved="2026-10-29")
    assert target == tmp_path / "x" / "data.csv.gz"
    assert gzip.decompress(target.read_bytes()) == content
    (row,) = read_manifest(tmp_path)
    assert row == {
        "path": "x/data.csv.gz",
        "url": "http://example.test/data.csv",
        "retrieved": "2026-10-29",
        "sha256_original": hashlib.sha256(content).hexdigest(),
        "bytes_original": str(len(content)),
    }


def test_save_raw_upserts_same_path(tmp_path):
    sdio.save_raw(b"one", "d.csv", "http://u", raw_dir=tmp_path, retrieved="2026-01-01")
    sdio.save_raw(b"two", "d.csv", "http://u", raw_dir=tmp_path, retrieved="2026-02-02")
    sdio.save_raw(b"other", "a.csv", "http://v", raw_dir=tmp_path, retrieved="2026-02-02")
    rows = read_manifest(tmp_path)
    assert [r["path"] for r in rows] == ["a.csv.gz", "d.csv.gz"]
    assert rows[1]["sha256_original"] == hashlib.sha256(b"two").hexdigest()


class FakeResponse:
    def raise_for_status(self):
        pass


def test_get_with_retry_retries_then_succeeds(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("boom")
        return FakeResponse()

    monkeypatch.setattr(sdio.requests, "get", fake_get)
    monkeypatch.setattr(sdio.time, "sleep", lambda s: None)
    assert isinstance(sdio.get_with_retry("http://u"), FakeResponse)
    assert len(calls) == 3


def test_get_with_retry_raises_after_exhausting(monkeypatch):
    def always_fail(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(sdio.requests, "get", always_fail)
    monkeypatch.setattr(sdio.time, "sleep", lambda s: None)
    with pytest.raises(requests.ConnectionError):
        sdio.get_with_retry("http://u", retries=2)
