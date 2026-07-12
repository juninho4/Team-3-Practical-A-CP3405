import os
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# R5 Technical Agent W25 assets
# QQQ is used as the ETF proxy for NDX / Nasdaq 100
TICKERS = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLV", "XLY", "XLE"]

MARKET_NAMES = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100 proxy",
    "IWM": "Russell 2000",
    "XLK": "Technology sector",
    "XLF": "Financial sector",
    "XLV": "Healthcare sector",
    "XLY": "Consumer Discretionary sector",
    "XLE": "Energy sector"
}

PERIOD = "1y"
INTERVAL = "1d"

DATA_FOLDER = "data"
CHART_FOLDER = "charts"


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

    plt.figure(figsize=(10, 5))

    plt.plot(data.index, data["Close"], label="Close Price")
    plt.plot(data.index, data["EMA20"], label="EMA20")

    plt.title(f"{ticker} - Price with EMA20")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)

    chart_path = os.path.join(CHART_FOLDER, f"{ticker}_EMA20_chart.png")
    plt.savefig(chart_path, bbox_inches="tight")
    plt.close()

    print(f"Saved chart to {chart_path}")


def fetch_market_data():
    """
    Fetch market data, calculate EMA indicators,
    save CSV files, create charts, and create a structured output file.
    """

    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(CHART_FOLDER, exist_ok=True)

    summary_rows = []

    for ticker in TICKERS:
        print(f"Fetching data for {ticker}...")

        data = yf.download(
            ticker,
            period=PERIOD,
            interval=INTERVAL,
            auto_adjust=True,
            progress=False
        )

        if data.empty:
            print(f"No data found for {ticker}")
            continue

        # Calculate EMA indicators
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["EMA200"] = data["Close"].ewm(span=200, adjust=False).mean()

        # Save full price data
        data_file = os.path.join(DATA_FOLDER, f"{ticker}.csv")
        data.to_csv(data_file)
        print(f"Saved data to {data_file}")

        # Create chart
        create_chart(data, ticker)

        # Latest values
        last_row = data.iloc[-1]
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
            "Last Close": round(last_close, 2),
            "EMA20": round(ema20, 2),
            "EMA50": round(ema50, 2),
            "EMA200": round(ema200, 2),
            "EMA20 Condition": ema20_condition,
            "Technical Bias": technical_bias
        })

    # Save structured output file
    summary = pd.DataFrame(summary_rows)
    summary_file = "technical_agent_output_W25.csv"
    summary.to_csv(summary_file, index=False)

    print(f"Saved structured output to {summary_file}")
    print("Market data fetch and chart generation completed.")


if __name__ == "__main__":
    fetch_market_data()
