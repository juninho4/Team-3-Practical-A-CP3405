#!/usr/bin/env python3
"""R6 Data Collector.

Fetches the latest closes for SPX, NDX, IWM and all 11 S&P 500 sector
ETFs, writes one CSV file, builds a local HTML evidence page, and screenshots
that page with a hidden browser. The default workflow never displays a browser
window or visits Finviz. Original Finviz/Yahoo webpage screenshots remain
available as an optional legacy mode.

Normal run:
    python r6_data_collector.py

Historical/reproducible run:
    python r6_data_collector.py --as-of 2026-07-10

Custom output path:
    python r6_data_collector.py --output C:/my_repo/vW29/evidence/my_actuals.csv

CSV-only run (skip locally generated PNG evidence):
    python r6_data_collector.py --skip-screenshots

Optional original webpage screenshots (may trigger security verification):
    python r6_data_collector.py --web-screenshots
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
SOURCE_NAME = "Yahoo Finance chart API"
FINVIZ_PRICES_1W = "https://finviz.com/futures?p=w"
FINVIZ_PERFORMANCE_1W = "https://finviz.com/futures_performance?v=12"


@dataclass(frozen=True)
class Instrument:
    ticker: str
    code: str
    name: str
    category: str


@dataclass(frozen=True)
class SectorPage:
    name: str
    filename: str
    url: str


# Website-required instruments: SPX, NDX, IWM and all 11 sector ETFs.
INSTRUMENTS = [
    Instrument("^GSPC", "SPX", "S&P 500 Index", "Index"),
    Instrument("^NDX", "NDX", "Nasdaq 100 Index", "Index"),
    Instrument("IWM", "IWM", "Russell 2000 ETF", "Index ETF"),
    Instrument("XLK", "XLK", "Technology Select Sector SPDR", "Sector ETF"),
    Instrument("XLV", "XLV", "Health Care Select Sector SPDR", "Sector ETF"),
    Instrument("XLF", "XLF", "Financial Select Sector SPDR", "Sector ETF"),
    Instrument("XLY", "XLY", "Consumer Discretionary Select Sector SPDR", "Sector ETF"),
    Instrument("XLC", "XLC", "Communication Services Select Sector SPDR", "Sector ETF"),
    Instrument("XLI", "XLI", "Industrial Select Sector SPDR", "Sector ETF"),
    Instrument("XLP", "XLP", "Consumer Staples Select Sector SPDR", "Sector ETF"),
    Instrument("XLE", "XLE", "Energy Select Sector SPDR", "Sector ETF"),
    Instrument("XLB", "XLB", "Materials Select Sector SPDR", "Sector ETF"),
    Instrument("XLRE", "XLRE", "Real Estate Select Sector SPDR", "Sector ETF"),
    Instrument("XLU", "XLU", "Utilities Select Sector SPDR", "Sector ETF"),
]

SECTOR_PAGES = [
    SectorPage("Technology", "Technology", "https://finance.yahoo.com/sectors/technology/"),
    SectorPage("Communication Services", "Communication_Services", "https://finance.yahoo.com/sectors/communication-services/"),
    SectorPage("Consumer Cyclical", "Consumer_Cyclical", "https://finance.yahoo.com/sectors/consumer-cyclical/"),
    SectorPage("Consumer Defensive", "Consumer_Defensive", "https://finance.yahoo.com/sectors/consumer-defensive/"),
    SectorPage("Energy", "Energy", "https://finance.yahoo.com/sectors/energy/"),
    SectorPage("Financial Services", "Financial_Services", "https://finance.yahoo.com/sectors/financial-services/"),
    SectorPage("Healthcare", "Healthcare", "https://finance.yahoo.com/sectors/healthcare/"),
    SectorPage("Industrials", "Industrials", "https://finance.yahoo.com/sectors/industrials/"),
    SectorPage("Basic Materials", "Basic_Materials", "https://finance.yahoo.com/sectors/basic-materials/"),
    SectorPage("Real Estate", "Real_Estate", "https://finance.yahoo.com/sectors/real-estate/"),
    SectorPage("Utilities", "Utilities", "https://finance.yahoo.com/sectors/utilities/"),
]

CSV_FIELDS = [
    "week",
    "fetched_at_sgt",
    "ticker",
    "code",
    "name",
    "category",
    "market_date",
    "close",
    "previous_close",
    "change_1d",
    "return_1d_pct",
    "close_5_sessions_ago",
    "return_5d_pct",
    "currency",
    "exchange",
    "source",
    "source_url",
    "status",
    "error",
]


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD, for example 2026-07-10"
        ) from exc


def singapore_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def project_root() -> Path:
    """Return the project folder when this file is stored in project/py/."""
    script_directory = Path(__file__).resolve().parent

    # Final integrated layout: project/py/r6_data_collector.py
    if script_directory.name.casefold() == "py":
        return script_directory.parent

    # Development fallback: find a parent that already looks like the project.
    for parent in [script_directory, *script_directory.parents]:
        if (parent / "app").is_dir() and (parent / "py").is_dir():
            return parent

    # Before the full project is assembled, treat the script's parent as project.
    return script_directory.parent


def default_evidence_directory() -> Path:
    iso_week = singapore_now().date().isocalendar().week
    return project_root().parent / f"vW{iso_week:02d}" / "evidence"


def unix_timestamp(day: date) -> int:
    moment = datetime.combine(day, datetime_time.min, tzinfo=timezone.utc)
    return int(moment.timestamp())


def yahoo_urls(ticker: str, start: date, end: date) -> list[str]:
    encoded = urllib.parse.quote(ticker, safe="")
    query = urllib.parse.urlencode(
        {
            "period1": unix_timestamp(start),
            "period2": unix_timestamp(end + timedelta(days=2)),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?{query}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?{query}",
    ]


def request_json(url: str, retries: int = 3, timeout: int = 20) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt * 1.5)
    raise RuntimeError(str(last_error or "Unknown network error"))


def valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def extract_prices(payload: dict[str, Any], as_of: date) -> tuple[list[tuple[date, float]], dict[str, str]]:
    chart = payload.get("chart", {})
    api_error = chart.get("error")
    if api_error:
        raise RuntimeError(api_error.get("description") or str(api_error))

    results = chart.get("result") or []
    if not results:
        raise RuntimeError("Yahoo returned no chart result")

    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quotes = indicators.get("quote") or []
    closes = quotes[0].get("close", []) if quotes else []
    adjusted_sets = indicators.get("adjclose") or []
    adjusted = adjusted_sets[0].get("adjclose", []) if adjusted_sets else []

    prices: dict[date, float] = {}
    for index, raw_timestamp in enumerate(timestamps):
        raw_close = adjusted[index] if index < len(adjusted) else None
        if not valid_number(raw_close):
            raw_close = closes[index] if index < len(closes) else None
        if not valid_number(raw_close):
            continue

        market_day = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc).date()
        if market_day <= as_of:
            prices[market_day] = float(raw_close)

    ordered = sorted(prices.items())
    if not ordered:
        raise RuntimeError(f"No valid close was available on or before {as_of}")

    metadata = result.get("meta") or {}
    return ordered, {
        "currency": str(metadata.get("currency") or ""),
        "exchange": str(metadata.get("exchangeName") or metadata.get("fullExchangeName") or ""),
    }


def percent_change(latest: float, earlier: float) -> float:
    if earlier == 0:
        return math.nan
    return ((latest / earlier) - 1.0) * 100.0


def rounded(value: float, decimals: int = 4) -> str:
    if not math.isfinite(value):
        return ""
    return f"{value:.{decimals}f}"


def fetch_instrument(instrument: Instrument, as_of: date, fetched_at: str) -> dict[str, str]:
    start = as_of - timedelta(days=45)
    urls = yahoo_urls(instrument.ticker, start, as_of)
    errors: list[str] = []

    for url in urls:
        try:
            prices, metadata = extract_prices(request_json(url), as_of)
            latest_day, latest_close = prices[-1]
            previous_close = prices[-2][1] if len(prices) >= 2 else math.nan
            five_day_close = prices[-6][1] if len(prices) >= 6 else prices[0][1]

            return {
                "week": f"{latest_day.isocalendar().year}-W{latest_day.isocalendar().week:02d}",
                "fetched_at_sgt": fetched_at,
                "ticker": instrument.ticker,
                "code": instrument.code,
                "name": instrument.name,
                "category": instrument.category,
                "market_date": latest_day.isoformat(),
                "close": rounded(latest_close),
                "previous_close": rounded(previous_close),
                "change_1d": rounded(latest_close - previous_close),
                "return_1d_pct": rounded(percent_change(latest_close, previous_close)),
                "close_5_sessions_ago": rounded(five_day_close),
                "return_5d_pct": rounded(percent_change(latest_close, five_day_close)),
                "currency": metadata["currency"],
                "exchange": metadata["exchange"],
                "source": SOURCE_NAME,
                "source_url": url,
                "status": "ok",
                "error": "",
            }
        except Exception as exc:
            errors.append(f"{urllib.parse.urlparse(url).netloc}: {exc}")

    return {
        "week": "",
        "fetched_at_sgt": fetched_at,
        "ticker": instrument.ticker,
        "code": instrument.code,
        "name": instrument.name,
        "category": instrument.category,
        "market_date": "",
        "close": "",
        "previous_close": "",
        "change_1d": "",
        "return_1d_pct": "",
        "close_5_sessions_ago": "",
        "return_5d_pct": "",
        "currency": "",
        "exchange": "",
        "source": SOURCE_NAME,
        "source_url": urls[0],
        "status": "error",
        "error": " | ".join(errors),
    }


def collect(as_of: date, workers: int = 4) -> list[dict[str, str]]:
    fetched_at = singapore_now().isoformat(timespec="seconds")
    results: dict[str, dict[str, str]] = {}

    print(f"[R6] Fetching {len(INSTRUMENTS)} instruments as of {as_of}...")
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(INSTRUMENTS)))) as executor:
        futures = {
            executor.submit(fetch_instrument, instrument, as_of, fetched_at): instrument
            for instrument in INSTRUMENTS
        }
        for future in as_completed(futures):
            instrument = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    field: "" for field in CSV_FIELDS
                }
                row.update(
                    {
                        "fetched_at_sgt": fetched_at,
                        "ticker": instrument.ticker,
                        "code": instrument.code,
                        "name": instrument.name,
                        "category": instrument.category,
                        "source": SOURCE_NAME,
                        "status": "error",
                        "error": str(exc),
                    }
                )
            results[instrument.ticker] = row
            marker = "OK" if row["status"] == "ok" else "FAILED"
            print(f"[R6] {marker}: {instrument.code}")

    # Preserve the website-required order in the CSV.
    return [results[instrument.ticker] for instrument in INSTRUMENTS]


def dataset_week(rows: list[dict[str, str]], fallback: date) -> str:
    market_dates = [
        date.fromisoformat(row["market_date"])
        for row in rows
        if row.get("status") == "ok" and row.get("market_date")
    ]
    reference = max(market_dates) if market_dates else fallback
    iso = reference.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def write_csv(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


def row_number(row: dict[str, str], field: str) -> float | None:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def evidence_footer(rows: list[dict[str, str]], csv_path: Path) -> str:
    fetched_at = next(
        (row.get("fetched_at_sgt", "") for row in rows if row.get("fetched_at_sgt")),
        singapore_now().isoformat(timespec="seconds"),
    )
    return (
        "Source: Yahoo Finance chart API | "
        f"Generated: {fetched_at} | CSV: {csv_path.name} | "
        "R6 browser screenshot of a local evidence page"
    )


def metric_text(value: float | None, suffix: str = "%") -> str:
    return f"{value:+.2f}{suffix}" if value is not None else "N/A"


def metric_class(value: float | None) -> str:
    if value is None:
        return "neutral"
    return "positive" if value >= 0 else "negative"


def return_bar_html(label: str, value: float | None, scale: float) -> str:
    numeric = value if value is not None else 0.0
    width = min(46.0, abs(numeric) / max(scale, 0.01) * 46.0)
    direction = "positive" if numeric >= 0 else "negative"
    return (
        '<div class="bar-row">'
        f'<div class="bar-label">{html.escape(label)}</div>'
        '<div class="bar-track"><div class="zero-line"></div>'
        f'<div class="bar {direction}" style="width:{width:.2f}%"></div></div>'
        f'<div class="bar-value {metric_class(value)}">{metric_text(value)}</div>'
        "</div>"
    )


def build_local_evidence_html(
    rows: list[dict[str, str]], week: str, output_dir: Path, csv_path: Path
) -> tuple[Path, list[tuple[str, Path]]]:
    valid_rows = [row for row in rows if row.get("status") == "ok"]
    sector_rows = [row for row in valid_rows if row.get("category") == "Sector ETF"]
    if not valid_rows:
        raise RuntimeError("No successful market rows were available for evidence")
    if not sector_rows:
        raise RuntimeError("No successful sector ETF rows were available for evidence")

    table_rows: list[str] = []
    for row in valid_rows:
        close = row_number(row, "close")
        one_day = row_number(row, "return_1d_pct")
        five_day = row_number(row, "return_5d_pct")
        table_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(row.get('code', ''))}</strong></td>"
            f"<td>{html.escape(row.get('name', ''))}</td>"
            f"<td>{html.escape(row.get('market_date', ''))}</td>"
            f"<td>{f'{close:,.2f}' if close is not None else 'N/A'}</td>"
            f'<td class="{metric_class(one_day)}">{metric_text(one_day)}</td>'
            f'<td class="{metric_class(five_day)}">{metric_text(five_day)}</td>'
            "</tr>"
        )

    performance = [
        (row.get("code", ""), row_number(row, "return_5d_pct"))
        for row in valid_rows
    ]
    performance.sort(key=lambda item: item[1] if item[1] is not None else -999, reverse=True)
    performance_scale = max(
        [abs(value) for _, value in performance if value is not None] or [1.0]
    )
    performance_bars = "".join(
        return_bar_html(code, value, performance_scale) for code, value in performance
    )

    footer = html.escape(evidence_footer(rows, csv_path))
    source_url = next(
        (row.get("source_url", "") for row in valid_rows if row.get("source_url")),
        "https://query1.finance.yahoo.com/v8/finance/chart/",
    )
    source_line = html.escape(source_url)

    sector_sections: list[str] = []
    screenshot_specs: list[tuple[str, Path]] = [
        ("closing-prices", output_dir / f"r6_closing_prices_{week}.png"),
        ("weekly-performance", output_dir / f"r6_1W_performance_{week}.png"),
    ]
    for row in sector_rows:
        code = row.get("code", "Sector")
        close = row_number(row, "close")
        one_day = row_number(row, "return_1d_pct")
        five_day = row_number(row, "return_5d_pct")
        sector_scale = max(abs(one_day or 0.0), abs(five_day or 0.0), 0.25)
        sector_sections.append(
            f'<section class="evidence" id="sector-{html.escape(code)}">'
            '<div class="eyebrow">R6 SECTOR ETF EVIDENCE</div>'
            f"<h1>{html.escape(code)} — {html.escape(row.get('name', 'Sector ETF'))}</h1>"
            f'<div class="subtitle">Market week {html.escape(week)}</div>'
            '<div class="stat-grid">'
            f'<div class="stat"><span>Close</span><strong>{f"{close:,.2f}" if close is not None else "N/A"}</strong></div>'
            f'<div class="stat"><span>Market date</span><strong>{html.escape(row.get("market_date", "N/A"))}</strong></div>'
            f'<div class="stat"><span>1-day return</span><strong class="{metric_class(one_day)}">{metric_text(one_day)}</strong></div>'
            f'<div class="stat"><span>1-week return</span><strong class="{metric_class(five_day)}">{metric_text(five_day)}</strong></div>'
            "</div>"
            '<div class="sector-bars">'
            f'{return_bar_html("1 day", one_day, sector_scale)}'
            f'{return_bar_html("1 week (5 sessions)", five_day, sector_scale)}'
            "</div>"
            f'<div class="source-url">Source URL: {source_line}</div>'
            f'<div class="footer">{footer}</div>'
            "</section>"
        )
        screenshot_specs.append(
            (
                f"sector-{code}",
                output_dir / "sectors" / f"r6_sector_1W_{week}_{code}.png",
            )
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>R6 Evidence {html.escape(week)}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 28px; background: #e2e8f0; color: #0f172a; font-family: Arial, Helvetica, sans-serif; }}
.evidence {{ width: 1440px; min-height: 860px; margin: 0 auto 28px; padding: 48px 58px 30px; background: white; display: flex; flex-direction: column; overflow: hidden; }}
.eyebrow {{ color: #2563eb; font-size: 15px; font-weight: 800; letter-spacing: 0.12em; }}
h1 {{ margin: 10px 0 4px; font-size: 40px; line-height: 1.12; }}
.subtitle {{ color: #475569; font-size: 19px; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 17px; }}
th {{ background: #0f172a; color: white; padding: 10px 12px; text-align: left; }}
td {{ border: 1px solid #cbd5e1; padding: 8px 12px; }}
tbody tr:nth-child(odd) {{ background: #f8fafc; }}
.positive {{ color: #15803d; font-weight: 800; }}
.negative {{ color: #b91c1c; font-weight: 800; }}
.neutral {{ color: #64748b; font-weight: 700; }}
.chart {{ margin-top: 4px; padding: 12px 0; }}
.bar-row {{ display: grid; grid-template-columns: 110px 1fr 105px; align-items: center; gap: 14px; min-height: 43px; }}
.bar-label {{ text-align: right; font-size: 17px; font-weight: 800; }}
.bar-track {{ height: 26px; background: #f1f5f9; position: relative; border-radius: 3px; overflow: hidden; }}
.zero-line {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: #334155; z-index: 2; }}
.bar {{ position: absolute; top: 3px; bottom: 3px; opacity: 0.92; }}
.bar.positive {{ left: 50%; background: #15803d; }}
.bar.negative {{ right: 50%; background: #b91c1c; }}
.bar-value {{ font-size: 17px; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin: 28px 0 52px; }}
.stat {{ border: 1px solid #cbd5e1; border-radius: 12px; padding: 20px; background: #f8fafc; }}
.stat span {{ display: block; color: #64748b; font-size: 16px; margin-bottom: 8px; }}
.stat strong {{ display: block; font-size: 28px; }}
.sector-bars .bar-row {{ min-height: 92px; grid-template-columns: 210px 1fr 120px; }}
.sector-bars .bar-track {{ height: 52px; }}
.sector-bars .bar-label, .sector-bars .bar-value {{ font-size: 21px; }}
.source-url {{ margin-top: auto; color: #475569; font-size: 13px; overflow-wrap: anywhere; }}
.footer {{ margin-top: 10px; border-top: 1px solid #cbd5e1; padding-top: 10px; color: #475569; font-size: 13px; text-align: center; }}
</style>
</head>
<body>
<section class="evidence" id="closing-prices">
  <div class="eyebrow">R6 MARKET EVIDENCE</div>
  <h1>Market Closing Prices — {html.escape(week)}</h1>
  <div class="subtitle">SPX, NDX, IWM and 11 S&amp;P 500 sector ETFs</div>
  <table>
    <thead><tr><th>Code</th><th>Instrument</th><th>Market date</th><th>Close</th><th>1D</th><th>1W (5 sessions)</th></tr></thead>
    <tbody>{''.join(table_rows)}</tbody>
  </table>
  <div class="source-url">Source URL: {source_line}</div>
  <div class="footer">{footer}</div>
</section>
<section class="evidence" id="weekly-performance">
  <div class="eyebrow">R6 MARKET EVIDENCE</div>
  <h1>One-Week Market Performance — {html.escape(week)}</h1>
  <div class="subtitle">Return over the latest five market sessions</div>
  <div class="chart">{performance_bars}</div>
  <div class="source-url">Source URL: {source_line}</div>
  <div class="footer">{footer}</div>
</section>
{''.join(sector_sections)}
</body>
</html>
"""
    html_path = output_dir / f"r6_evidence_{week}.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(document, encoding="utf-8")
    print(f"[R6] Local evidence webpage created: {html_path}")
    return html_path, screenshot_specs


