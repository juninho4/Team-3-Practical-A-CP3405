# LLM Comparison vW30

## Role

R8 LLM Synthesis Operator

## Models Used

- Gemini
- OpenRouter

All 2 successful model(s) were given the same shared prompt and the same evidence package, including:

- Almanac evidence
- Macro / News evidence
- Technical evidence

---

## Shared Prompt

- `vW30/llm/shared_prompt.md`

---

## Raw LLM Responses

Raw AI responses are saved in:

- `vW30/llm/synthesis_gemini.txt`
- `vW30/llm/synthesis_openrouter.txt`

---

## Comparison Table

| Dimension | Gemini | OpenRouter |
|---|---|---|
| Weekly Regime | Not found | Low/Medium/High with justification. Then up to 3 key supporting evidence items, up to 2 key contradictions. Then invalidation conditions. Then predicted % move ranges for SPX, N... |
| Confidence | Score | Low/Medium/High with justification. Then up to 3 key supporting evidence items, up to 2 key contradictions. Then invalidation conditions. Then predicted % move ranges for SPX, N... |
| SPX Direction | Bearish / Down | Bullish / Up |
| SPX % Range | -0.5% to -1.5% | [+X.X% to +X.X%] |
| NDX Direction | Bearish / Down | Bullish / Up |
| NDX % Range | -1.0% to -2.5% | [+X.X% to +X.X%] |
| IWM Direction | Bearish / Down | Bullish / Up |
| IWM % Range | -0.8% to -2.2% | [+X.X% to +X.X%] |
| Main Bullish / Stabilising Evidence | Not found | (2 points max) |
| Main Bearish Evidence | Not found | (3 points max) |
| Invalidation Condition | Not found | what would change this view |

---

## Agreement Between Models

The models mostly agreed that:

- Most models leaned toward a Uncertain weekly regime.
- SPX direction consensus was closest to Bearish / Down.
- NDX direction consensus was closest to Bearish / Down.
- IWM direction consensus was closest to Bearish / Down.

---

## Disagreement Between Models

The models disagreed on:

- Models assigned different confidence levels.
- Predicted percentage ranges differed, especially around the size of the expected move.
- Individual models weighted the same evidence differently.
- Individual models weighted the same evidence differently.

---

## Model-by-Model Notes

### Gemini

Gemini suggested a **Not found** regime with **Score** confidence.

Predicted ranges:

- SPX: -0.5% to -1.5%
- NDX: -1.0% to -2.5%
- IWM: -0.8% to -2.2%

Main reasoning:

- Not found

Key risk / invalidation:

- Not found

### OpenRouter

OpenRouter suggested a **Low/Medium/High with justification. Then up to 3 key supporting evidence items, up to 2 key contradictions. Then invalidation conditions. Then predicted % move ranges for SPX, NDX, IWM with direction and range. Then plain-English brief 2-3 sentences. Then disclaimer. Must be exactly that structure** regime with **Low/Medium/High with justification. Then up to 3 key supporting evidence items, up to 2 key contradictions. Then invalidation conditions. Then predicted % move ranges for SPX, NDX, IWM with direction and range. Then plain-English brief 2-3 sentences. Then disclaimer. Must be exactly that structure** confidence.

Predicted ranges:

- SPX: [+X.X% to +X.X%]
- NDX: [+X.X% to +X.X%]
- IWM: [+X.X% to +X.X%]

Main reasoning:

- (3 points max)

Key risk / invalidation:

- what would change this view

---

## R8 Synthesis Summary

The overall AI view is **Uncertain** with **Medium** confidence.

The strongest common argument is that:

- Most models leaned toward a Uncertain weekly regime.
- SPX direction consensus was closest to Bearish / Down.
- NDX direction consensus was closest to Bearish / Down.

The biggest uncertainty is:

- what would change this view

The most bullish model is:

- Gemini

The most bearish model is:

- Gemini

The most cautious model is:

- Gemini

This output will be passed to R7 Human Score Analyst for final human judgement.

---

## R8 Recommendation to R7

Suggested regime for human review:

**Uncertain**

Suggested confidence:

**Medium**

Suggested relative strength / weakness:

1. SPX: Bearish / Down
2. NDX: Bearish / Down
3. IWM: Bearish / Down

Suggested predicted ranges for human review:

- SPX: -0.5% to -1.5%
- NDX: -1.0% to -2.5%
- IWM: -0.8% to -2.2%

Suggested key risk:

- what would change this view

Suggested invalidation condition:

- what would change this view
