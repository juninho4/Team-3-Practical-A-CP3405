"""
generate_report.py

Pulls data from all three modules and writes a single Markdown report.

Usage:
    python generate_report.py                 # tries FedWatch via Selenium,
                                                # falls back to manual prompts
    python generate_report.py --no-fedwatch    # skip FedWatch entirely,
                                                # leaves that section as TODO

Output: ./fed_market_report_YYYY-MM-DD.md
"""

from __future__ import annotations
import argparse
import datetime as dt

import treasury_yields
import fedwatch
import finviz_futures


def fmt_pct(x, decimals=1):
    return f"{x:.{decimals}f}%" if isinstance(x, (int, float)) else "n/a"


def fmt_bps(x):
    if x is None:
        return "n/a"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.0f} bps"


def build_predictive_note(yields: dict, fw: dict) -> str:
    """
    A rules-of-thumb summary stitched together from the pulled data points.
    This is NOT investment advice -- it's a plain-language readout of what
    the curve shape + FedWatch odds mechanically imply, for a human to
    interpret further. Kept deliberately hedged.
    """
    lines = []

    curve = yields.get("curve_2s10s_bps")
    if curve is not None:
        if curve < 0:
            lines.append(
                f"- The 2s10s curve is **inverted** ({fmt_bps(curve)}), historically "
                "associated with markets pricing in slower growth or eventual rate cuts."
            )
        elif curve < 50:
            lines.append(
                f"- The 2s10s curve is positive but flat ({fmt_bps(curve)}), "
                "consistent with a market in a wait-and-see posture on growth/policy."
            )
        else:
            lines.append(
                f"- The 2s10s curve is meaningfully positive ({fmt_bps(curve)}), "
                "consistent with a market pricing steady/expansionary conditions ahead."
            )

    direction = yields.get("10y_direction")
    change = yields.get("10y_change_bps")
    if direction == "up":
        lines.append(
            f"- The 10-year yield rose {fmt_bps(change)} week-over-week -- "
            "typically reflects firmer growth/inflation expectations or reduced "
            "demand for duration."
        )
    elif direction == "down":
        lines.append(
            f"- The 10-year yield fell {fmt_bps(change)} week-over-week -- "
            "typically reflects safe-haven demand, softer growth data, or "
            "increased rate-cut expectations."
        )
    elif direction == "flat":
        lines.append("- The 10-year yield was roughly flat week-over-week.")

    hold = fw.get("hold_pct")
    cut = fw.get("cut_pct")
    hike = fw.get("hike_pct")
    if hold is not None:
        try:
            hold_f, cut_f, hike_f = float(hold), float(cut or 0), float(hike or 0)
            if hold_f >= 70:
                lines.append(
                    f"- Fed funds futures assign a **{fmt_pct(hold_f)} probability to a hold** "
                    "at the next meeting -- the market sees the Fed on pause."
                )
            elif cut_f > hold_f:
                lines.append(
                    f"- Fed funds futures now favor a **cut ({fmt_pct(cut_f)})** over a hold "
                    f"({fmt_pct(hold_f)}) at the next meeting."
                )
            else:
                lines.append(
                    f"- Odds are split: hold {fmt_pct(hold_f)} vs. cut {fmt_pct(cut_f)} "
                    f"vs. hike {fmt_pct(hike_f)}."
                )
        except (TypeError, ValueError):
            pass

    lines.append(
        "\n> This section is a mechanical readout of the pulled numbers, not investment "
        "advice or a forecast -- yields and futures-implied odds change intraday, and "
        "this reflects a single snapshot."
    )
    return "\n".join(lines)


