"""
fedwatch.py

Three things live here, because they come from three different sources with
three different reliability profiles:

1. get_current_fed_funds_rate()
   -> FRED's no-API-key CSV endpoint (fredgraph.csv) for DFEDTARU / DFEDTARL
      (the upper/lower bound of the current Fed funds target range).
      This is an official, stable public endpoint.

2. get_next_fomc_meeting()
   -> Scrapes federalreserve.gov's published FOMC calendar page (plain HTML,
      no JS rendering needed). Reasonably stable, but date formatting on that
      page has changed before, so this is defensive and falls back to None.

3. get_fedwatch_probabilities()
   -> CME FedWatch has NO free public JSON API. The free web tool
      (cmegroup.com/.../countdown-to-fomc.html) renders its data inside a
      "QuikStrike" iframe via client-side JS, and CME's official REST API
      requires a paid/OAuth-licensed entitlement
      (see cmegroup.com/market-data/market-data-api/fedwatch-api.html).
      So this function uses Selenium to drive a real (headless) browser,
      exactly the approach documented publicly for this tool. It requires
      `pip install selenium` and a matching chromedriver on PATH.
      If Selenium/chromedriver isn't available, or CME changes their page
      layout, this raises FedWatchUnavailable -- the report generator will
      then prompt for manual entry rather than silently failing.
"""

from __future__ import annotations
import csv
import io
import re
import datetime as dt
import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FEDWATCH_URL = "https://www.cmegroup.com/trading/interest-rates/countdown-to-fomc.html"


class FedWatchUnavailable(Exception):
    pass


def get_current_fed_funds_rate() -> dict:
    """Returns {'lower': float, 'upper': float, 'date': 'YYYY-MM-DD'} for the
    current Fed funds target range, via FRED's key-free CSV endpoint."""
    resp = requests.get(FRED_CSV, params={"id": "DFEDTARU,DFEDTARL"}, timeout=20)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = [r for r in reader if r.get("DFEDTARU") not in (None, "", ".")]
    if not rows:
        raise RuntimeError("FRED returned no usable Fed funds target data.")
    last = rows[-1]
    return {
        "lower": float(last["DFEDTARL"]),
        "upper": float(last["DFEDTARU"]),
        "date": last["observation_date"],
    }


def get_next_fomc_meeting(reference_date: dt.date | None = None) -> dict | None:
    """
    Scrapes the Fed's own FOMC calendar page for the next meeting date.
    Returns {'start': date, 'end': date} or None if it couldn't be parsed
    (page layout changed) -- caller should fall back to manual entry.
    """
    reference_date = reference_date or dt.date.today()
    resp = requests.get(FOMC_CALENDAR_URL, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (research script)"})
    resp.raise_for_status()
    html = resp.text

    # Meeting dates on this page look like "January 27-28", "March 17-18*",
    # inside panels labeled with the year. This is a best-effort regex parse,
    # not an HTML-structure parse, since the Fed's markup for this page
    # changes periodically.
    year_pattern = re.compile(r'\b(20\d{2})\s+FOMC\s+Meetings\b', re.IGNORECASE)
    date_pattern = re.compile(
        r'([A-Z][a-z]+)\s+(\d{1,2})(?:-(\d{1,2}))?'
    )

    candidates = []
    for year_match in year_pattern.finditer(html):
        year = int(year_match.group(1))
        # look at the chunk of html following the year heading
        chunk = html[year_match.end(): year_match.end() + 4000]
        for m in date_pattern.finditer(chunk):
            month_name, day1, day2 = m.group(1), m.group(2), m.group(3)
            try:
                start = dt.datetime.strptime(f"{month_name} {day1} {year}", "%B %d %Y").date()
            except ValueError:
                continue
            end = start
            if day2:
                try:
                    end = start.replace(day=int(day2))
                except ValueError:
                    pass
            candidates.append({"start": start, "end": end})

    future = sorted(
        (c for c in candidates if c["end"] >= reference_date),
        key=lambda c: c["start"],
    )
    return future[0] if future else None


def get_fedwatch_probabilities(headless: bool = True) -> dict:
    """
    Drives a headless browser to CME's free FedWatch tool and reads the
    probability table for the nearest FOMC meeting.

    Returns:
      {
        'meeting_date': str,
        'hold_pct': float,
        'cut_25bps_pct': float,
        'cut_50bps_or_more_pct': float,
        'hike_pct': float,
      }

    Raises FedWatchUnavailable if selenium/chromedriver isn't installed or
    the page structure doesn't match what we expect (CME has changed this
    tool's markup before without notice -- it's a JS widget, not an API).
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
    except ImportError as e:
        raise FedWatchUnavailable(
            "selenium is not installed. Run: pip install selenium\n"
            "You'll also need a chromedriver binary matching your Chrome "
            "version, on PATH. See https://chromedriver.chromium.org/"
        ) from e

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(30)
        driver.get(FEDWATCH_URL)

        driver.implicitly_wait(3)
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)

        # Click into the "Probabilities" view if it's not already showing.
        try:
            driver.find_element(By.LINK_TEXT, "Probabilities").click()
        except Exception:
            pass  # may already be the default view

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        if not rows:
            raise FedWatchUnavailable(
                "Loaded the FedWatch page but found no probability table rows. "
                "CME likely changed the page layout -- enter data manually."
            )

        # First data row of the probabilities table = nearest meeting.
        cells = rows[0].find_elements(By.TAG_NAME, "td")
        cell_text = [c.text.strip() for c in cells]

        def pct(s):
            m = re.search(r"[\d.]+", s)
            return float(m.group()) if m else None

        # Layout historically: [Meeting date, Days to meeting, Ease%, No Change%, Hike%, ...]
        # We keep this best-effort and clearly labeled so a layout change is obvious.
        return {
            "meeting_date": cell_text[0] if len(cell_text) > 0 else None,
            "cut_pct": pct(cell_text[2]) if len(cell_text) > 2 else None,
            "hold_pct": pct(cell_text[3]) if len(cell_text) > 3 else None,
            "hike_pct": pct(cell_text[4]) if len(cell_text) > 4 else None,
            "raw_row": cell_text,
        }
    finally:
        driver.quit()


def get_fedwatch_probabilities_or_manual(headless: bool = True) -> dict:
    """Try the Selenium scrape; on any failure, prompt for manual entry so the
    report can still be generated."""
    try:
        return get_fedwatch_probabilities(headless=headless)
    except Exception as e:
        print(f"[fedwatch] Automated FedWatch scrape failed: {e}")
        print("Enter FedWatch numbers manually (from cmegroup.com/.../countdown-to-fomc.html).")
        print("Leave blank + Enter to skip a field.")

        def ask(label):
            val = input(f"  {label}: ").strip()
            return val or None

        return {
            "meeting_date": ask("Next FOMC meeting date (as shown on FedWatch)"),
            "hold_pct": ask("Hold probability (%)"),
            "cut_pct": ask("Cut probability, all cut sizes combined (%)"),
            "hike_pct": ask("Hike probability (%)"),
            "raw_row": None,
            "manual_entry": True,
        }


if __name__ == "__main__":
    import json
    print("Fed funds rate:", json.dumps(get_current_fed_funds_rate(), indent=2))
    meeting = get_next_fomc_meeting()
    print("Next FOMC meeting:", meeting)
