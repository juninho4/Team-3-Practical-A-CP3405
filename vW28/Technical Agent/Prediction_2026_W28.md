# Prediction_2026_W28

## R5 Technical Agent Summary

For Sprint 6 / W28, my role was **R5 Technical Agent**. My responsibility was to automate technical analysis for the main market indexes and all S&P 500 sectors.

The analysis covers:

* SPY / S&P 500
* QQQ / Nasdaq 100 proxy
* IWM / Russell 2000
* XLK / Technology
* XLF / Financials
* XLV / Healthcare
* XLY / Consumer Discretionary
* XLE / Energy
* XLC / Communication Services
* XLI / Industrials
* XLP / Consumer Staples
* XLU / Utilities
* XLRE / Real Estate
* XLB / Materials

---

## What I Did This Week

This week, I upgraded the R5 Technical Agent from a manual/semi-automated workflow into a more automated pipeline.

I updated the Python script `fetch_market_data.py` to:

* fetch market data automatically using `yfinance`
* cover SPY, QQQ, IWM, and all 11 S&P 500 sector ETFs
* calculate EMA20, EMA50, and EMA200
* generate one CSV file for each ticker
* generate EMA20 chart images
* create structured output files in CSV and JSON format
* run through GitHub Actions automatically after a push

The main output files are:

| Output                            | Purpose                                |
| --------------------------------- | -------------------------------------- |
| `technical_agent_output_W28.csv`  | Structured technical summary           |
| `technical_agent_output_W28.json` | Structured output for pipeline use     |
| `data/*.csv`                      | Raw market data with EMA indicators    |
| `charts/*.png`                    | EMA20 chart evidence                   |
| `fetch_market_data.py`            | R5 automation script                   |
| `requirements.txt`                | Python package list for GitHub Actions |

---

## What I Found

The technical agent checks whether each ticker is trading above or below EMA20 and compares EMA20 with EMA50 to create a simple technical bias.

The main finding is that the R5 workflow can now produce technical evidence automatically instead of relying only on manual screenshots. This makes the analysis more consistent because every ticker is processed using the same method.

The structured output helps the team quickly compare:

* current price
* EMA20
* EMA50
* EMA200
* EMA20 condition
* technical bias
* chart evidence

This is useful because Sprint 6 requires the pipeline to run without manual work.

---

## GitHub Actions Evidence

I also created a GitHub Actions workflow for the R5 Technical Agent.

The workflow ran successfully after I pushed changes to GitHub. It installed the required Python packages, ran the R5 Python script, and produced an artifact containing the generated outputs.

This shows that the R5 Technical Agent pipeline can run automatically without me manually running the script on my own computer.

Evidence:

* Workflow name: `R5 Technical Agent Pipeline`
* Status: `Success`
* Trigger: `push`
* Artifact produced: `1`

---

## Final Result

The R5 Technical Agent is now automated for Sprint 6. It can fetch market data, calculate EMA indicators, generate chart evidence, and produce structured CSV/JSON outputs for SPY, QQQ, IWM, and all 11 S&P 500 sectors.

Overall, my Sprint 6 result is that the R5 work is no longer only a manual technical analysis task. It is now a repeatable automated pipeline that supports the team’s market prediction process.