def build_markdown(yields: dict, fed_rate: dict, meeting, fw: dict, futures: dict) -> str:
    today = dt.date.today().isoformat()
    md = []
    md.append(f"# Fed & Rates Market Snapshot — {today}\n")

    md.append("## Federal Reserve\n")
    if fed_rate:
        md.append(
            f"- **Current Fed funds target range:** {fed_rate['lower']:.2f}% – "
            f"{fed_rate['upper']:.2f}% (as of {fed_rate['date']})"
        )
    else:
        md.append("- Current Fed funds rate: _unavailable_")

    if meeting:
        end = meeting["end"]
        md.append(f"- **Next FOMC meeting:** {meeting['start']:%B %d} – {end:%B %d, %Y}")
    else:
        md.append("- Next FOMC meeting: _could not parse federalreserve.gov calendar — check manually_")

    md.append("\n### CME FedWatch (30-Day Fed Funds futures-implied odds)\n")
    if fw.get("manual_entry"):
        md.append("_Entered manually — automated scrape was unavailable this run._\n")
    md.append(f"- Meeting: {fw.get('meeting_date', 'n/a')}")
    md.append(f"- Hold probability: {fmt_pct(fw.get('hold_pct'))}")
    md.append(f"- Cut probability: {fmt_pct(fw.get('cut_pct'))}")
    md.append(f"- Hike probability: {fmt_pct(fw.get('hike_pct'))}")

    md.append("\n## Treasury Yields\n")
    md.append(f"Latest data: **{yields['latest_date']}** | Prior week: **{yields['prior_week_date']}**\n")
    md.append("| Maturity | Latest | Prior Week | Change |")
    md.append("|---|---|---|---|")
    for mat in ("2Y", "10Y", "30Y"):
        latest_v = yields["latest"].get(mat)
        prior_v = yields["prior_week"].get(mat)
        chg = None
        if latest_v is not None and prior_v is not None:
            chg = round((latest_v - prior_v) * 100, 1)
        md.append(
            f"| {mat} | {latest_v if latest_v is not None else 'n/a'}% "
            f"| {prior_v if prior_v is not None else 'n/a'}% "
            f"| {fmt_bps(chg)} |"
        )

    md.append(f"\n- **2s10s yield curve:** {fmt_bps(yields.get('curve_2s10s_bps'))} "
               f"{'(inverted)' if (yields.get('curve_2s10s_bps') or 0) < 0 else ''}")
    md.append(f"- **10-year direction this week:** {yields.get('10y_direction', 'n/a').upper()} "
               f"({fmt_bps(yields.get('10y_change_bps'))})")

    md.append("\n## Commodities & Dollar (Finviz Futures, 1-Week Change)\n")
    md.append("| Instrument | Last | 1W Change |")
    md.append("|---|---|---|")
    for name, data in futures.items():
        last = data.get("last")
        chg = data.get("change_1w_pct")
        md.append(
            f"| {name} | {last if last is not None else 'n/a'} "
            f"| {fmt_pct(chg) if chg is not None else 'n/a'} |"
        )

    md.append("\n## Predictive Implication (mechanical readout, not advice)\n")
    md.append(build_predictive_note(yields, fw))

    md.append(f"\n---\n*Generated {dt.datetime.now():%Y-%m-%d %H:%M} local time. "
               "Sources: home.treasury.gov, federalreserve.gov, FRED (fred.stlouisfed.org), "
               "CME FedWatch (cmegroup.com), Finviz (finviz.com/futures.ashx). "
               "Not investment advice.*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fedwatch", action="store_true",
                         help="Skip the FedWatch scrape entirely (leaves placeholders)")
    parser.add_argument("--no-headless", action="store_true",
                         help="Run the FedWatch browser visibly (useful for debugging)")
    args = parser.parse_args()

    print("Fetching Treasury yields...")
    yields = treasury_yields.get_current_and_prior_week()

    print("Fetching current Fed funds rate...")
    try:
        fed_rate = fedwatch.get_current_fed_funds_rate()
    except Exception as e:
        print(f"  WARNING: {e}")
        fed_rate = None

    print("Fetching next FOMC meeting date...")
    try:
        meeting = fedwatch.get_next_fomc_meeting()
    except Exception as e:
        print(f"  WARNING: {e}")
        meeting = None

    if args.no_fedwatch:
        fw = {"meeting_date": None, "hold_pct": None, "cut_pct": None, "hike_pct": None}
    else:
        print("Fetching FedWatch probabilities (this launches a headless browser)...")
        fw = fedwatch.get_fedwatch_probabilities_or_manual(headless=not args.no_headless)

    print("Fetching Finviz futures (WTI, Gold, DXY)...")
    try:
        futures = finviz_futures.get_weekly_futures_changes()
    except Exception as e:
        print(f"  WARNING: {e}")
        futures = {name: {"last": None, "change_1w_pct": None}
                   for name in finviz_futures.TARGET_INSTRUMENTS}

    print("Building report...")
    md = build_markdown(yields, fed_rate, meeting, fw, futures)

    out_path = f"fed_market_report_{dt.date.today().isoformat()}.md"
    with open(out_path, "w") as f:
        f.write(md)

    print(f"\nDone -> {out_path}")


if __name__ == "__main__":
    main()
