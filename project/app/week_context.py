#!/usr/bin/env python3
"""Shared ISO-week calculation for the integrated market pipeline."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


SINGAPORE_TIME = timezone(timedelta(hours=8))
WEEK_PATTERN = re.compile(r"^(?:v)?W(\d{1,2})$", re.IGNORECASE)


@dataclass(frozen=True)
class WeekContext:
    iso_year: int
    iso_week: int
    label: str
    monday: date


def singapore_today() -> date:
    return datetime.now(SINGAPORE_TIME).date()


def context_for_date(day: date) -> WeekContext:
    iso = day.isocalendar()
    return WeekContext(
        iso_year=iso.year,
        iso_week=iso.week,
        label=f"vW{iso.week:02d}",
        monday=date.fromisocalendar(iso.year, iso.week, 1),
    )


def parse_week_label(value: str) -> str:
    """Normalize W29/vW29 to vW29 and reject invalid week numbers."""
    match = WEEK_PATTERN.fullmatch(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError("Use a week label such as vW29 or W29")

    week = int(match.group(1))
    if not 1 <= week <= 53:
        raise argparse.ArgumentTypeError("ISO week must be between 1 and 53")
    return f"vW{week:02d}"


def resolve_week_context(requested: str | None = None) -> WeekContext:
    current = context_for_date(singapore_today())
    if requested is None:
        return current

    label = parse_week_label(requested)
    week = int(label[2:])
    try:
        monday = date.fromisocalendar(current.iso_year, week, 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{label} does not exist in ISO year {current.iso_year}"
        ) from exc
    return WeekContext(current.iso_year, week, label, monday)