def capture_local_evidence_screenshots(
    html_path: Path, screenshot_specs: list[tuple[str, Path]]
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required. Run: pip install playwright; "
            "then: playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        try:
            launch_options: dict[str, Any] = {"headless": True}
            # Windows already includes Edge. Using its installed binary avoids
            # a separate Chromium download while still keeping the window hidden.
            if os.name == "nt":
                launch_options["channel"] = "msedge"
            browser = playwright.chromium.launch(**launch_options)
        except Exception as exc:
            if os.name == "nt":
                raise RuntimeError(
                    "Microsoft Edge could not be started headlessly. Confirm Edge is installed."
                ) from exc
            raise RuntimeError("Chromium is not installed. Run: playwright install chromium") from exc
        try:
            page = browser.new_page(
                viewport={"width": 1600, "height": 1000},
                device_scale_factor=1,
            )
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=30000)
            for element_id, output in screenshot_specs:
                output.parent.mkdir(parents=True, exist_ok=True)
                locator = page.locator(f"#{element_id}")
                locator.wait_for(state="visible", timeout=10000)
                locator.screenshot(path=str(output), animations="disabled")
                print(f"[R6] Browser screenshot saved: {output}")
        finally:
            browser.close()


def generate_local_evidence(
    rows: list[dict[str, str]], week: str, output_dir: Path, csv_path: Path
) -> list[str]:
    """Build a local webpage and screenshot it with an invisible browser."""
    for filename in [
        f"finviz_closing_prices_{week}.png",
        f"finviz_1W_{week}.png",
    ]:
        obsolete = output_dir / filename
        if obsolete.is_file():
            obsolete.unlink()
            print(f"[R6] Removed obsolete webpage screenshot: {obsolete}")

    try:
        html_path, specs = build_local_evidence_html(rows, week, output_dir, csv_path)
        capture_local_evidence_screenshots(html_path, specs)
        return []
    except Exception as exc:
        message = f"local webpage screenshot: {exc}"
        print(f"[R6] Local evidence failed: {message}", file=sys.stderr)
        return [message]


