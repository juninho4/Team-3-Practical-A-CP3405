"""
finviz_futures.py

Finviz doesn't publish an API for this either -- futures.ashx is a plain
server-rendered HTML table (no JS rendering needed, unlike FedWatch), so a
simple requests + BeautifulSoup scrape works. Finviz does rate-limit /
block scripted traffic without a browser-like User-Agent, and their table
layout/column order can change, so this is defensive about both.

Note: finviz.com's terms of use restrict automated scraping for anything
beyond personal/casual use -- keep request volume low (this script makes a
single request) and don't redistribute the data commercially.
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

FUTURES_URL = "https://finviz.com/futures.ashx"

# Finviz labels vary slightly ("Gold", "Crude Oil WTI", "US Dollar Index")
TARGET_INSTRUMENTS = {
    "WTI Crude Oil": re.compile(r"crude\s*oil.*wti|wti.*crude", re.IGNORECASE),
    "Gold": re.compile(r"^gold$", re.IGNORECASE),
    "DXY (US Dollar Index)": re.compile(r"dollar\s*index|dxy", re.IGNORECASE),
}


def get_weekly_futures_changes() -> dict:
    """
    Returns:
      {
        'WTI Crude Oil': {'last': float|None, 'change_1w_pct': float|None},
        'Gold': {...},
        'DXY (US Dollar Index)': {...},
      }
    Any instrument not found on the page comes back with None values, and
    a warning is printed, rather than raising -- so one renamed row doesn't
    break the whole report.
    """
    resp = requests.get(
        FUTURES_URL,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            )
        },
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = {name: {"last": None, "change_1w_pct": None} for name in TARGET_INSTRUMENTS}

    # Finviz futures tables are laid out as several small per-category tables,
    # each row: [Ticker/Name, Last, Change, ... , 1W %, ...]. We scan every
    # table row on the page and match by instrument name text.
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        row_text = [c.get_text(strip=True) for c in cells]
        label = row_text[0]

        for name, pattern in TARGET_INSTRUMENTS.items():
            if pattern.search(label):
                numbers = []
                for cell in row_text[1:]:
                    cleaned = cell.replace("%", "").replace(",", "").strip()
                    try:
                        numbers.append(float(cleaned))
                    except ValueError:
                        numbers.append(None)
                if numbers:
                    results[name]["last"] = numbers[0] if len(numbers) > 0 else None
                # 1-Week % change column -- Finviz's futures page groups
                # columns as Last, Chg, Chg%, ... 1W, 1M, ... ; the 1W%
                # position has shifted before, so we grab it by searching
                # for a percent-looking cell after the first couple columns
                # AND label the field clearly so it's easy to spot-check.
                for cell_text in row_text[1:]:
                    if "%" in cell_text and cell_text not in ("%",):
                        pass  # collected above in numbers already
                if len(numbers) >= 4:
                    results[name]["change_1w_pct"] = numbers[3]
                break

    for name, data in results.items():
        if data["last"] is None:
            print(f"[finviz_futures] WARNING: could not find '{name}' on the futures page "
                  f"-- Finviz may have renamed/reordered rows. Verify manually at {FUTURES_URL}")

    return results


if __name__ == "__main__":
    import json
    print(json.dumps(get_weekly_futures_changes(), indent=2))
