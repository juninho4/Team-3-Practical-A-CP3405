#!/usr/bin/env python3
"""R4 Macro Agent.

Creates an independent, source-linked macro analysis for the selected ISO week.
The script uses public market data and official US government sources; no API
key is required.

Install dependencies:
    pip install yfinance pandas matplotlib

Examples:
    python r4_macro_agent.py
    python r4_macro_agent.py --week-start 2026-07-06
    python r4_macro_agent.py --week-start 2026-07-06 --output-dir C:/my_project/output/agents
"""

from __future__ import annotations

import argparse
import email.utils
import json
import math
import os
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "r4-matplotlib"))

try:
    import matplotlib.pyplot as plt
    import pandas as pd
    import yfinance as yf
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Run: pip install yfinance pandas matplotlib"
    ) from exc


USER_AGENT = "CP3405-R4-Macro-Agent/1.0"

MACRO_TICKERS = {
    "^TNX": "US 10Y Treasury yield",
    "DX-Y.NYB": "US Dollar Index",
    "^VIX": "VIX volatility index",
    "CL=F": "WTI crude oil",
    "GC=F": "Gold",
    "HYG": "High-yield corporate bonds",
    "SPY": "S&P 500 proxy",
    "QQQ": "Nasdaq 100 proxy",
    "IWM": "Russell 2000 proxy",
}

SECTOR_TICKERS = {
    "XLK": "Technology",
    "XLV": "Health Care",
    "XLF": "Financials",
    "XLY": "Consumer Discretionary",
    "XLC": "Communication Services",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
}

CYCLICAL_SECTORS = ["XLK", "XLF", "XLY", "XLC", "XLI", "XLE", "XLB"]
DEFENSIVE_SECTORS = ["XLV", "XLP", "XLRE", "XLU"]

SOURCES = {
    "yahoo": "https://finance.yahoo.com/",
    "finviz": "https://finviz.com/map.ashx?t=sec",
    "bls_api": "https://www.bls.gov/developers/",
    "bls_calendar": "https://www.bls.gov/schedule/news_release/",
    "fed_press": "https://www.federalreserve.gov/newsevents/pressreleases.htm",
    "fed_calendar": "https://www.federalreserve.gov/newsevents/calendar.htm",
}


@dataclass
class Signal:
    name: str
    value: str
    change: str
    interpretation: str
    score: int


def current_monday(today: date | None = None) -> date:
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def project_root() -> Path:
    """Return project when this script is stored in project/py/."""
    script_directory = Path(__file__).resolve().parent

    # Final integrated layout: project/py/r4_macro_agent.py
    if script_directory.name.casefold() == "py":
        return script_directory.parent

    # Development fallback when the complete folder structure already exists.
    for parent in [script_directory, *script_directory.parents]:
        if (parent / "app").is_dir() and (parent / "output").is_dir():
            return parent

    return script_directory.parent


def default_agents_directory() -> Path:
    return project_root() / "output" / "agents"


def parse_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD, for example 2026-07-06") from exc
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("--week-start must be a Monday")
    return parsed


