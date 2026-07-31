# fetch_market_data.py
# R5 Technical Agent - Sprint 9 / W31
# Automatically uses the latest completed US market session.

import json
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


# QQQ is used as the ETF proxy for NDX / Nasdaq 100.
TICKERS = [
    "SPY", "QQQ", "IWM",
    "XLK", "XLF", "XLV", "XLY", "XLE", "XLC",
    "XLI", "XLP", "XLU", "XLRE", "XLB"
]

MARKET_NAMES = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100 proxy",
    "IWM": "Russell 2000",
    "XLK": "Technology sector",
    "XLF": "Financial sector",
    "XLV": "Healthcare sector",
    "XLY": "Consumer Discretionary sector",
    "XLE": "Energy sector",
    "XLC": "Communication Services sector",
    "XLI": "Industrials sector",
    "XLP": "Consumer Staples sector",
    "XLU": "Utilities sector",
    "XLRE": "Real Estate sector",
    "XLB": "Materials sector",
}

INTERVAL = "1d"

# Keep the historical start date fixed, as requested.
DOWNLOAD_START_DATE = "2025-07-17"

# W31 is the default. GitHub Actions can override this with:
# SPRINT_WEEK: W31
SPRINT_WEEK = os.getenv("SPRINT_WEEK", "W31")

DATA_FOLDER = "data"
CHART_FOLDER = "charts"

CSV_OUTPUT = f"technical_agent_output_{SPRINT_WEEK}.csv"
JSON_OUTPUT = f"technical_agent_output_{SPRINT_WEEK}.json"

NEW_YORK_TIMEZONE = ZoneInfo("America/New_York")

# Wait until 30 minutes after the regular 4:00 PM New York close.
# This avoids selecting the current day when the market is still open.
SAFE_MARKET_CLOSE_TIME = time(16, 30)


def get_automatic_download_window():
    """
    Return an automatic cutoff date and yfinance end date.

    yfinance treats `end` as exclusive. Therefore, the end date must be
    one calendar day after the latest completed market date.

    Holidays do not need to be manually listed. If the requested cutoff is
    a market holiday, yfinance simply returns the previous available session.
    """
    now_new_york = datetime.now(NEW_YORK_TIMEZONE)
    cutoff_date = now_new_york.date()

    # Before 4:30 PM New York time, today's daily candle is not considered final.
    if now_new_york.time() < SAFE_MARKET_CLOSE_TIME:
        cutoff_date -= timedelta(days=1)

    # Move Saturday/Sunday back to Friday.
    while cutoff_date.weekday() >= 5:
        cutoff_date -= timedelta(days=1)

    exclusive_end_date = cutoff_date + timedelta(days=1)

    return cutoff_date.isoformat(), exclusive_end_date.isoformat()


def get_technical_bias(last_close, ema20, ema50):
    """Create a simple technical bias based on EMA position."""
    if last_close > ema20 and ema20 > ema50:
        return "Bullish"
    if last_close > ema20:
        return "Neutral bullish"
    if last_close < ema20 and ema20 < ema50:
        return "Bearish"
    return "Neutral bearish"


def clean_downloaded_data(data):
    """Flatten yfinance multi-index columns when necessary."""
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.index = pd.to_datetime(data.index)
    return data.sort_index()


def create_chart(data, ticker):
    """Create and save a price chart with EMA20."""
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(data.index, data["Close"], label="Close Price")
    ax.plot(data.index, data["EMA20"], label="EMA20")

    ax.set_title(f"{ticker} - Price with EMA20")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend()
    ax.grid(True)

    chart_path = os.path.join(CHART_FOLDER, f"{ticker}_EMA20_chart.png")
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved chart to {chart_path}")
    return chart_path


def fetch_market_data():
    """
    Fetch data through the latest completed US market session, calculate
    EMA indicators, save per-ticker CSVs and charts, and create summary
    CSV/JSON files.
    """
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(CHART_FOLDER, exist_ok=True)

    requested_cutoff_date, download_end_date = get_automatic_download_window()

    print(f"New York market cutoff: {requested_cutoff_date}")
    print(f"yfinance exclusive end date: {download_end_date}")

    summary_rows = []

    for ticker in TICKERS:
        print(f"\nFetching data for {ticker}...")

        try:
            data = yf.download(
                ticker,
                start=DOWNLOAD_START_DATE,
                end=download_end_date,
                interval=INTERVAL,
                auto_adjust=True,
                progress=False,
            )
        except Exception as error:
            print(f"Error fetching {ticker}: {error}")
            continue

        data = clean_downloaded_data(data)

        if data.empty:
            print(f"No data found for {ticker}")
            continue

        if "Close" not in data.columns:
            print(f"No Close price column found for {ticker}")
            continue

        # yfinance returns only available sessions before the exclusive end date.
        # The final row is therefore the latest available completed trading day.
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["EMA200"] = data["Close"].ewm(span=200, adjust=False).mean()

        data_file = os.path.join(DATA_FOLDER, f"{ticker}.csv")
        data.to_csv(data_file)
        print(f"Saved data to {data_file}")

        chart_path = create_chart(data, ticker)

        last_row = data.iloc[-1]
        last_trading_date = data.index[-1].strftime("%Y-%m-%d")
        last_close = float(last_row["Close"])
        ema20 = float(last_row["EMA20"])
        ema50 = float(last_row["EMA50"])
        ema200 = float(last_row["EMA200"])

        ema20_condition = (
            "Above EMA20" if last_close > ema20 else "Below EMA20"
        )
        technical_bias = get_technical_bias(last_close, ema20, ema50)

        summary_rows.append({
            "Ticker": ticker,
            "Market": MARKET_NAMES[ticker],
            "Last Trading Date": last_trading_date,
            "Last Close": round(last_close, 2),
            "EMA20": round(ema20, 2),
            "EMA50": round(ema50, 2),
            "EMA200": round(ema200, 2),
            "EMA20 Condition": ema20_condition,
            "Technical Bias": technical_bias,
            "Data File": data_file,
            "Chart File": chart_path,
            "Sprint Week": f"v{SPRINT_WEEK}",
        })

    if not summary_rows:
        raise RuntimeError("No market data was generated for any ticker.")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(CSV_OUTPUT, index=False)

    with open(JSON_OUTPUT, "w", encoding="utf-8") as json_file:
        json.dump(summary_rows, json_file, indent=4)

    actual_dates = sorted(summary["Last Trading Date"].unique().tolist())

    print(f"\nSaved structured CSV output to {CSV_OUTPUT}")
    print(f"Saved structured JSON output to {JSON_OUTPUT}")
    print(f"Actual trading date(s) returned: {', '.join(actual_dates)}")
    print("R5 automatic market data fetch completed.")


if __name__ == "__main__":
    fetch_market_data()
