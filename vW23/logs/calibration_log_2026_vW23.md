# Calibration Log

## Purpose

This file tracks how well our team predictions match actual market results over time.

The focus is not only whether the prediction was right or wrong, but whether our confidence level was appropriate.

---

## Week 23 Actual Market Result

| Index | Actual Weekly Move | Direction |
|---|---:|---|
| SPX / S&P 500 | About -2.57% to -2.64% | Bearish |
| NDX / Nasdaq 100 | About -4.53% | Bearish |
| IWM / Russell 2000 | About -3.06% | Bearish |

---

## Week 23 Market Context

The actual market outcome was risk-off.

Key evidence:

- SPX, NDX, and IWM all declined.
- NDX was the weakest major index.
- VIX rose, showing higher market fear.
- Bitcoin dropped sharply.
- Technology was the weakest sector.
- Defensive sectors performed better than growth and cyclical sectors.

---

## Team Prediction Review

| Index | Team / AI Consensus Before Week | Actual Result | Direction Correct? | Range Correct? |
|---|---|---:|---|---|
| SPX | Neutral-to-Bullish / Bullish | About -2.57% to -2.64% | No | No |
| NDX | Bullish / strongest expected index | About -4.53% | No | No |
| IWM | Neutral to mildly bullish / fragile | About -3.06% | Partly cautious, but direction mostly wrong | No |

---

## Calibration Assessment

### What We Got Right

- The team identified weak June midterm seasonality as a key risk.
- The team noted geopolitical risk as an important contradiction.
- Some models, especially DeepSeek, warned that the market could become choppy or weaker.
- IWM was correctly identified as fragile by several models.

### What We Got Wrong

- The overall view was too optimistic.
- The models overweighted recent bullish technical momentum.
- The models underestimated how quickly risk sentiment could reverse.
- NDX was expected to be the strongest index, but it became the weakest.
- Technology leadership was treated as a bullish signal, but Technology later became the largest drag.

### Was Our Confidence Appropriate?

The confidence level should have been lower.

Most models used Medium confidence, which was better than High, but the team still leaned too bullish. Because the actual result was strongly bearish, the correct calibration should have been more cautious, probably Neutral or Bearish with Medium confidence.

---

## Calibration Score

| Area | Score | Comment |
|---|---:|---|
| Direction Accuracy | Low | Most predictions leaned bullish or neutral, but the market fell sharply |
| Range Accuracy | Low | Actual losses were outside most predicted upside or mild-downside ranges |
| Confidence Calibration | Medium-Low | Medium confidence avoided overconfidence, but the directional view was still wrong |
| Risk Awareness | Medium | Seasonal and geopolitical risks were identified, but not weighted enough |
| Overall Calibration | Low-Medium | Evidence quality was good, but final interpretation was too optimistic |

---

## Lessons for Next Sprint

Next sprint, the team should avoid relying too much on recent technical strength.

When Almanac, macro risk, and volatility risk all conflict with bullish technical momentum, the final view should be more cautious.

The team should also give more weight to sector rotation. If Technology weakens sharply, NDX can underperform quickly.

---

## Running Calibration Record

| Week | Regime Prediction | Confidence | Actual Result | Calibration Comment |
|---|---|---|---|---|
| W23 | Neutral-to-Bullish / Bullish bias | Medium | Bearish | Prediction was too optimistic. DeepSeek was closest because it gave a neutral and downside-aware view. |
