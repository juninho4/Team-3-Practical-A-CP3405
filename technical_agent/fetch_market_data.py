# fetch_market_data.py

import os
import yfinance as yf

# R5 Technical Agent assets
TICKERS = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLV"]

# Download period
PERIOD = "1y"
INTERVAL = "1d"

# Output folder
OUTPUT_FOLDER = "data"


def fetch_market_data():
    """
    Fetch market data and calculate EMA indicators for R5 Technical Agent.
    The script saves one CSV file for each ETF.
    """

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for ticker in TICKERS:
        print(f"Fetching data for {ticker}...")

        data = yf.download(
            ticker,
            period=PERIOD,
            interval=INTERVAL,
            auto_adjust=True
        )

        if data.empty:
            print(f"No data found for {ticker}")
            continue

        # Calculate EMA indicators
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["EMA200"] = data["Close"].ewm(span=200, adjust=False).mean()

        # Save to CSV
        file_path = os.path.join(OUTPUT_FOLDER, f"{ticker}.csv")
        data.to_csv(file_path)

        print(f"Saved {ticker} data to {file_path}")

    print("Market data fetch completed.")


if __name__ == "__main__":
    fetch_market_data()
