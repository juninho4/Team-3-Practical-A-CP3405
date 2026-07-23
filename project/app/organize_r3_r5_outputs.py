#!/usr/bin/env python3
"""Verify direct R3 output and move legacy R3/R5 output into the weekly layout.

Expected final location of this script:
    project/app/organize_r3_r5_outputs.py

Expected unchanged agent code location:
    project/py/r3_almanac_agent.py
    project/py/fetch_market_data.py

Final output layout:
    vWXX/agents/almanac/                      R3 files
    vWXX/technical agent/                     R5 files

The vWXX folder is stored at the repository root, beside .github and project.

Normal run:
    python organize_r3_r5_outputs.py

Optional source override:
    python organize_r3_r5_outputs.py --source-dir C:/path/to/project/py

The current R3 agent writes directly to ``vWXX/agents/almanac``.  Legacy
month-named R3 files are still accepted so older runs remain compatible.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

from week_context import WeekContext, resolve_week_context


R3_PATTERNS = [
    "*_vital_statistics.png",
    "*_almanac_evidence.csv",
    "*_almanac.md",
]

R5_ROOT_PATTERNS = [
    "technical_agent_output_*.csv",
    "technical_agent_output_*.json",
]

R5_FOLDER_PATTERNS = {
    "data": ["*.csv"],
    "charts": ["*.png"],
}


def project_root() -> Path:
    """Return project when this script is stored in project/app/."""
    script_directory = Path(__file__).resolve().parent

    if script_directory.name.casefold() == "app":
        return script_directory.parent

    # Development fallback when the script has not been placed in app yet.
    for parent in [script_directory, *script_directory.parents]:
        if (parent / "py").is_dir() and (parent / "app").is_dir():
            return parent

    return script_directory.parent


def unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def source_directories(source_override: Path | None) -> list[Path]:
    """Search likely working directories without scanning final output folders."""
    root = project_root()
    candidates = []
    if source_override is not None:
        candidates.append(source_override)
    candidates.extend([root / "py", Path.cwd()])
    return [path for path in unique_paths(candidates) if path.is_dir()]


def move_file(source: Path, destination: Path) -> str:
    source = source.resolve()
    destination = destination.resolve()

    if source == destination:
        return "already placed"

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    shutil.move(str(source), str(destination))
    return "moved"


def find_root_files(sources: list[Path], patterns: list[str]) -> list[Path]:
    matches: list[Path] = []
    for source_directory in sources:
        for pattern in patterns:
            matches.extend(path for path in source_directory.glob(pattern) if path.is_file())
    return unique_paths(matches)


def find_folder_files(
    sources: list[Path],
    folder_name: str,
    patterns: list[str],
) -> list[tuple[Path, Path]]:
    """Return each file and its path relative to data/ or charts/."""
    matches: list[tuple[Path, Path]] = []
    seen: set[Path] = set()

    for source_directory in sources:
        folder = source_directory / folder_name
        if not folder.is_dir():
            continue
        for pattern in patterns:
            for path in folder.glob(pattern):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                matches.append((resolved, path.relative_to(folder)))
    return matches


def add_week_to_csv(path: Path, week: WeekContext) -> None:
    """Add a Sprint Week column to generated evidence without editing agent code."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, csv.Error):
        return
    if not fieldnames:
        return
    if "Sprint Week" not in fieldnames:
        fieldnames.append("Sprint Week")
    for row in rows:
        row["Sprint Week"] = week.label

    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def add_week_to_json(path: Path, week: WeekContext) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                item["Sprint Week"] = week.label
    elif isinstance(data, dict):
        data["Sprint Week"] = week.label
    else:
        return
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def add_week_to_markdown(path: Path, week: WeekContext) -> None:
    marker = f"<!-- sprint-week: {week.label} -->"
    original = path.read_text(encoding="utf-8", errors="replace")
    if marker in original:
        return
    note = (
        f"{marker}\n"
        f"> Sprint week: **{week.label}** "
        f"(ISO {week.iso_year}-W{week.iso_week:02d})\n\n"
    )
    path.write_text(note + original, encoding="utf-8")


