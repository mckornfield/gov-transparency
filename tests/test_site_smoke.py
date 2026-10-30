"""Loads the real site in Chromium. Needs network access (d3/Plot come from the jsDelivr CDN)
and `uv run playwright install chromium`."""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke
SITE = Path(__file__).resolve().parents[1] / "site"


@pytest.fixture(scope="module")
def site_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                             "--directory", str(SITE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()


def open_index(page, site_url, hash_=""):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/{hash_}")
    page.wait_for_selector("#treemap rect.leaf")
    return errors


def test_index_renders_chart_table_and_headline(page, site_url):
    errors = open_index(page, site_url)
    assert page.locator("#treemap rect.leaf").count() > 20
    assert page.locator("#table-body tr").count() > 10
    assert "FY2023" in page.locator("#headline").inner_text()
    assert "$" in page.locator("#headline").inner_text()
    assert errors == []


def test_every_figure_has_a_method_drawer(page, site_url):
    open_index(page, site_url)
    assert page.locator("figure").count() == page.locator("figure details.method").count() >= 2


def test_mode_toggle_updates_hash_and_table(page, site_url):
    open_index(page, site_url)
    before = page.locator("#value-head").inner_text()
    page.check("input[name=mode][value=perResident]")
    page.wait_for_function("location.hash.includes('mode=perResident')")
    assert page.locator("#value-head").inner_text() != before


def test_deep_link_restores_state(page, site_url):
    open_index(page, site_url, "#fy=2015&basis=actual&mode=total&transfers=1")
    assert page.input_value("#fy") == "2015"
    assert page.is_checked("#transfers")
    assert "FY2015" in page.locator("#headline").inner_text()


def test_garbage_hash_falls_back_without_errors(page, site_url):
    errors = open_index(page, site_url, "#fy=abc&basis=zzz&mode=%00")
    assert page.input_value("#fy") == "2023"
    assert errors == []


def test_year_slider_works_from_the_keyboard(page, site_url):
    open_index(page, site_url)
    page.focus("#fy")
    page.keyboard.press("ArrowLeft")
    page.wait_for_function("document.getElementById('fy').value === '2022'")
    assert "FY2022" in page.locator("#headline").inner_text()


def test_switching_to_adopted_budget_extends_the_years(page, site_url):
    open_index(page, site_url)
    page.check("input[name=basis][value=adopted]")
    page.wait_for_function("document.getElementById('fy').max === '2026'")


def test_no_horizontal_scroll_on_a_phone(page, site_url):
    page.set_viewport_size({"width": 390, "height": 800})
    open_index(page, site_url)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_methods_page(page, site_url):
    page.goto(f"{site_url}/methods.html")
    assert "methods" in page.locator("h1").inner_text().lower()
    assert "Transfers Out" in page.locator("main").inner_text()
