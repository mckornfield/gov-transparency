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
    page.wait_for_selector("#bars rect")
    return errors


def test_index_renders_chart_table_and_headline(page, site_url):
    errors = open_index(page, site_url)
    assert page.locator("#bars rect").count() > 16
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


def test_headline_says_whether_transfers_are_included(page, site_url):
    open_index(page, site_url)
    assert "excluding transfers" in page.locator("#headline").inner_text().lower()
    assert "excluding transfers" in page.locator("#totals-method").text_content().lower()
    page.check("#transfers")
    page.wait_for_function("document.getElementById('headline').innerText.toLowerCase().includes('including transfers')")


def test_every_chart_has_a_data_table(page, site_url):
    open_index(page, site_url)
    assert page.locator("#totals-table tbody tr").count() == 13  # FY2011-23 actuals
    assert page.locator("#class-table tbody tr").count() >= 5
    page.check("input[name=basis][value=adopted]")
    page.wait_for_function("document.querySelectorAll('#totals-table tbody tr').length === 16")


def test_page_states_how_old_the_data_is(page, site_url):
    open_index(page, site_url)
    text = page.locator("#asof").inner_text()
    assert "FY2023" in text and "retrieved" in text.lower()


def test_bar_view_is_the_default_and_groups_the_long_tail(page, site_url):
    open_index(page, site_url)
    assert "All other" in page.locator("#bars").inner_text()
    assert page.locator("#treemap").is_hidden()
    assert page.locator("#expand").is_visible()


def test_expand_shows_every_group(page, site_url):
    open_index(page, site_url)
    page.click("#expand")
    page.wait_for_function("!document.getElementById('bars').innerText.includes('All other')")
    assert "expand=1" in page.url
    assert "top 15" in page.locator("#expand").inner_text().lower()


def test_treemap_is_still_available_behind_a_toggle(page, site_url):
    open_index(page, site_url)
    page.check("input[name=view][value=treemap]")
    page.wait_for_selector("#treemap rect.leaf")
    assert page.locator("#bars").is_hidden()
    assert "view=treemap" in page.url


def test_spending_type_colours_do_not_shift_between_views(page, site_url):
    open_index(page, site_url)
    def swatches():
        return page.evaluate("[...document.querySelectorAll('#legend .swatch')].map(e => e.style.background)")
    before = swatches()
    page.check("input[name=basis][value=adopted]")
    page.wait_for_function("document.getElementById('fy').max === '2026'")
    assert swatches() == before


def open_vendors(page, site_url, hash_=""):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/vendors.html{hash_}")
    page.wait_for_selector("#leader-table tbody tr")
    return errors


def test_vendors_page_shows_leaders_headline_and_honest_coverage(page, site_url):
    errors = open_vendors(page, site_url)
    assert page.locator("#leader-table tbody tr").count() == 25
    head = page.locator("#vhead").inner_text()
    assert "FY2026" in head and "vendors" in head and "$" in head
    coverage = page.locator("#vcoverage").inner_text().lower()
    assert "not directly comparable" in coverage and "less than $25,000" in coverage
    assert "not total spending" in coverage
    assert "% of the city" not in coverage  # the two totals are not nested, so no "coverage" percentage
    assert "pass-through" in page.locator("#passthrough-note").inner_text().lower()
    assert errors == []


def test_every_vendor_figure_has_a_method_drawer(page, site_url):
    open_vendors(page, site_url)
    assert page.locator("figure").count() == page.locator("figure details.method").count() >= 1


def test_vendor_search_finds_a_payee_and_shows_its_trend(page, site_url):
    open_vendors(page, site_url)
    page.locator("#q").press_sequentially("water authority")  # real keystrokes: the space must survive
    page.wait_for_selector("#search-table tbody tr")
    assert page.input_value("#q") == "water authority"
    assert "San Diego County Water Authority" in page.locator("#search-table").inner_text()
    assert "q=water%20authority" in page.url
    page.click("#search-table tbody tr button")
    page.wait_for_selector("#vendor-trend svg")
    assert page.locator("#vendor-trend rect").count() == 5


def test_vendor_search_with_regex_characters_is_literal_and_safe(page, site_url):
    errors = open_vendors(page, site_url)
    page.fill("#q", "(.*")
    page.wait_for_function("document.getElementById('search-empty').hidden === false")
    assert "no vendors" in page.locator("#search-empty").inner_text().lower()
    assert errors == []


def test_vendors_deep_link_restores_year_and_search(page, site_url):
    open_vendors(page, site_url, "#fy=2022&q=sdcers")
    assert page.input_value("#fy") == "2022"
    assert page.input_value("#q") == "sdcers"
    assert "SDCERS" in page.locator("#search-table").inner_text()
    assert "FY2022" in page.locator("#vhead").inner_text()


def test_vendors_page_has_no_horizontal_scroll_on_a_phone(page, site_url):
    page.set_viewport_size({"width": 390, "height": 800})
    open_vendors(page, site_url)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_nav_links_to_the_vendors_page_from_every_page(page, site_url):
    for path in ("/", "/methods.html"):
        page.goto(site_url + path)
        assert page.locator("nav a[href='vendors.html']").count() == 1


def test_peers_page_renders(page, site_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/peers.html")
    page.wait_for_selector("#peer-chart svg")
    assert "middle peer" in page.inner_text("#phead")
    assert page.locator("#peer-table tbody tr").count() == 8
    assert page.locator("#city-table tbody tr").count() == 12
    page.check("#kind-utility")
    page.wait_for_function("location.hash.includes('kinds=')")
    assert page.locator("#peer-table tbody tr").count() == 12
    assert page.locator("figure details.method").count() == 1
    assert not errors


def test_peers_deep_link_and_garbage_hash(page, site_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/peers.html#kinds=core,outside")
    page.wait_for_selector("#peer-chart svg")
    assert page.is_checked("#kind-outside") and not page.is_checked("#kind-utility")
    page.goto(f"{site_url}/peers.html#kinds=%00zzz")
    page.wait_for_selector("#peer-chart svg")
    assert page.is_checked("#kind-core")
    assert not errors