def request_bytes(url: str, *, data: bytes | None = None, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json,text/calendar,application/rss+xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_close_prices(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    """Download adjusted close prices and normalize yfinance column formats."""
    raw = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
        timeout=20,
    )
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no market data")

    if isinstance(raw.columns, pd.MultiIndex):
        level_zero = set(raw.columns.get_level_values(0))
        if "Close" in level_zero:
            close = raw["Close"].copy()
        else:
            close = raw.xs("Close", axis=1, level=1).copy()
    else:
        if "Close" not in raw.columns:
            raise RuntimeError("Close price column was not returned")
        close = raw[["Close"]].copy()
        close.columns = [tickers[0]]

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    close = close.apply(pd.to_numeric, errors="coerce").sort_index()
    return close.dropna(how="all")


def last_valid_series(frame: pd.DataFrame, ticker: str, end: date) -> pd.Series:
    if ticker not in frame.columns:
        return pd.Series(dtype="float64")
    series = frame[ticker].dropna()
    if series.empty:
        return series
    end_timestamp = pd.Timestamp(end)
    if series.index.tz is not None:
        end_timestamp = end_timestamp.tz_localize(series.index.tz)
    return series.loc[series.index <= end_timestamp]


def five_session_change(series: pd.Series) -> float:
    if len(series) < 2:
        return math.nan
    previous_position = max(0, len(series) - 6)
    previous = float(series.iloc[previous_position])
    latest = float(series.iloc[-1])
    return ((latest / previous) - 1.0) * 100.0


def level_change(series: pd.Series) -> float:
    if len(series) < 2:
        return math.nan
    previous_position = max(0, len(series) - 6)
    return float(series.iloc[-1]) - float(series.iloc[previous_position])


def threshold_score(value: float, positive_below: float, negative_above: float) -> int:
    if math.isnan(value):
        return 0
    if value <= positive_below:
        return 1
    if value >= negative_above:
        return -1
    return 0


def build_market_signals(close: pd.DataFrame, week_end: date) -> tuple[list[Signal], dict[str, Any]]:
    values: dict[str, Any] = {}
    for ticker in MACRO_TICKERS:
        series = last_valid_series(close, ticker, week_end)
        if series.empty:
            values[ticker] = {"last": math.nan, "pct5": math.nan, "level5": math.nan}
            continue
        values[ticker] = {
            "last": float(series.iloc[-1]),
            "pct5": five_session_change(series),
            "level5": level_change(series),
            "date": series.index[-1].date().isoformat(),
        }

    tnx = values["^TNX"]
    dxy = values["DX-Y.NYB"]
    vix = values["^VIX"]
    hyg = values["HYG"]
    oil = values["CL=F"]

    signals = [
        Signal(
            "US 10Y yield",
            format_number(tnx["last"], "%"),
            format_signed(tnx["level5"], " pts"),
            "Lower yields support rate-sensitive assets" if tnx["level5"] < -0.05
            else "Higher yields pressure rate-sensitive assets" if tnx["level5"] > 0.05
            else "Yield pressure is broadly neutral",
            threshold_score(tnx["level5"], -0.05, 0.05),
        ),
        Signal(
            "US Dollar Index",
            format_number(dxy["last"]),
            format_signed(dxy["pct5"], "%"),
            "A weaker dollar is a macro tailwind" if dxy["pct5"] < -0.3
            else "A stronger dollar is a macro headwind" if dxy["pct5"] > 0.3
            else "Dollar movement is neutral",
            threshold_score(dxy["pct5"], -0.3, 0.3),
        ),
        Signal(
            "VIX",
            format_number(vix["last"]),
            format_signed(vix["pct5"], "%"),
            "Falling volatility supports risk appetite" if vix["pct5"] < -5
            else "Rising volatility signals risk aversion" if vix["pct5"] > 5
            else "Volatility signal is neutral",
            threshold_score(vix["pct5"], -5, 5),
        ),
        Signal(
            "High-yield bonds (HYG)",
            format_number(hyg["last"]),
            format_signed(hyg["pct5"], "%"),
            "Credit conditions support risk assets" if hyg["pct5"] > 0.2
            else "Credit weakness is a risk signal" if hyg["pct5"] < -0.2
            else "Credit conditions are neutral",
            1 if hyg["pct5"] > 0.2 else -1 if hyg["pct5"] < -0.2 else 0,
        ),
        Signal(
            "WTI crude oil",
            format_number(oil["last"], "$"),
            format_signed(oil["pct5"], "%"),
            "Oil strength may increase inflation pressure" if oil["pct5"] > 3
            else "Oil weakness reduces near-term inflation pressure" if oil["pct5"] < -3
            else "Oil signal is neutral",
            -1 if oil["pct5"] > 3 else 1 if oil["pct5"] < -3 else 0,
        ),
    ]
    return signals, values


def get_bls_cpi() -> dict[str, Any]:
    """Get headline CPI from the official BLS public API."""
    this_year = date.today().year
    payload = json.dumps(
        {
            "seriesid": ["CUUR0000SA0"],
            "startyear": str(this_year - 2),
            "endyear": str(this_year),
        }
    ).encode("utf-8")
    raw = json.loads(
        request_bytes("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=payload)
    )
    series = raw["Results"]["series"][0]["data"]
    observations: dict[tuple[int, int], float] = {}
    for row in series:
        period = row.get("period", "")
        if re.fullmatch(r"M(0[1-9]|1[0-2])", period):
            observations[(int(row["year"]), int(period[1:]))] = float(row["value"])

    months = sorted(observations)
    yoy_values: list[tuple[tuple[int, int], float]] = []
    for year, month in months:
        current = observations[(year, month)]
        previous = observations.get((year - 1, month))
        if previous:
            yoy_values.append(((year, month), ((current / previous) - 1) * 100))

    if not yoy_values:
        raise RuntimeError("BLS CPI response did not contain enough observations")

    latest_month, latest_yoy = yoy_values[-1]
    previous_yoy = yoy_values[-2][1] if len(yoy_values) > 1 else latest_yoy
    return {
        "period": f"{latest_month[0]}-{latest_month[1]:02d}",
        "yoy": latest_yoy,
        "previous_yoy": previous_yoy,
        "change": latest_yoy - previous_yoy,
        "score": 1 if latest_yoy < previous_yoy - 0.05 else -1 if latest_yoy > previous_yoy + 0.05 else 0,
    }


def unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def parse_ics_date(value: str) -> date | None:
    digits = re.search(r"(\d{8})", value)
    if not digits:
        return None
    try:
        return datetime.strptime(digits.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def get_bls_events(week_start: date, week_end: date) -> list[dict[str, str]]:
    """Read scheduled BLS releases from the official public ICS calendar."""
    text = request_bytes("https://www.bls.gov/schedule/news_release/bls.ics").decode(
        "utf-8", errors="replace"
    )
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfold_ics(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            event_date = parse_ics_date(current.get("DTSTART", ""))
            if event_date and week_start <= event_date <= week_end:
                events.append(
                    {
                        "date": event_date.isoformat(),
                        "event": current.get("SUMMARY", "BLS release").replace("\\,", ","),
                        "source": current.get("URL", SOURCES["bls_calendar"]),
                    }
                )
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.split(";", 1)[0]] = value
    return sorted(events, key=lambda event: (event["date"], event["event"]))


def get_fed_items(week_start: date, week_end: date) -> list[dict[str, str]]:
    """Get Federal Reserve releases published during the selected week."""
    xml_data = request_bytes("https://www.federalreserve.gov/feeds/press_all.xml")
    root = ET.fromstring(xml_data)
    events: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "Federal Reserve release").strip()
        link = (item.findtext("link") or SOURCES["fed_press"]).strip()
        published = item.findtext("pubDate") or ""
        try:
            event_date = email.utils.parsedate_to_datetime(published).date()
        except (TypeError, ValueError):
            continue
        if week_start <= event_date <= week_end:
            events.append(
                {"date": event_date.isoformat(), "event": title, "source": link}
            )
    return sorted(events, key=lambda event: (event["date"], event["event"]))


def sector_table(close: pd.DataFrame, week_end: date) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker, sector in SECTOR_TICKERS.items():
        series = last_valid_series(close, ticker, week_end)
        if series.empty:
            continue
        latest = float(series.iloc[-1])
        ema20 = float(series.ewm(span=20, adjust=False).mean().iloc[-1])
        rows.append(
            {
                "Ticker": ticker,
                "Sector": sector,
                "Last Close": round(latest, 2),
                "5D Return (%)": round(five_session_change(series), 2),
                "EMA20 Condition": "Above EMA20" if latest > ema20 else "Below EMA20",
            }
        )
    return pd.DataFrame(rows).sort_values("5D Return (%)", ascending=False, ignore_index=True)


def mean_sector_return(sectors: pd.DataFrame, tickers: list[str]) -> float:
    selected = sectors.loc[sectors["Ticker"].isin(tickers), "5D Return (%)"]
    return float(selected.mean()) if not selected.empty else math.nan


def sector_rotation_signal(sectors: pd.DataFrame) -> Signal:
    cyclical = mean_sector_return(sectors, CYCLICAL_SECTORS)
    defensive = mean_sector_return(sectors, DEFENSIVE_SECTORS)
    spread = cyclical - defensive
    if spread > 0.5:
        text, score = "Cyclical leadership indicates risk-on rotation", 1
    elif spread < -0.5:
        text, score = "Defensive leadership indicates risk-off rotation", -1
    else:
        text, score = "Sector rotation is mixed", 0
    return Signal(
        "Sector rotation",
        f"Cyclical {cyclical:+.2f}% / Defensive {defensive:+.2f}%",
        f"Spread {spread:+.2f} pts",
        text,
        score,
    )


def format_number(value: float, suffix: str = "") -> str:
    return "N/A" if math.isnan(value) else f"{value:.2f}{suffix}"


def format_signed(value: float, suffix: str = "") -> str:
    return "N/A" if math.isnan(value) else f"{value:+.2f}{suffix}"


def score_label(score: int) -> tuple[str, str]:
    if score >= 4:
        return "Bullish", "High"
    if score >= 2:
        return "Slightly Bullish", "Medium"
    if score <= -4:
        return "Bearish", "High"
    if score <= -2:
        return "Slightly Bearish", "Medium"
    return "Neutral / Mixed", "Low"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |" for row in rows]
    return "\n".join([head, divider, *body])


def create_chart(
    close: pd.DataFrame,
    sectors: pd.DataFrame,
    week_end: date,
    path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ticker, label in [("^TNX", "10Y yield"), ("DX-Y.NYB", "US dollar"), ("^VIX", "VIX")]:
        series = last_valid_series(close, ticker, week_end).tail(30)
        if len(series) > 1:
            normalized = series / float(series.iloc[0]) * 100
            axes[0].plot(series.index, normalized, label=label)
    axes[0].set_title("Macro indicators (30-session normalized)")
    axes[0].set_ylabel("Start = 100")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    plot_sectors = sectors.sort_values("5D Return (%)", ascending=True)
    colors = ["#b91c1c" if value < 0 else "#15803d" for value in plot_sectors["5D Return (%)"]]
    axes[1].barh(plot_sectors["Ticker"], plot_sectors["5D Return (%)"], color=colors)
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].set_title("S&P 500 sector rotation (5 sessions)")
    axes[1].set_xlabel("Return (%)")
    axes[1].grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def safe_call(function: Any, default: Any, warnings: list[str], label: str) -> Any:
    try:
        return function()
    except Exception as exc:  # Continue with the remaining independent evidence sources.
        warnings.append(f"{label} unavailable: {exc}")
        return default


def build_report(
    week_start: date,
    week_end: date,
    market_signals: list[Signal],
    rotation: Signal,
    cpi: dict[str, Any] | None,
    sectors: pd.DataFrame,
    events: list[dict[str, str]],
    chart_name: str,
    warnings: list[str],
) -> str:
    signals = [*market_signals, rotation]
    total_score = sum(signal.score for signal in signals) + (cpi["score"] if cpi else 0)
    verdict, confidence = score_label(total_score)
    positive = [signal.interpretation for signal in signals if signal.score > 0]
    negative = [signal.interpretation for signal in signals if signal.score < 0]

    if cpi:
        cpi_direction = (
            "cooling" if cpi["change"] < -0.05 else "accelerating" if cpi["change"] > 0.05 else "stable"
        )
        cpi_text = (
            f"Latest headline CPI ({cpi['period']}) was {cpi['yoy']:.2f}% year-on-year, "
            f"versus {cpi['previous_yoy']:.2f}% in the prior month. Inflation is {cpi_direction}."
        )
    else:
        cpi_text = "Official CPI data could not be retrieved during this run."

    leaders = ", ".join(
        f"{row['Ticker']} ({row['5D Return (%)']:+.2f}%)" for _, row in sectors.head(3).iterrows()
    )
    laggards = ", ".join(
        f"{row['Ticker']} ({row['5D Return (%)']:+.2f}%)" for _, row in sectors.tail(3).iterrows()
    )

    signal_rows = [
        [signal.name, signal.value, signal.change, signal.interpretation, f"{signal.score:+d}"]
        for signal in signals
    ]
    sector_rows = [
        [
            str(row["Ticker"]),
            str(row["Sector"]),
            f"{row['5D Return (%)']:+.2f}%",
            str(row["EMA20 Condition"]),
        ]
        for _, row in sectors.iterrows()
    ]
    event_rows = [
        [event["date"], event["event"], f"[Official source]({event['source']})"] for event in events
    ]
    if not event_rows:
        event_rows = [["No BLS release found", "Check the Fed calendar manually for speeches and meetings", f"[Fed calendar]({SOURCES['fed_calendar']})"]]

    positive_lines = "\n".join(f"- {item}" for item in positive) or "- No strong bullish macro signal."
    negative_lines = "\n".join(f"- {item}" for item in negative) or "- No strong bearish macro signal."
    warning_text = "\n".join(f"- {warning}" for warning in warnings) or "- All automated sources returned data."

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    week_number = week_start.isocalendar().week
    return f"""# R4 Macro Agent Output — W{week_number:02d}

## Analysis Period

- Week: {week_start.isoformat()} to {week_end.isoformat()}
- Generated: {generated}
- Method: Independent rule-based macro analysis completed before LLM synthesis

## Final Macro Thesis

- **Verdict:** {verdict}
- **Confidence:** {confidence}
- **Macro score:** {total_score:+d}

The macro environment is assessed as **{verdict.lower()}**. The strongest positive evidence is {positive[0].lower() if positive else 'limited'}, while the main headwind is {negative[0].lower() if negative else 'limited'}. This verdict should support or challenge the team prediction, but it should not replace R3 historical evidence or R5 technical analysis.

## Macro Dashboard

{markdown_table(['Signal', 'Latest', '5-session change', 'Interpretation', 'Score'], signal_rows)}

## Inflation Signal

{cpi_text}

Source: [US Bureau of Labor Statistics API]({SOURCES['bls_api']})

## Sector Rotation

- Leaders: {leaders}
- Laggards: {laggards}
- Rotation conclusion: {rotation.interpretation}

{markdown_table(['Ticker', 'Sector', '5D return', 'Trend'], sector_rows)}

Evidence chart: [{chart_name}]({chart_name})

## Key Macro Events

{markdown_table(['Date', 'Event', 'Source'], event_rows)}

## Evidence Supporting the Team Prediction

{positive_lines}

## Evidence Undermining the Team Prediction

{negative_lines}

## Risks and Invalidation

- A sharp reversal in the 10-year yield or US dollar would invalidate the current rate/liquidity interpretation.
- A VIX increase above the current weekly trend would weaken any risk-on conclusion.
- New CPI, labour-market, or Federal Reserve information released after this report must be reviewed manually.
- Sector leadership concentrated in only one sector should not be treated as broad market strength.

## Sources

- [Yahoo Finance market data]({SOURCES['yahoo']})
- [Finviz sector map]({SOURCES['finviz']})
- [BLS public data API]({SOURCES['bls_api']})
- [BLS release calendar]({SOURCES['bls_calendar']})
- [Federal Reserve press releases]({SOURCES['fed_press']})
- [Federal Reserve calendar]({SOURCES['fed_calendar']})

## Data Collection Notes

{warning_text}
"""


def run(week_start: date, output_dir: Path) -> Path:
    week_end = week_start + timedelta(days=6)
    download_end = min(week_end, date.today())
    download_start = download_end - timedelta(days=150)
    week_number = week_start.isocalendar().week
    output_dir.mkdir(parents=True, exist_ok=True)

    tickers = list(dict.fromkeys([*MACRO_TICKERS, *SECTOR_TICKERS]))
    close = download_close_prices(tickers, download_start, download_end)
    market_signals, _ = build_market_signals(close, download_end)
    sectors = sector_table(close, download_end)
    if sectors.empty:
        raise RuntimeError("No sector data was available")

    warnings: list[str] = []
    cpi = safe_call(get_bls_cpi, None, warnings, "BLS CPI")
    bls_events = safe_call(
        lambda: get_bls_events(week_start, week_end), [], warnings, "BLS release calendar"
    )
    fed_items = safe_call(
        lambda: get_fed_items(week_start, week_end), [], warnings, "Federal Reserve feed"
    )
    events = sorted([*bls_events, *fed_items], key=lambda event: (event["date"], event["event"]))
    rotation = sector_rotation_signal(sectors)

    macro_csv = output_dir / f"r4_macro_market_data_W{week_number:02d}.csv"
    sector_csv = output_dir / f"r4_sector_rotation_W{week_number:02d}.csv"
    chart_path = output_dir / f"r4_macro_evidence_W{week_number:02d}.png"
    report_path = output_dir / f"macro_agent_output_W{week_number:02d}.md"

    pd.DataFrame(
        [
            {
                "Signal": signal.name,
                "Latest": signal.value,
                "5-session change": signal.change,
                "Interpretation": signal.interpretation,
                "Score": signal.score,
            }
            for signal in market_signals
        ]
    ).to_csv(macro_csv, index=False)
    sectors.to_csv(sector_csv, index=False)
    create_chart(close, sectors, download_end, chart_path)

    report = build_report(
        week_start,
        week_end,
        market_signals,
        rotation,
        cpi,
        sectors,
        events,
        chart_path.name,
        warnings,
    )
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the weekly R4 macro analysis")
    parser.add_argument(
        "--week-start",
        type=parse_date,
        default=current_monday(),
        help="Monday of the analysis week in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_agents_directory(),
        help="Output directory; default: project/output/agents",
    )
    args = parser.parse_args()

    try:
        report_path = run(args.week_start, args.output_dir)
    except Exception as exc:
        print(f"R4 Macro Agent failed: {exc}", file=sys.stderr)
        return 1

    print(f"Project root: {project_root()}")
    print(f"Created {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
