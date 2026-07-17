# fetch_market_data.py
# R5 Technical Agent - Sprint 6 / W28
# Purpose:
# Fetch market data for SPY, QQQ/NDX, IWM, and all 11 S&P 500 sectors.
# Calculate EMA indicators, generate charts, and create structured CSV/JSON outputs.

import os
import json

import matplotlib
matplotlib.use("Agg")  # Prevents PyCharm/Tkinter chart errors

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt


# R5 Technical Agent W28 assets
# QQQ is used as the ETF proxy for NDX / Nasdaq 100
TICKERS = [
    "SPY",   # S&P 500
    "QQQ",   # Nasdaq 100 proxy
    "IWM",   # Russell 2000

    # 11 S&P 500 sectors
    "XLK",   # Technology
    "XLF",   # Financials
    "XLV",   # Healthcare
    "XLY",   # Consumer Discretionary
    "XLE",   # Energy
    "XLC",   # Communication Services
    "XLI",   # Industrials
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLRE",  # Real Estate
    "XLB"    # Materials
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
    "XLB": "Materials sector"
}


PERIOD = "1y"
INTERVAL = "1d"

TARGET_LAST_TRADING_DATE = "2026-07-17"
DOWNLOAD_START_DATE = "2025-07-17"
DOWNLOAD_END_DATE = "2026-07-18"  # yfinance end date is exclusive

end = "2026-07-18"

DATA_FOLDER = "data"
CHART_FOLDER = "charts"

CSV_OUTPUT = "technical_agent_output_W29.csv"
JSON_OUTPUT = "technical_agent_output_W29.json"


def get_technical_bias(last_close, ema20, ema50):
    """Create a simple technical bias based on EMA position."""

    if last_close > ema20 and ema20 > ema50:
        return "Bullish"
    elif last_close > ema20:
        return "Neutral bullish"
    elif last_close < ema20 and ema20 < ema50:
        return "Bearish"
    else:
        return "Neutral bearish"


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


def clean_downloaded_data(data):

    data.index = pd.to_datetime(data.index)
    target_date = pd.to_datetime(TARGET_LAST_TRADING_DATE)

    # Keep only data up to 2026-07-17
    data = data[data.index <= target_date]
    """
    Clean yfinance data.
    Sometimes yfinance returns multi-index columns.
    This function keeps the code safer.
    """

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data


def fetch_market_data():
    """
    Fetch market data up to the target trading date,
    calculate EMA indicators, save CSV files, create charts,
    and create structured CSV/JSON output.
    """

    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(CHART_FOLDER, exist_ok=True)

    summary_rows = []

    for ticker in TICKERS:
        print(f"Fetching data for {ticker} up to {TARGET_LAST_TRADING_DATE}...")

        data = yf.download(
            ticker,
            start=DOWNLOAD_START_DATE,
            end=DOWNLOAD_END_DATE,
            interval=INTERVAL,
            auto_adjust=True,
            progress=False
        )

        data = clean_downloaded_data(data)

        if data.empty:
            print(f"No data found for {ticker}")
            continue

        data.index = pd.to_datetime(data.index)
        target_date = pd.to_datetime(TARGET_LAST_TRADING_DATE)

        # Keep only data up to the required trading date
        data = data[data.index <= target_date]

        if data.empty:
            print(f"No data available up to {TARGET_LAST_TRADING_DATE} for {ticker}")
            continue

        if "Close" not in data.columns:
            print(f"No Close price column found for {ticker}")
            continue

        # Calculate EMA indicators
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["EMA200"] = data["Close"].ewm(span=200, adjust=False).mean()

        # Save full price data up to target date
        data_file = os.path.join(DATA_FOLDER, f"{ticker}.csv")
        data.to_csv(data_file)
        print(f"Saved data to {data_file}")

        # Create chart using data only up to target date
        chart_path = create_chart(data, ticker)

        # Latest values should now stop at 2026-07-17
        last_row = data.iloc[-1]

        last_trading_date = last_row.name.strftime("%Y-%m-%d")
        last_close = float(last_row["Close"])
        ema20 = float(last_row["EMA20"])
        ema50 = float(last_row["EMA50"])
        ema200 = float(last_row["EMA200"])

        if last_close > ema20:
            ema20_condition = "Above EMA20"
        else:
            ema20_condition = "Below EMA20"

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
            "Chart File": chart_path
        })

    # Save structured CSV output
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(CSV_OUTPUT, index=False)

    # Save structured JSON output
    with open(JSON_OUTPUT, "w", encoding="utf-8") as json_file:
        json.dump(summary_rows, json_file, indent=4)

    print(f"Saved structured CSV output to {CSV_OUTPUT}")
    print(f"Saved structured JSON output to {JSON_OUTPUT}")
    print(f"R5 market data fetch completed using last trading date: {TARGET_LAST_TRADING_DATE}")


if __name__ == "__main__":
    fetch_market_data()
