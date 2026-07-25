#!/usr/bin/env python3
"""Generate the weekly R3 Almanac analysis used by the integrated pipeline.

R3 owns three evidence types:
1. seasonal patterns from Stock Trader's Almanac 2026;
2. the 2026 midterm-election historical analogue; and
3. calendar signals such as options expiry, FOMC meetings and earnings season.

The script writes directly into ``vWXX/agents/almanac``.  Each run uses the
requested ISO week in both filenames and file contents, so a later week never
overwrites an earlier week's evidence.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import fitz


SINGAPORE_TIME = timezone(timedelta(hours=8))
EXPECTED_PDF_NAME = "Stock Trader's Almanac 2026_L.pdf"
PDF_YEAR = 2026

MARKETS = ["DJIA", "S&P 500", "NASDAQ", "Russell 1K", "Russell 2K"]
TEAM_MARKETS = ["S&P 500", "NASDAQ", "Russell 2K"]
MARKET_MAPPING = {
    "S&P 500": "SPX",
    "NASDAQ": "NDX proxy",
    "Russell 2K": "IWM proxy",
}

FOMC_2026 = [
    (date(2026, 1, 27), date(2026, 1, 28), False),
    (date(2026, 3, 17), date(2026, 3, 18), True),
    (date(2026, 4, 28), date(2026, 4, 29), False),
    (date(2026, 6, 16), date(2026, 6, 17), True),
    (date(2026, 7, 28), date(2026, 7, 29), False),
    (date(2026, 9, 15), date(2026, 9, 16), True),
    (date(2026, 10, 27), date(2026, 10, 28), False),
    (date(2026, 12, 8), date(2026, 12, 9), True),
]

# Approximate broad windows, used only as a risk/dispersion flag.  They are not
# presented as exact company reporting dates.
EARNINGS_WINDOWS_2026 = [
    (date(2026, 1, 12), date(2026, 2, 13), "Q4 2025 earnings season"),
    (date(2026, 4, 13), date(2026, 5, 15), "Q1 2026 earnings season"),
    (date(2026, 7, 13), date(2026, 8, 14), "Q2 2026 earnings season"),
    (date(2026, 10, 12), date(2026, 11, 13), "Q3 2026 earnings season"),
]

MARKET_SPECIAL_DAYS_2026 = {
    date(2026, 1, 1): ("New Year's Day", "Closed"),
    date(2026, 1, 19): ("Martin Luther King Jr. Day", "Closed"),
    date(2026, 2, 16): ("Presidents Day", "Closed"),
    date(2026, 4, 3): ("Good Friday", "Closed"),
    date(2026, 5, 25): ("Memorial Day", "Closed"),
    date(2026, 6, 19): ("Juneteenth", "Closed"),
    date(2026, 7, 3): ("Independence Day observed", "Closed"),
    date(2026, 9, 7): ("Labor Day", "Closed"),
    date(2026, 11, 26): ("Thanksgiving Day", "Closed"),
    date(2026, 11, 27): ("Day after Thanksgiving", "Early close at 1:00 p.m. ET"),
    date(2026, 12, 24): ("Christmas Eve", "Early close at 1:00 p.m. ET"),
    date(2026, 12, 25): ("Christmas Day", "Closed"),
}


class R3Error(RuntimeError):
    """Raised when reliable R3 evidence cannot be produced."""


@dataclass(frozen=True)
class MonthEvidence:
    month: int
    month_name: str
    pdf_page: int
    highlights: list[str]
    rank: dict[str, int]
    up_years: dict[str, int]
    down_years: dict[str, int]
    average_return: dict[str, float]
    midterm_return: dict[str, float]
    expiration_week_return: dict[str, float]
    week_after_expiration_return: dict[str, float]
    first_day_return: dict[str, float]
    last_day_return: dict[str, float]


@dataclass(frozen=True)
class CalendarSignal:
    name: str
    dates: str
    direction: str
    confidence: str
    score: float | None
    note: str
    source: str


def singapore_today() -> date:
    return datetime.now(SINGAPORE_TIME).date()


def parse_monday(value: str) -> date:
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--week-start must use YYYY-MM-DD"
        ) from exc
    if result.weekday() != 0:
        raise argparse.ArgumentTypeError("--week-start must be a Monday")
    return result


def default_monday() -> date:
    today = singapore_today()
    return today - timedelta(days=today.weekday())


def normalize_week_label(value: str, week_start: date) -> str:
    expected = f"vW{week_start.isocalendar().week:02d}"
    match = re.fullmatch(r"(?:v)?W(\d{1,2})", value.strip(), re.IGNORECASE)
    if match is None:
        raise R3Error("Use a week label such as vW30 or W30")
    normalized = f"vW{int(match.group(1)):02d}"
    if normalized != expected:
        raise R3Error(
            f"Week label {normalized} does not match --week-start {week_start} "
            f"({expected})"
        )
    return normalized


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_pdf(explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise R3Error(f"Almanac PDF was not found: {path}")
        return path

    root = project_root()
    candidates = [
        root / "information" / EXPECTED_PDF_NAME,
        root / "py" / EXPECTED_PDF_NAME,
    ]
    candidates.extend(sorted((root / "information").glob("Stock Trader's Almanac 2026_L*.pdf")))
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise R3Error(
        f"Put {EXPECTED_PDF_NAME} in {root / 'information'} or pass --pdf"
    )


def clean_text(text: str) -> str:
    return (
        text.replace("–", "-")
        .replace("−", "-")
        .replace("—", "-")
        .replace("\u00a0", " ")
    )


def numeric_values(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"(?<![\d/])-?\d+(?:\.\d+)?", text)]


def row_values(table: str, start: str, end: str, integer: bool = False) -> list[float] | list[int]:
    match = re.search(start + r"\s*(.*?)\s*" + end, table, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        raise R3Error(f"Could not parse Almanac row: {start}")
    values = numeric_values(match.group(1))[: len(MARKETS)]
    if len(values) != len(MARKETS):
        raise R3Error(f"Almanac row {start} returned {len(values)} values, expected 5")
    if integer:
        return [int(value) for value in values]
    return values


def as_market_dict(values: Iterable[float | int]) -> dict[str, float | int]:
    return dict(zip(MARKETS, values, strict=True))


def find_month_page(document: fitz.Document, month_name: str) -> tuple[int, str]:
    heading = f"{month_name.upper()} ALMANAC"
    matches: list[tuple[int, str]] = []
    for index, page in enumerate(document):
        text = page.get_text()
        if text.lstrip().startswith(heading) and "Vital Statistics" in text:
            matches.append((index, text))
    if len(matches) != 1:
        pages = [index + 1 for index, _ in matches]
        raise R3Error(f"Expected one {heading} page, found PDF pages {pages}")
    return matches[0]


def extract_highlights(text: str, month_name: str) -> list[str]:
    end_marker = f"{month_name.title()} Vital Statistics"
    intro = text.split(end_marker, 1)[0]
    intro = intro.split("page 126.", 1)[-1]
    highlights: list[str] = []
    for item in intro.split("◆"):
        item = re.sub(r"\s+", " ", item).strip(" .\n")
        if len(item) < 12:
            continue
        highlights.append(item[:240].rstrip())
    return highlights[:6]


def section_average_values(text: str, title: str, next_titles: list[str]) -> dict[str, float]:
    start = text.find(title)
    if start < 0:
        raise R3Error(f"Could not find Almanac statistics section: {title}")
    endings = [text.find(item, start + len(title)) for item in next_titles]
    endings = [position for position in endings if position >= 0]
    end = min(endings) if endings else len(text)
    section = text[start:end]
    # A few Almanac pages omit the word "Change" after "Avg %" even though
    # the five values are the same statistic.
    matches = list(
        re.finditer(r"Avg\s*%(?:\s*Change)?", section, flags=re.IGNORECASE)
    )
    if not matches:
        raise R3Error(f"Could not find average returns in section: {title}")
    values = numeric_values(section[matches[-1].end() :])[: len(MARKETS)]
    if len(values) != len(MARKETS):
        raise R3Error(f"Section {title} returned {len(values)} values, expected 5")
    return {key: float(value) for key, value in as_market_dict(values).items()}


def parse_month(document: fitz.Document, month: int) -> MonthEvidence:
    month_name = date(PDF_YEAR, month, 1).strftime("%B")
    page_index, raw_text = find_month_page(document, month_name)
    text = clean_text(raw_text)
    if "Vital Statistics" not in text:
        raise R3Error(f"{month_name} Vital Statistics table is missing")
    table = text.split("Vital Statistics", 1)[1]

    rank = as_market_dict(row_values(table, r"\bRank\b", r"\bUp\b", integer=True))
    up_years = as_market_dict(row_values(table, r"\bUp\b", r"\bDown\b", integer=True))
    down_years = as_market_dict(
        row_values(table, r"\bDown\b", r"Average\s*%\s*Change", integer=True)
    )
    average = as_market_dict(
        row_values(table, r"Average\s*%\s*Change", r"Midterm\s*Yr\s*Avg\s*%\s*Chg")
    )
    midterm = as_market_dict(
        row_values(table, r"Midterm\s*Yr\s*Avg\s*%\s*Chg", r"Best\s*&\s*Worst")
    )

    stats_text = clean_text(document[page_index + 1].get_text())
    expiration = section_average_values(
        stats_text,
        "Monthly Options Expiration Week",
        ["Week After Monthly Options Expiration", "First Trading Day Performance"],
    )
    after_expiration = section_average_values(
        stats_text,
        "Week After Monthly Options Expiration",
        ["First Trading Day Performance"],
    )
    first_day = section_average_values(
        stats_text,
        "First Trading Day Performance",
        ["Last Trading Day Performance"],
    )
    last_day = section_average_values(
        stats_text,
        "Last Trading Day Performance",
        ["Dow & S&P"],
    )

    return MonthEvidence(
        month=month,
        month_name=month_name,
        pdf_page=page_index + 1,
        highlights=extract_highlights(text, month_name),
        rank={key: int(value) for key, value in rank.items()},
        up_years={key: int(value) for key, value in up_years.items()},
        down_years={key: int(value) for key, value in down_years.items()},
        average_return={key: float(value) for key, value in average.items()},
        midterm_return={key: float(value) for key, value in midterm.items()},
        expiration_week_return=expiration,
        week_after_expiration_return=after_expiration,
        first_day_return=first_day,
        last_day_return=last_day,
    )


def days_in_week(week_start: date) -> list[date]:
    return [week_start + timedelta(days=offset) for offset in range(7)]


def third_friday(year: int, month: int) -> date:
    day = date(year, month, 15)
    return day + timedelta(days=(4 - day.weekday()) % 7)


def first_weekday(year: int, month: int) -> date:
    day = date(year, month, 1)
    while day.weekday() >= 5 or MARKET_SPECIAL_DAYS_2026.get(day, ("", ""))[1] == "Closed":
        day += timedelta(days=1)
    return day


def last_weekday(year: int, month: int) -> date:
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    day = next_month - timedelta(days=1)
    while day.weekday() >= 5 or MARKET_SPECIAL_DAYS_2026.get(day, ("", ""))[1] == "Closed":
        day -= timedelta(days=1)
    return day


def overlaps(start: date, end: date, week_start: date, week_end: date) -> bool:
    return start <= week_end and end >= week_start


def direction(value: float, neutral_band: float = 0.10) -> str:
    if value > neutral_band:
        return "Bullish"
    if value < -neutral_band:
        return "Bearish"
    return "Neutral"


def average_for_team(values: dict[str, float]) -> float:
    return sum(values[market] for market in TEAM_MARKETS) / len(TEAM_MARKETS)


def calendar_signals(
    week_start: date,
    week_end: date,
    evidence_by_month: dict[int, MonthEvidence],
) -> list[CalendarSignal]:
    signals: list[CalendarSignal] = []
    months = sorted(evidence_by_month)

    for month in months:
        evidence = evidence_by_month[month]
        expiry = third_friday(week_start.year, month)
        expiry_week_start = expiry - timedelta(days=expiry.weekday())
        expiry_week_end = expiry_week_start + timedelta(days=6)
        after_start = expiry_week_start + timedelta(days=7)
        after_end = after_start + timedelta(days=6)

        if overlaps(expiry_week_start, expiry_week_end, week_start, week_end):
            score = average_for_team(evidence.expiration_week_return)
            triple = month in {3, 6, 9, 12}
            signals.append(
                CalendarSignal(
                    name=("Triple-witching week" if triple else "Monthly options-expiration week"),
                    dates=f"{expiry_week_start.isoformat()} to {expiry_week_end.isoformat()}",
                    direction=direction(score),
                    confidence="Medium",
                    score=score,
                    note=(
                        f"Historical average across SPX/NDX-proxy/IWM-proxy: {score:+.2f}%. "
                        "Expiration flows can increase volatility."
                    ),
                    source=f"Almanac PDF page {evidence.pdf_page + 1}",
                )
            )

        if overlaps(after_start, after_end, week_start, week_end):
            score = average_for_team(evidence.week_after_expiration_return)
            signals.append(
                CalendarSignal(
                    name="Week after monthly options expiration",
                    dates=f"{after_start.isoformat()} to {after_end.isoformat()}",
                    direction=direction(score),
                    confidence="Medium",
                    score=score,
                    note=f"Historical average across SPX/NDX-proxy/IWM-proxy: {score:+.2f}%.",
                    source=f"Almanac PDF page {evidence.pdf_page + 1}",
                )
            )

        first_day = first_weekday(week_start.year, month)
        if week_start <= first_day <= week_end:
            score = average_for_team(evidence.first_day_return)
            signals.append(
                CalendarSignal(
                    name="First trading-day seasonal tendency",
                    dates=first_day.isoformat(),
                    direction=direction(score, 0.05),
                    confidence="Medium",
                    score=score,
                    note=f"Historical first-day average across team proxies: {score:+.2f}%.",
                    source=f"Almanac PDF page {evidence.pdf_page + 1}",
                )
            )

        last_day = last_weekday(week_start.year, month)
        if week_start <= last_day <= week_end:
            score = average_for_team(evidence.last_day_return)
            signals.append(
                CalendarSignal(
                    name="Last trading-day seasonal tendency",
                    dates=last_day.isoformat(),
                    direction=direction(score, 0.05),
                    confidence="Medium",
                    score=score,
                    note=f"Historical last-day average across team proxies: {score:+.2f}%.",
                    source=f"Almanac PDF page {evidence.pdf_page + 1}",
                )
            )

        if month in {1, 4, 7, 10} and week_start <= first_day <= week_end:
            signals.append(
                CalendarSignal(
                    name="Opening month of a new quarter",
                    dates=first_day.isoformat(),
                    direction="Bullish",
                    confidence="Medium",
                    score=0.25,
                    note="Almanac highlights institutional cash-flow strength in first months of quarters.",
                    source=f"Almanac PDF page {evidence.pdf_page}",
                )
            )

    for meeting_start, meeting_end, has_sep in FOMC_2026:
        if overlaps(meeting_start, meeting_end, week_start, week_end):
            signals.append(
                CalendarSignal(
                    name="FOMC meeting" + (" with SEP" if has_sep else ""),
                    dates=f"{meeting_start.isoformat()} to {meeting_end.isoformat()}",
                    direction="Mixed / volatility",
                    confidence="High",
                    score=None,
                    note="Policy communication is a major event risk; R3 does not assume its direction in advance.",
                    source="Federal Reserve 2026 FOMC calendar",
                )
            )

    for earnings_start, earnings_end, label in EARNINGS_WINDOWS_2026:
        if overlaps(earnings_start, earnings_end, week_start, week_end):
            signals.append(
                CalendarSignal(
                    name=label,
                    dates=f"{earnings_start.isoformat()} to {earnings_end.isoformat()}",
                    direction="Mixed / volatility",
                    confidence="Medium",
                    score=None,
                    note="Approximate broad reporting window; expect higher company and index dispersion.",
                    source="Calendar convention (approximate window)",
                )
            )

    for event_day, (label, status) in MARKET_SPECIAL_DAYS_2026.items():
        if week_start <= event_day <= week_end:
            signals.append(
                CalendarSignal(
                    name=f"U.S. equity market: {label}",
                    dates=event_day.isoformat(),
                    direction="Liquidity / schedule",
                    confidence="High",
                    score=None,
                    note=f"Nasdaq 2026 calendar status: {status}.",
                    source="Nasdaq Trader 2026 holiday calendar",
                )
            )

    return signals


def score_report(
    week_days: list[date],
    evidence_by_month: dict[int, MonthEvidence],
    signals: list[CalendarSignal],
) -> tuple[float, str, str, list[str]]:
    month_counts = Counter(day.month for day in week_days)
    components: list[float] = []
    explanations: list[str] = []

    for month, count in month_counts.items():
        evidence = evidence_by_month[month]
        market_values = [evidence.midterm_return[market] for market in TEAM_MARKETS]
        month_score = sum(market_values) / len(market_values)
        components.extend([month_score] * count)
        explanations.append(
            f"{evidence.month_name} midterm analogue averages {month_score:+.2f}% "
            "across SPX, NASDAQ (NDX proxy) and Russell 2K (IWM proxy)."
        )

    for signal in signals:
        if signal.score is not None:
            components.append(signal.score)

    if not components:
        raise R3Error("No numeric seasonal evidence was available")
    score = sum(components) / len(components)

    if score >= 0.75:
        verdict = "Bullish"
    elif score >= 0.15:
        verdict = "Slightly Bullish"
    elif score > -0.15:
        verdict = "Neutral"
    elif score > -0.75:
        verdict = "Slightly Bearish"
    else:
        verdict = "Bearish"

    signs = {direction(value) for value in components if direction(value) != "Neutral"}
    event_risk = any(signal.direction == "Mixed / volatility" for signal in signals)
    if len(components) >= 6 and len(signs) <= 1 and not event_risk:
        confidence = "High"
    elif len(components) >= 3:
        confidence = "Medium"
    else:
        confidence = "Low"
    if event_risk:
        explanations.append("Scheduled event risk lowers confidence in a purely seasonal call.")
    return score, verdict, confidence, explanations


def highlight_direction(text: str) -> str:
    lower = text.casefold()
    positive = any(word in lower for word in ["best", "strength", "gain", "bullish", " up "])
    negative = any(word in lower for word in ["worst", "weak", "bearish", "down", "danger"])
    if positive and negative:
        return "Mixed"
    if positive:
        return "Bullish"
    if negative:
        return "Bearish"
    return "Context"


def render_evidence_images(
    document: fitz.Document,
    evidence_by_month: dict[int, MonthEvidence],
    output_dir: Path,
    week_label: str,
) -> list[Path]:
    outputs: list[Path] = []
    for evidence in evidence_by_month.values():
        page = document[evidence.pdf_page - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        output = output_dir / (
            f"{week_label}_{evidence.month_name.lower()}_vital_statistics.png"
        )
        pixmap.save(output)
        outputs.append(output)
    return outputs


def write_csv(
    path: Path,
    week_label: str,
    week_start: date,
    week_end: date,
    evidence_by_month: dict[int, MonthEvidence],
    signals: list[CalendarSignal],
) -> None:
    fields = [
        "Sprint Week",
        "ISO Week",
        "Analysis Start",
        "Analysis End",
        "Evidence Type",
        "Month",
        "Market",
        "Metric",
        "Value",
        "Unit",
        "Direction",
        "Confidence",
        "Source",
        "PDF Page",
        "Note",
    ]
    rows: list[dict[str, str]] = []
    iso_week = f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}"
    base = {
        "Sprint Week": week_label,
        "ISO Week": iso_week,
        "Analysis Start": week_start.isoformat(),
        "Analysis End": week_end.isoformat(),
    }

    for evidence in evidence_by_month.values():
        for market in TEAM_MARKETS:
            display_market = MARKET_MAPPING[market]
            for metric, value in [
                ("All-year monthly average", evidence.average_return[market]),
                ("Midterm-year monthly average", evidence.midterm_return[market]),
            ]:
                rows.append(
                    {
                        **base,
                        "Evidence Type": "Historical seasonal statistic",
                        "Month": evidence.month_name,
                        "Market": display_market,
                        "Metric": metric,
                        "Value": f"{value:.2f}",
                        "Unit": "%",
                        "Direction": direction(value),
                        "Confidence": "High",
                        "Source": EXPECTED_PDF_NAME,
                        "PDF Page": str(evidence.pdf_page),
                        "Note": (
                            f"Rank {evidence.rank[market]}; "
                            f"up {evidence.up_years[market]}, down {evidence.down_years[market]}"
                        ),
                    }
                )
        for highlight in evidence.highlights:
            rows.append(
                {
                    **base,
                    "Evidence Type": "Almanac highlight",
                    "Month": evidence.month_name,
                    "Market": "Broad US market",
                    "Metric": "Published seasonal observation",
                    "Value": "",
                    "Unit": "",
                    "Direction": highlight_direction(highlight),
                    "Confidence": "Medium",
                    "Source": EXPECTED_PDF_NAME,
                    "PDF Page": str(evidence.pdf_page),
                    "Note": highlight,
                }
            )

    for signal in signals:
        rows.append(
            {
                **base,
                "Evidence Type": "Calendar signal",
                "Month": "",
                "Market": "Broad US market",
                "Metric": signal.name,
                "Value": "" if signal.score is None else f"{signal.score:.2f}",
                "Unit": "" if signal.score is None else "%",
                "Direction": signal.direction,
                "Confidence": signal.confidence,
                "Source": signal.source,
                "PDF Page": "",
                "Note": f"{signal.dates}: {signal.note}",
            }
        )

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table_row(values: list[str]) -> str:
    return "| " + " | ".join(value.replace("|", "/") for value in values) + " |"


def write_markdown(
    path: Path,
    week_label: str,
    week_start: date,
    week_end: date,
    evidence_by_month: dict[int, MonthEvidence],
    signals: list[CalendarSignal],
    score: float,
    verdict: str,
    confidence: str,
    explanations: list[str],
    image_paths: list[Path],
) -> None:
    iso = week_start.isocalendar()
    lines = [
        f"<!-- sprint-week: {week_label} -->",
        f"# R3 Almanac Agent Output - {week_label}",
        "",
        "## Analysis Window",
        "",
        f"- Sprint week: **{week_label}** (ISO {iso.year}-W{iso.week:02d})",
        f"- Dates: **{week_start.isoformat()} to {week_end.isoformat()}**",
        f"- Source edition: **Stock Trader's Almanac 2026**",
        "- Required R3 scope: seasonal patterns, historical analogues, and calendar-based signals",
        "",
        "## Executive Read",
        "",
        f"- Almanac verdict: **{verdict}**",
        f"- Confidence contribution: **{confidence}**",
        f"- Composite seasonal score: **{score:+.2f}%**",
        "",
    ]
    lines.extend(f"- {item}" for item in explanations)

    lines.extend(
        [
            "",
            "## Historical Pattern Table",
            "",
            "2026 is a U.S. midterm-election year, so the midterm-year column is the primary historical analogue.",
            "",
            "| Month | Team market | Rank | Up/Down years | All-year avg | Midterm avg | Signal |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for evidence in evidence_by_month.values():
        for market in TEAM_MARKETS:
            value = evidence.midterm_return[market]
            lines.append(
                markdown_table_row(
                    [
                        evidence.month_name,
                        MARKET_MAPPING[market],
                        str(evidence.rank[market]),
                        f"{evidence.up_years[market]}/{evidence.down_years[market]}",
                        f"{evidence.average_return[market]:+.1f}%",
                        f"{value:+.1f}%",
                        direction(value),
                    ]
                )
            )

    lines.extend(["", "## Calendar-Based Signals", ""])
    if signals:
        lines.extend(
            [
                "| Event | Date(s) | Signal | Confidence | Interpretation |",
                "|---|---|---|---|---|",
            ]
        )
        for signal in signals:
            lines.append(
                markdown_table_row(
                    [signal.name, signal.dates, signal.direction, signal.confidence, signal.note]
                )
            )
    else:
        lines.append("No major expiry, FOMC, month-end, quarter-start, or earnings-window flag was detected for this week.")

    lines.extend(["", "## Almanac Seasonal Highlights", ""])
    for evidence in evidence_by_month.values():
        lines.append(f"### {evidence.month_name}")
        lines.append("")
        if evidence.highlights:
            lines.extend(f"- {item}" for item in evidence.highlights[:4])
        else:
            lines.append("- No reliable bullet highlights were extracted; use the statistics table above.")
        lines.append("")

    lines.extend(
        [
            "## Monday Speaking Point",
            "",
            (
                f"R3 reads the {week_label} seasonal backdrop as **{verdict.lower()}** with "
                f"**{confidence.lower()} confidence**. The 2026 midterm analogue gives a "
                f"{score:+.2f}% composite signal across SPX, the NASDAQ proxy for NDX, and "
                "Russell 2K as the IWM proxy. Calendar event risk should be checked against R4 "
                "macro and R5 technical evidence before the final call."
            ),
            "",
            "## Evidence Files",
            "",
            f"- `{week_label}_almanac_evidence.csv`",
        ]
    )
    lines.extend(f"- `{image.name}`" for image in image_paths)
    lines.extend(
        [
            "",
            "## Method and Limitations",
            "",
            "- NDX is represented by the Almanac NASDAQ series; IWM is represented by Russell 2K.",
            "- Seasonal history is a context signal, not a live-price forecast and not investment advice.",
            "- FOMC dates use the Federal Reserve 2026 meeting calendar. Earnings windows are approximate and are treated only as volatility flags.",
            "- Federal Reserve calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            "- Nasdaq market calendar: https://www.nasdaqtrader.com/trader.aspx?id=calendar",
            "- If a week crosses a month boundary, every month touched by that Monday-Sunday window is included in the same weekly report.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    week_start: date,
    week_label: str,
    pdf_path: Path,
    output_dir: Path,
) -> tuple[Path, Path, list[Path]]:
    week_end = week_start + timedelta(days=6)
    if week_start.year != PDF_YEAR or week_end.year != PDF_YEAR:
        raise R3Error(
            f"This source edition supports 2026 weeks only; received {week_start} to {week_end}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    week_days = days_in_week(week_start)
    months = list(dict.fromkeys(day.month for day in week_days))

    with fitz.open(pdf_path) as document:
        evidence_by_month = {month: parse_month(document, month) for month in months}
        signals = calendar_signals(week_start, week_end, evidence_by_month)
        score, verdict, confidence, explanations = score_report(
            week_days, evidence_by_month, signals
        )
        images = render_evidence_images(
            document, evidence_by_month, output_dir, week_label
        )

    csv_path = output_dir / f"{week_label}_almanac_evidence.csv"
    report_path = output_dir / f"{week_label}_almanac.md"
    write_csv(
        csv_path,
        week_label,
        week_start,
        week_end,
        evidence_by_month,
        signals,
    )
    write_markdown(
        report_path,
        week_label,
        week_start,
        week_end,
        evidence_by_month,
        signals,
        score,
        verdict,
        confidence,
        explanations,
        images,
    )

    print(f"[R3] Week: {week_label} ({week_start} to {week_end})")
    print(f"[R3] Report: {report_path}")
    print(f"[R3] Evidence CSV: {csv_path}")
    for image in images:
        print(f"[R3] Evidence image: {image}")
    return report_path, csv_path, images


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate weekly R3 seasonal, historical and calendar evidence"
    )
    parser.add_argument(
        "--week-start",
        type=parse_monday,
        default=default_monday(),
        help="Monday of the analysis week in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--week-label",
        help="Sprint label such as vW30; default comes from --week-start",
    )
    parser.add_argument("--pdf", type=Path, help="Optional Almanac PDF path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Default: repository-root/vWXX/agents/almanac",
    )
    args = parser.parse_args()

    try:
        week_label = (
            normalize_week_label(args.week_label, args.week_start)
            if args.week_label
            else f"vW{args.week_start.isocalendar().week:02d}"
        )
        pdf_path = find_pdf(args.pdf)
        output_dir = args.output_dir
        if output_dir is None:
            output_dir = project_root().parent / week_label / "agents" / "almanac"
        run(args.week_start, week_label, pdf_path, output_dir.resolve())
    except (R3Error, OSError, RuntimeError) as exc:
        print(f"[R3] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