def r3_destination_name(source: Path, week: WeekContext) -> str:
    name = source.name.casefold()
    if name.endswith("_vital_statistics.png"):
        return f"{week.label}_vital_statistics.png"
    if name.endswith("_almanac_evidence.csv"):
        return f"{week.label}_almanac_evidence.csv"
    if name.endswith("_almanac.md"):
        return f"{week.label}_almanac.md"
    return f"{week.label}_{source.name}"


def r5_destination_name(source: Path, week: WeekContext) -> str:
    current = f"W{week.iso_week:02d}"
    return re.sub(
        r"(?i)(technical_agent_output_)W\d{1,2}",
        lambda match: match.group(1) + current,
        source.name,
    )


def move_r3_outputs(
    sources: list[Path], destination: Path, week: WeekContext
) -> list[Path]:
    moved: list[Path] = []
    for source in find_root_files(sources, R3_PATTERNS):
        target = destination / r3_destination_name(source, week)
        status = move_file(source, target)
        if target.suffix.casefold() == ".md":
            add_week_to_markdown(target, week)
        elif target.suffix.casefold() == ".csv":
            add_week_to_csv(target, week)
        print(f"[Organizer] R3 {status}: {target}")
        moved.append(target)
    return moved


def move_r5_outputs(
    sources: list[Path], destination: Path, week: WeekContext
) -> list[Path]:
    moved: list[Path] = []

    for source in find_root_files(sources, R5_ROOT_PATTERNS):
        target = destination / r5_destination_name(source, week)
        status = move_file(source, target)
        if target.suffix.casefold() == ".csv":
            add_week_to_csv(target, week)
        elif target.suffix.casefold() == ".json":
            add_week_to_json(target, week)
        print(f"[Organizer] R5 {status}: {target}")
        moved.append(target)

    for folder_name, patterns in R5_FOLDER_PATTERNS.items():
        for source, relative_path in find_folder_files(sources, folder_name, patterns):
            target = destination / folder_name / relative_path
            status = move_file(source, target)
            print(f"[Organizer] R5 {status}: {target}")
            moved.append(target)

    return moved


def remove_empty_source_folders(sources: list[Path]) -> None:
    """Remove empty R5 data/charts folders, but never remove the py folder."""
    for source_directory in sources:
        for folder_name in R5_FOLDER_PATTERNS:
            folder = source_directory / folder_name
            try:
                folder.rmdir()
            except (FileNotFoundError, OSError):
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move R3 and R5 outputs into the integrated project output folders"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Optional directory where unchanged R3/R5 code generated its files",
    )
    parser.add_argument(
        "--week",
        help="Output week such as vW29; default: current Singapore ISO week",
    )
    args = parser.parse_args()

    root = project_root()
    week = resolve_week_context(args.week)
    sources = source_directories(args.source_dir)
    weekly_output = root.parent / week.label
    r3_destination = weekly_output / "agents" / "almanac"
    r5_destination = weekly_output / "technical agent"

    r3_destination.mkdir(parents=True, exist_ok=True)
    r5_destination.mkdir(parents=True, exist_ok=True)

    print(f"[Organizer] Project root: {root}")
    print(f"[Organizer] Week folder: {week.label}")
    print("[Organizer] Searching:")
    for source in sources:
        print(f"[Organizer] - {source}")

    r3_files = move_r3_outputs(sources, r3_destination, week)
    r5_files = move_r5_outputs(sources, r5_destination, week)
    remove_empty_source_folders(sources)

    r3_available = bool(r3_files) or any(
        any(r3_destination.glob(pattern)) for pattern in R3_PATTERNS
    )
    r5_available = bool(r5_files) or any(
        any(r5_destination.glob(pattern)) for pattern in R5_ROOT_PATTERNS
    ) or any((r5_destination / folder).is_dir() for folder in R5_FOLDER_PATTERNS)

    print("")
    print(f"[Organizer] R3 files placed: {len(r3_files)}")
    print(f"[Organizer] R5 files placed: {len(r5_files)}")

    missing: list[str] = []
    if not r3_available:
        missing.append("No R3 output was found")
    if not r5_available:
        missing.append("No R5 output was found")

    if missing:
        for message in missing:
            print(f"[Organizer] WARNING: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