def browser_goto(page: Any, url: str, timeout_error: type[Exception], wait_ms: int = 6000) -> None:
    print(f"[R6] Opening screenshot source: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=70000)
    except timeout_error:
        print("[R6] Page timeout; attempting to capture the loaded content.")
    page.wait_for_timeout(wait_ms)
    close_popups(page)
    page.wait_for_timeout(800)


def finviz_verification_active(page: Any) -> bool:
    """Detect Cloudflare/Finviz verification pages before taking evidence."""
    try:
        title = page.title().casefold()
    except Exception:
        title = ""
    try:
        body = page.locator("body").inner_text(timeout=2000).casefold()
    except Exception:
        body = ""

    challenge_phrases = [
        "performing security verification",
        "verifies you are not a bot",
        "verify you are human",
        "checking your browser",
        "just a moment",
        "cloudflare",
    ]
    combined = f"{title}\n{body}"
    return any(phrase in combined for phrase in challenge_phrases)


def wait_for_finviz_verification(page: Any, maximum_seconds: int = 60) -> None:
    """Wait for legitimate browser verification; never save the challenge page."""
    if not finviz_verification_active(page):
        return

    print("")
    print("[R6] Finviz security verification detected.")
    print("[R6] Edge is minimized. Restore it from the taskbar if manual verification is required.")
    print("[R6] This browser profile is saved, so later runs can reuse its cookies.")

    deadline = time.time() + maximum_seconds
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        if not finviz_verification_active(page):
            page.wait_for_timeout(2500)
            print("[R6] Finviz verification completed.")
            return

    raise RuntimeError(
        "Finviz verification did not complete within 60 seconds. "
        "The incorrect verification-page screenshot was not saved."
    )


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def find_edge_executable() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def connect_to_normal_edge(playwright: Any) -> tuple[Any, Any]:
    """Start normal Edge outside Playwright, then connect through CDP."""
    port = 9223
    if not port_open("127.0.0.1", port):
        edge = find_edge_executable()
        if edge is None:
            raise RuntimeError("Microsoft Edge executable was not found")

        # Use a new profile name so an earlier Playwright-launched profile does
        # not carry the same Finviz challenge state.
        profile = project_root() / "app" / "r6_edge_profile"
        profile.mkdir(parents=True, exist_ok=True)
        command = [
            str(edge),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-minimized",
            FINVIZ_PRICES_1W,
        ]
        subprocess.Popen(command, cwd=project_root())
        print("[R6] Started normal Microsoft Edge minimized for Finviz evidence.")

        deadline = time.time() + 30
        while time.time() < deadline:
            if port_open("127.0.0.1", port):
                break
            time.sleep(1)
        else:
            raise RuntimeError("Edge debugging port 9223 did not open")

    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("Connected to Edge, but no browser context was available")
    return browser, contexts[0]


def close_popups(page: Any) -> None:
    selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('Reject all')",
        "button:has-text('Reject All')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('Continue')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "[aria-label='Close']",
        "[title='Close']",
    ]
    for selector in selectors:
        try:
            item = page.locator(selector).first
            if item.is_visible(timeout=400):
                item.click(timeout=2000)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def scroll_top(page: Any) -> None:
    try:
        page.keyboard.press("Home")
        page.evaluate(
            """
            () => {
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
                for (const element of document.querySelectorAll('*')) {
                    try { element.scrollTop = 0; } catch (error) {}
                }
            }
            """
        )
        page.wait_for_timeout(700)
    except Exception:
        pass


