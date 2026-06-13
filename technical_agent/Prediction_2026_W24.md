# W24 R5 Technical Agent Report

## Purpose

This file records the R5 technical analysis for Week 24.

My role is **R5 Technical Agent**, so my responsibility is to analyse:

- SPX / S&P 500
- NDX / Nasdaq 100
- IWM / Russell 2000
- Minimum 3 S&P 500 sectors

The analysis focuses on chart trend, EMA20 condition, support, resistance, and technical bias.

---

## Assets Covered

| Market / Sector | Ticker Used | Full Name |
|---|---|---|
| SPX / S&P 500 | SPY | SPDR S&P 500 ETF Trust |
| NDX / Nasdaq 100 | NDX | Nasdaq 100 Index |
| IWM / Russell 2000 | IWM | iShares Russell 2000 ETF |
| Technology Sector | XLK | Technology Select Sector SPDR Fund |
| Financial Sector | XLF | Financial Select Sector SPDR Fund |
| Healthcare Sector | XLV | Health Care Select Sector SPDR Fund |

---

# W24 Technical Analysis

## 1. SPY / S&P 500

| Item | Analysis |
|---|---|
| Current Chart Condition | Price is near the recent high and moving sideways after an uptrend. |
| EMA20 Condition | Price is slightly above EMA20. |
| Support | Around 10.20 to 10.30. |
| Resistance | Around 10.50 to 10.60. |
| Technical Bias | Slightly bullish / neutral bullish. |

### Comment

SPY is still in a short-term upward structure because the price remains above EMA20. However, the recent candles show consolidation near resistance, so the market may need a breakout before stronger bullish momentum continues.

---

## 2. NDX / Nasdaq 100

| Item | Analysis |
|---|---|
| Current Chart Condition | Strong uptrend from April to June, with a recent pullback and recovery. |
| EMA20 Condition | Price is slightly above EMA20. |
| Support | Around 28,500 to 29,000. |
| Resistance | Around 30,000 to 30,500. |
| Technical Bias | Bullish, but volatile. |

### Comment

NDX shows one of the strongest technical setups. The price is still near the upper area of the chart and remains close to EMA20 after a sharp pullback. The recent recovery is positive, but volatility is higher, so the bullish bias depends on price staying above the support area.

---

## 3. IWM / Russell 2000

| Item | Analysis |
|---|---|
| Current Chart Condition | Clear upward trend with higher highs and higher lows. |
| EMA20 Condition | Price is above EMA20. |
| Support | Around 285 to 286. |
| Resistance | Around 294 to 296. |
| Technical Bias | Bullish. |

### Comment

IWM is showing a positive trend. The chart has recovered from the recent pullback and remains above EMA20. If price breaks above the recent high, the bullish trend will become stronger.

---

## 4. XLK / Technology Sector

| Item | Analysis |
|---|---|
| Current Chart Condition | Strong rally from April to June, followed by a short pullback. |
| EMA20 Condition | Price is above EMA20. |
| Support | Around 180 to 182. |
| Resistance | Around 195 to 200. |
| Technical Bias | Bullish. |

### Comment

XLK is one of the strongest sector charts. The technology sector remains above EMA20 and still has strong upward momentum. The main risk is that price is close to the recent resistance area.

---

## 5. XLF / Financial Sector

| Item | Analysis |
|---|---|
| Current Chart Condition | Recovering after a weaker period earlier in the chart. |
| EMA20 Condition | Price is above EMA20. |
| Support | Around 51.80 to 52.00. |
| Resistance | Around 54.50 to 55.00. |
| Technical Bias | Neutral bullish. |

### Comment

XLF has improved after its previous downtrend. The price has moved back above EMA20, which is a positive signal. However, the chart is not as strong as NDX, IWM, or XLK because it still needs to break previous resistance.

---

## 6. XLV / Healthcare Sector

| Item | Analysis |
|---|---|
| Current Chart Condition | Recovery after a downtrend from March to May. |
| EMA20 Condition | Price is above EMA20. |
| Support | Around 149 to 150. |
| Resistance | Around 155 to 156. |
| Technical Bias | Neutral bullish / recovery bias. |

### Comment

XLV is recovering after a weaker period. The price has moved above EMA20, which is a positive sign. However, the chart still needs to break above the 155 to 156 resistance area before it becomes clearly bullish.

---

# Overall Technical Summary

| Asset | Technical Bias | Strength |
|---|---|---|
| SPY | Slightly bullish / neutral bullish | Medium |
| NDX | Bullish, but volatile | Strong |
| IWM | Bullish | Strong |
| XLK | Bullish | Strong |
| XLF | Neutral bullish | Medium |
| XLV | Neutral bullish / recovery | Medium |

## Final Summary

Most of the selected markets and ETFs are showing positive technical conditions. NDX, IWM, and XLK have the strongest bullish structures because they are trading above or near EMA20 and remain in clear upward trends.

SPY is still positive but currently consolidating near resistance. XLF and XLV are improving, but they are not as strong as NDX and XLK.

Overall, the W24 technical bias is:

**Neutral bullish to bullish**

---

# Evidence Used

The analysis is based on the uploaded ProRealTime chart screenshots for:

- SPY
- NDX
- IWM
- XLK
- XLF
- XLV

Each chart uses daily candles and EMA20.


---

# Automation Increment

## Automated Script

For Week 24, I created an automated data fetch script:

`fetch_market_data.py`

## Purpose

The purpose of this script is to automatically download market price data for the R5 Technical Agent assets and calculate technical indicators.

## Assets Fetched

| Asset | Purpose |
|---|---|
| SPY | Tracks S&P 500 |
| NDX | Tracks Nasdaq 100 |
| IWM | Tracks Russell 2000 |
| XLK | Technology sector |
| XLF | Financial sector |
| XLV | Healthcare sector |

## Indicators Calculated

| Indicator | Meaning |
|---|---|
| EMA20 | Short-term trend |
| EMA50 | Medium-term trend |
| EMA200 | Long-term trend |

## Why I Automated This First

I chose to automate market data fetching first because my role is R5 Technical Agent. My responsibility is to analyse SPX, NDX, IWM, and sector charts. Before doing technical analysis, I need updated price data and reliable indicators.

Automating the data fetch makes the weekly analysis more consistent and reduces manual work. It also gives the team a repeatable workflow for future weekly predictions.

## Output

The script saves one CSV file for each ETF inside the `data` folder. Each CSV includes daily price data and EMA20, EMA50, and EMA200 values.
