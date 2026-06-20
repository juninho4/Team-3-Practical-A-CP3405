import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf


SYMBOLS = {
    "SPX": "^GSPC",
    "NDX": "^NDX",
    "IWM": "IWM"
}

sgt_now = datetime.now(ZoneInfo("Asia/Singapore"))
timestamp = sgt_now.strftime("%Y-%m-%d_%H-%M-%S_SGT")

output_dir = "data/market_closes"
os.makedirs(output_dir, exist_ok=True)

results = {
    "fetch_time_sgt": sgt_now.isoformat(),
    "note": "Automated GitHub Actions fetch for Friday market closes.",
    "symbols": {}
}

for name, ticker in SYMBOLS.items():
    data = yf.Ticker(ticker).history(period="5d")

    if data.empty:
        results["symbols"][name] = {
            "ticker": ticker,
            "error": "No data returned"
        }
        continue

    last_row = data.tail(1).iloc[0]
    last_date = str(data.tail(1).index[0].date())

    results["symbols"][name] = {
        "ticker": ticker,
        "last_trading_date": last_date,
        "close": round(float(last_row["Close"]), 2)
    }

output_file = f"{output_dir}/friday_closes_{timestamp}.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Saved market close data to {output_file}")
print(json.dumps(results, indent=2))