def add_time_tag(page: Any, label: str) -> None:
    captured_at = singapore_now().strftime("%Y-%m-%d %H:%M:%S SGT")
    page.evaluate(
        """
        ({capturedAt, label}) => {
            const old = document.getElementById('r6-time-tag');
            if (old) old.remove();
            const tag = document.createElement('div');
            tag.id = 'r6-time-tag';
            tag.textContent = `R6 captured: ${capturedAt} | ${label}`;
            tag.style.position = 'fixed';
            tag.style.left = '10px';
            tag.style.bottom = '10px';
            tag.style.zIndex = '2147483647';
            tag.style.background = 'rgba(255,255,255,0.94)';
            tag.style.color = '#111';
            tag.style.border = '1px solid #333';
            tag.style.padding = '4px 7px';
            tag.style.borderRadius = '4px';
            tag.style.fontFamily = 'Arial, sans-serif';
            tag.style.fontSize = '11px';
            tag.style.fontWeight = '600';
            document.body.appendChild(tag);
        }
        """,
        {"capturedAt": captured_at, "label": label},
    )


def save_viewport(page: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    page.screenshot(path=str(path), full_page=False)
    print(f"[R6] Screenshot saved: {path}")


def click_yahoo_5d(page: Any) -> None:
    clicked = False
    try:
        pattern = re.compile(r"^\s*5D\s*$", re.I)
        for tag_name in ["button", "a", "span"]:
            matches = page.locator(tag_name).filter(has_text=pattern)
            for index in range(min(matches.count(), 20)):
                item = matches.nth(index)
                if item.is_visible(timeout=400):
                    item.click(timeout=2500)
                    clicked = True
                    break
            if clicked:
                break
    except Exception:
        clicked = False

    if not clicked:
        # Retain the original program's coordinate fallback.
        page.mouse.click(306, 392)
    page.wait_for_timeout(2500)


def capture_finviz_prices(context: Any, week: str, output_dir: Path, timeout_error: type[Exception]) -> None:
    page = context.new_page()
    try:
        browser_goto(page, FINVIZ_PRICES_1W, timeout_error)
        wait_for_finviz_verification(page)
        scroll_top(page)
        add_time_tag(page, "Finviz closing prices 1W")
        save_viewport(page, output_dir / f"finviz_closing_prices_{week}.png")
    finally:
        page.close()


def capture_finviz_performance(context: Any, week: str, output_dir: Path, timeout_error: type[Exception]) -> None:
    page = context.new_page()
    try:
        browser_goto(page, FINVIZ_PERFORMANCE_1W, timeout_error)
        wait_for_finviz_verification(page)
        located = False
        for text in ["1 Week Performance", "1 WEEK PERFORMANCE"]:
            try:
                page.locator(f"text={text}").first.scroll_into_view_if_needed(timeout=2500)
                page.wait_for_timeout(600)
                page.evaluate("window.scrollBy(0, -140)")
                located = True
                break
            except Exception:
                continue
        if not located:
            scroll_top(page)
        add_time_tag(page, "Finviz futures performance 1W")
        save_viewport(page, output_dir / f"finviz_1W_{week}.png")
    finally:
        page.close()


def capture_yahoo_sectors(context: Any, week: str, output_dir: Path, timeout_error: type[Exception]) -> list[str]:
    errors: list[str] = []
    sector_dir = output_dir / "sectors"
    sector_dir.mkdir(parents=True, exist_ok=True)

    for sector in SECTOR_PAGES:
        page = context.new_page()
        try:
            browser_goto(page, sector.url, timeout_error, wait_ms=7000)
            scroll_top(page)
            click_yahoo_5d(page)
            scroll_top(page)
            add_time_tag(page, f"Yahoo Finance {sector.name} 5D")
            save_viewport(
                page,
                sector_dir / f"yahoo_sectors_5D_{week}_{sector.filename}.png",
            )
        except Exception as exc:
            message = f"{sector.name}: {exc}"
            errors.append(message)
            print(f"[R6] Screenshot failed: {message}", file=sys.stderr)
        finally:
            page.close()
    return errors


def capture_all_screenshots(week: str, output_dir: Path, headless: bool) -> list[str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return [
            "Playwright is not installed. Run: pip install playwright; "
            "then: playwright install chromium. " + str(exc)
        ]

    errors: list[str] = []
    with sync_playwright() as playwright:
        browser: Any | None = None
        if os.name == "nt":
            # A normal Edge process is less likely to be trapped on Finviz's
            # security verification than a Playwright-launched browser. Force
            # visible Edge even if an older launcher passes --headless.
            if headless:
                print("[R6] Ignoring --headless for Finviz so verification is visible.")
            browser, context = connect_to_normal_edge(playwright)
        else:
            profile = project_root() / "app" / "r6_browser_profile"
            profile.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=headless,
                slow_mo=100 if not headless else 0,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                locale="en-US",
                timezone_id="Asia/Singapore",
            )
        try:
            for label, action in [
                (
                    "Finviz closing prices",
                    lambda: capture_finviz_prices(context, week, output_dir, PlaywrightTimeoutError),
                ),
                (
                    "Finviz performance",
                    lambda: capture_finviz_performance(context, week, output_dir, PlaywrightTimeoutError),
                ),
            ]:
                try:
                    action()
                except Exception as exc:
                    errors.append(f"{label}: {exc}")
                    print(f"[R6] Screenshot failed: {label}: {exc}", file=sys.stderr)
                    if "verification did not complete" in str(exc).casefold():
                        errors.append(
                            "Remaining Finviz screenshot skipped because the same "
                            "browser verification is still active."
                        )
                        break
            errors.extend(
                capture_yahoo_sectors(context, week, output_dir, PlaywrightTimeoutError)
            )
        finally:
            if browser is not None:
                browser.close()
            else:
                context.close()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate R6 market CSV and hidden-browser local-page screenshots"
    )
    parser.add_argument(
        "--as-of",
        type=parse_iso_date,
        default=date.today(),
        help="Latest allowed market date (YYYY-MM-DD); default: today",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_evidence_directory(),
        help="Evidence directory; default: repository-root/vWXX/evidence",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional CSV path; default: repository-root/vWXX/evidence/r6_market_actuals_YYYY-WXX.csv",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel downloads; default: 4",
    )
    parser.add_argument(
        "--week",
        help="Optional screenshot label such as 2026-W28; default: latest CSV market week",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the optional --web-screenshots browser headlessly",
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Generate only the CSV and skip all PNG evidence",
    )
    parser.add_argument(
        "--web-screenshots",
        action="store_true",
        help=(
            "Also capture the legacy Finviz/Yahoo webpages. This opens a browser "
            "and may require manual security verification."
        ),
    )
    args = parser.parse_args()

    rows = collect(args.as_of, args.workers)
    week = args.week or dataset_week(rows, args.as_of)
    output = args.output or args.out / f"r6_market_actuals_{week}.csv"
    write_csv(rows, output)

    successful = sum(row["status"] == "ok" for row in rows)
    failed = len(rows) - successful
    print("")
    print(f"[R6] Project root: {project_root()}")
    print(f"[R6] CSV created: {output.resolve()}")
    print(f"[R6] Successful: {successful}/{len(rows)}; Failed: {failed}")

    screenshot_errors: list[str] = []
    if not args.skip_screenshots:
        print("")
        print(f"[R6] Taking hidden-browser screenshots of local evidence pages for {week}...")
        screenshot_errors.extend(generate_local_evidence(rows, week, args.out, output))

    if args.web_screenshots:
        print("")
        print(f"[R6] Capturing optional original Finviz/Yahoo webpages for {week}...")
        screenshot_errors.extend(capture_all_screenshots(week, args.out, args.headless))

    if not args.skip_screenshots or args.web_screenshots:
        if screenshot_errors:
            print(
                f"[R6] Evidence image stage completed with {len(screenshot_errors)} error(s).",
                file=sys.stderr,
            )
            for error in screenshot_errors:
                print(f"[R6] - {error}", file=sys.stderr)
        else:
            print("[R6] All requested evidence images were generated.")

    if successful == 0:
        print("[R6] No market data was downloaded. Check the CSV error column.", file=sys.stderr)
        return 1
    if failed:
        print("[R6] Partial result: check rows whose status is error.", file=sys.stderr)
        return 2
    if screenshot_errors:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
