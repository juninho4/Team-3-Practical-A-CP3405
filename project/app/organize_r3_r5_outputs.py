#!/usr/bin/env python3
"""Move unchanged R3 and R5 outputs into the integrated project layout.

Expected final location of this script:
    project/app/organize_r3_r5_outputs.py

Expected unchanged agent code location:
    project/py/R3 Almanac System.ipynb
    project/py/fetch_market_data.py

Final output layout:
    project/output/agents/almanac/       R3 files
    project/output/technical agent/      R5 files

Normal run:
    python organize_r3_r5_outputs.py

Optional source override:
    python organize_r3_r5_outputs.py --source-dir C:/path/to/project/py
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


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
        if (parent / "py").is_dir() and (parent / "output").is_dir():
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


def move_r3_outputs(sources: list[Path], destination: Path) -> list[Path]:
    moved: list[Path] = []
    for source in find_root_files(sources, R3_PATTERNS):
        target = destination / source.name
        status = move_file(source, target)
        print(f"[Organizer] R3 {status}: {target}")
        moved.append(target)
    return moved


def move_r5_outputs(sources: list[Path], destination: Path) -> list[Path]:
    moved: list[Path] = []

    for source in find_root_files(sources, R5_ROOT_PATTERNS):
        target = destination / source.name
        status = move_file(source, target)
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
    args = parser.parse_args()

    root = project_root()
    sources = source_directories(args.source_dir)
    r3_destination = root / "output" / "agents" / "almanac"
    r5_destination = root / "output" / "technical agent"

    r3_destination.mkdir(parents=True, exist_ok=True)
    r5_destination.mkdir(parents=True, exist_ok=True)

    print(f"[Organizer] Project root: {root}")
    print("[Organizer] Searching:")
    for source in sources:
        print(f"[Organizer] - {source}")

    r3_files = move_r3_outputs(sources, r3_destination)
    r5_files = move_r5_outputs(sources, r5_destination)
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
