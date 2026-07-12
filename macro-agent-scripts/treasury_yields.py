"""
treasury_yields.py

Pulls Daily Treasury Par Yield Curve rates from the U.S. Treasury's public,
no-key-required data feed:

    https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml
        ?data=daily_treasury_yield_curve&field_tdr_date_value_month=YYYYMM

This is the real, documented feed (Treasury's own "Treasury Daily Interest
Rate XML Feed" page) -- not a scrape of a rendered page -- so it's the most
stable data source in this project.

We pull the current month's data (falls back to the prior month automatically
near the start of a month/on weekends when today's row doesn't exist yet),
and also pull last week's row so we can report the week-over-week direction
for the 10-year.
"""

from __future__ import annotations
import datetime as dt
import xml.etree.ElementTree as ET
import requests

FEED_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/pages/xml"
)

# Maturity -> the column name Treasury uses in the Atom/XML feed
FIELD_MAP = {
    "2Y": "BC_2YEAR",
    "10Y": "BC_10YEAR",
    "30Y": "BC_30YEAR",
}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}


def _fetch_month(year_month: str) -> list[dict]:
    """year_month like '202607'. Returns list of {date, 2Y, 10Y, 30Y} rows, oldest first."""
    params = {
        "data": "daily_treasury_yield_curve",
        "field_tdr_date_value_month": year_month,
    }
    resp = requests.get(FEED_URL, params=params, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (research script)"})
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    rows = []
    for entry in root.findall("atom:entry", NS):
        props = entry.find("atom:content/m:properties", NS)
        if props is None:
            continue
        date_el = props.find("d:NEW_DATE", NS)
        if date_el is None or not date_el.text:
            continue
        date = date_el.text[:10]  # 'YYYY-MM-DDT00:00:00' -> 'YYYY-MM-DD'
        row = {"date": date}
        for label, field in FIELD_MAP.items():
            el = props.find(f"d:{field}", NS)
            row[label] = float(el.text) if el is not None and el.text else None
        rows.append(row)

    rows.sort(key=lambda r: r["date"])
    return rows


def get_yield_history(lookback_days: int = 10) -> list[dict]:
    """
    Returns yield rows covering at least `lookback_days` calendar days up to
    today, pulling the current month and (if needed, e.g. early in the month)
    the previous month too.
    """
    today = dt.date.today()
    months_needed = {today.strftime("%Y%m")}
    start = today - dt.timedelta(days=lookback_days + 5)
    months_needed.add(start.strftime("%Y%m"))

    all_rows: dict[str, dict] = {}
    for ym in sorted(months_needed):
        try:
            for row in _fetch_month(ym):
                all_rows[row["date"]] = row
        except requests.RequestException as e:
            print(f"[treasury_yields] WARNING: could not fetch {ym}: {e}")

    return [all_rows[d] for d in sorted(all_rows)]


def get_current_and_prior_week(lookback_days: int = 12) -> dict:
    """
    Returns a summary dict:
      {
        'latest_date': 'YYYY-MM-DD',
        'latest': {'2Y': .., '10Y': .., '30Y': ..},
        'prior_week_date': 'YYYY-MM-DD',
        'prior_week': {'2Y': .., '10Y': .., '30Y': ..},
        '10y_change_bps': float,
        '10y_direction': 'up' | 'down' | 'flat',
        'curve_2s10s_bps': float,   # 10Y - 2Y, in bps; negative = inverted
      }
    Raises RuntimeError if no data could be retrieved at all.
    """
    rows = get_yield_history(lookback_days=lookback_days)
    if not rows:
        raise RuntimeError("No treasury yield data retrieved -- check network/feed URL.")

    latest = rows[-1]

    # Find the row ~7 calendar days before latest (nearest trading day at or before that date)
    latest_date = dt.date.fromisoformat(latest["date"])
    target = latest_date - dt.timedelta(days=7)
    prior_candidates = [r for r in rows if dt.date.fromisoformat(r["date"]) <= target]
    prior = prior_candidates[-1] if prior_candidates else rows[0]

    def bps(a, b):
        if a is None or b is None:
            return None
        return round((a - b) * 100, 1)  # yields are in %, so *100 = bps

    change = bps(latest["10Y"], prior["10Y"])
    if change is None:
        direction = "unknown"
    elif change > 0.5:
        direction = "up"
    elif change < -0.5:
        direction = "down"
    else:
        direction = "flat"

    curve = None
    if latest["10Y"] is not None and latest["2Y"] is not None:
        curve = round((latest["10Y"] - latest["2Y"]) * 100, 1)

    return {
        "latest_date": latest["date"],
        "latest": {k: latest[k] for k in ("2Y", "10Y", "30Y")},
        "prior_week_date": prior["date"],
        "prior_week": {k: prior[k] for k in ("2Y", "10Y", "30Y")},
        "10y_change_bps": change,
        "10y_direction": direction,
        "curve_2s10s_bps": curve,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_current_and_prior_week(), indent=2))
