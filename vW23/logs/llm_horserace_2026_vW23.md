# LLM Horserace

## Purpose

This file tracks the performance of each AI model across weekly market prediction sprints.

The goal is to compare ChatGPT, Claude, Gemini, and DeepSeek based on prediction direction, percentage range, confidence, and reasoning quality.

---

## Week 23 Actual Result

| Index | Actual Weekly Move | Direction |
|---|---:|---|
| SPX / S&P 500 | About -2.57% to -2.64% | Bearish |
| NDX / Nasdaq 100 | About -4.53% | Bearish |
| IWM / Russell 2000 | About -3.06% | Bearish |

The actual result was clearly bearish and risk-off.

---

## Week 23 LLM Prediction Comparison

| Model | Regime | SPX Prediction | NDX Prediction | IWM Prediction | Confidence | Accuracy |
|---|---|---|---|---|---|---|
| ChatGPT | Bullish | +0.4% to +1.3% | +0.8% to +2.0% | +0.2% to +1.0% | Medium | Low |
| Claude | Neutral-to-Bullish | -0.5% to +1.5% | 0.0% to +2.0% | -1.0% to +1.0% | Medium | Medium-Low |
| DeepSeek | Neutral | -1.0% to +0.3% | -1.7% to +0.6% | -1.2% to +0.5% | Medium | Medium |
| Gemini | Bullish | +0.2% to +1.2% | +0.5% to +1.8% | -0.5% to +0.7% | Medium | Low |

---

## Model Ranking

| Rank | Model | Reason |
|---:|---|---|
| 1 | DeepSeek | Closest overall. It gave a Neutral view and included downside ranges for SPX, NDX, and IWM. It was still not bearish enough, but it was the least wrong. |
| 2 | Claude | More cautious than ChatGPT and Gemini. It allowed some downside for SPX and IWM, but still expected NDX to be positive. |
| 3 | Gemini | Bullish overall. It was slightly cautious on IWM, but wrong on SPX and NDX direction. |
| 4 | ChatGPT | Most clearly bullish across all three indexes and therefore least accurate this week. |

---

## Direction Score

| Model | SPX Direction | NDX Direction | IWM Direction | Direction Score |
|---|---|---|---|---:|
| ChatGPT | Wrong | Wrong | Wrong | 0 / 3 |
| Claude | Partly | Wrong | Partly | 1 / 3 |
| DeepSeek | Correct bias | Correct bias | Correct bias | 3 / 3 |
| Gemini | Wrong | Wrong | Partly | 1 / 3 |

---

## Range Score

| Model | Range Assessment | Score |
|---|---|---:|
| ChatGPT | Actual results were far below all predicted ranges | 0 / 3 |
| Claude | Allowed small downside for SPX and IWM, but actual losses were much larger | 1 / 3 |
| DeepSeek | Closest downside-aware ranges, but still not bearish enough | 2 / 3 |
| Gemini | Mostly bullish ranges, actual results were much lower | 0 / 3 |

---

## Confidence Score

| Model | Confidence | Assessment | Score |
|---|---|---|---:|
| ChatGPT | Medium | Confidence was not too high, but view was wrong | 1 / 2 |
| Claude | Medium | Reasonable caution, but still too optimistic | 1 / 2 |
| DeepSeek | Medium | Best calibrated because uncertainty was emphasised | 2 / 2 |
| Gemini | Medium | Confidence was moderate, but bullish view was wrong | 1 / 2 |

---

## Total Score

| Model | Direction Score | Range Score | Confidence Score | Total |
|---|---:|---:|---:|---:|
| ChatGPT | 0 | 0 | 1 | 1 / 8 |
| Claude | 1 | 1 | 1 | 3 / 8 |
| DeepSeek | 3 | 2 | 2 | 7 / 8 |
| Gemini | 1 | 0 | 1 | 2 / 8 |

---

## Current Leader

**DeepSeek**

DeepSeek performed best this week because it was the only model that did not commit to a bullish regime. It correctly recognised that bullish technical momentum conflicted with weak seasonality and geopolitical risk. Its predicted downside ranges were still too mild, but they were closer than the other models.

---

## What the Models Missed

The models mostly missed the size of the bearish move.

Main missed factors:

- They underestimated how quickly Technology could reverse from leadership to weakness.
- They gave too much weight to indexes being above EMA levels.
- They did not give enough weight to bearish June midterm seasonality.
- They underestimated the effect of volatility and risk-off rotation.
- They expected NDX to outperform, but NDX was actually the weakest index.

---

## Reflection

The best-performing model this week was DeepSeek because it gave the most cautious and downside-aware view.

The weakest-performing model this week was ChatGPT because it gave the clearest bullish forecast across SPX, NDX, and IWM.

Next week, the team should not automatically treat technical momentum as the main driver. If seasonality, macro risk, and sector rotation all warn against risk-on positioning, the team should reduce confidence or choose a more defensive regime.
