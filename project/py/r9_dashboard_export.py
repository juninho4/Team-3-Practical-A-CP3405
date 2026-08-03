#!/usr/bin/env python3
"""Export the current weekly market output to a GitHub Pages JSON file.

The exporter does not call any external API. It reads the exact week folder
selected by the integrated launcher and writes docs/data/latest_prediction.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SINGAPORE_TIME = timezone(timedelta(hours=8))
WEEK_PATTERN = re.compile(r"^(?:v)?W(\d{1,2})$", re.IGNORECASE)
PROVIDERS = ("groq", "gemini", "openrouter")
DISPLAY_NAMES = {
    "groq": "Groq",
    "gemini": "Gemini",
    "openrouter": "OpenRouter",
}


def project_root() -> Path:
    script = Path(__file__).resolve()
    return script.parent.parent if script.parent.name.lower() in {"py", "app"} else script.parent


def normalize_week(value: str) -> str:
    match = WEEK_PATTERN.fullmatch(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError("Use a week label such as vW31 or W31")
    week = int(match.group(1))
    if not 1 <= week <= 53:
        raise argparse.ArgumentTypeError("ISO week must be between 1 and 53")
    return f"vW{week:02d}"


def current_week() -> str:
    iso = datetime.now(SINGAPORE_TIME).date().isocalendar()
    return f"vW{iso.week:02d}"


def resolve_week_dir(repo: Path, week: str, requested: str) -> Path:
    label = normalize_week(week)
    raw = (requested or os.environ.get("MARKET_WEEK_OUTPUT_DIR", "")).strip()
    candidate = Path(raw).expanduser() if raw else repo / label
    if not candidate.is_absolute():
        candidate = repo / candidate
    candidate = candidate.resolve()
    if candidate.name.casefold() != label.casefold():
        raise RuntimeError(
            "Dashboard week directory does not match week label: "
            f"week={label}, directory={candidate}"
        )
    return candidate


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def compact(text: str, limit: int = 360) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" -|#\t\r\n")
    if not cleaned:
        return "No summary available."
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    return text


def markdown_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def markdown_preview(path: Path, preferred_terms: tuple[str, ...]) -> str:
    text = read_text(path)
    if not text:
        return "No output file was found."

    plain = strip_markdown(text)
    lines = []
    for raw in plain.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or set(line) <= {"-", ":", "|", " "}:
            continue
        if line.startswith("#"):
            continue
        lines.append(line.lstrip("-*0123456789. "))

    preferred = [
        line for line in lines
        if any(term.casefold() in line.casefold() for term in preferred_terms)
    ]
    selected = preferred[:2] if preferred else lines[:3]
    return compact(" ".join(selected))


def newest_file(folder: Path, patterns: tuple[str, ...]) -> Path | None:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in folder.glob(pattern) if path.is_file())
    if not found:
        return None
    return max(found, key=lambda path: (path.stat().st_mtime_ns, path.name))


def parse_llm_report(report: str) -> tuple[str, str, dict[str, dict[str, str]], str]:
    regime = "Uncertain"
    confidence = "Unknown"
    predictions = {
        symbol: {"direction": "Unavailable", "range": "Unavailable"}
        for symbol in ("SPX", "NDX", "IWM")
    }

    synthesis = markdown_section(report, "R8 Synthesis Summary")
    match = re.search(
        r"overall\s+AI\s+view\s+is\s+\*\*(.+?)\*\*\s+with\s+\*\*(.+?)\*\*\s+confidence",
        synthesis,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        regime = compact(strip_markdown(match.group(1)), 80)
        confidence = compact(strip_markdown(match.group(2)), 80)

    recommendation = markdown_section(report, "R8 Recommendation to R7")
    for symbol in predictions:
        direction_match = re.search(
            rf"^\s*\d+\.\s*{symbol}\s*:\s*(.+?)\s*$",
            recommendation,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        range_match = re.search(
            rf"^\s*-\s*{symbol}\s*:\s*(.+?)\s*$",
            recommendation,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if direction_match:
            predictions[symbol]["direction"] = compact(strip_markdown(direction_match.group(1)), 100)
        if range_match:
            predictions[symbol]["range"] = compact(strip_markdown(range_match.group(1)), 100)

    if synthesis:
        summary = compact(strip_markdown(synthesis), 520)
    elif report:
        summary = compact(strip_markdown(report), 520)
    else:
        summary = "R8 comparison report was not produced."

    return regime, confidence, predictions, summary


def parse_api_log(log_text: str, llm_dir: Path) -> dict[str, dict[str, str]]:
    models = {
        key: {
            "name": DISPLAY_NAMES[key],
            "model": "Unknown",
            "status": "success" if (llm_dir / f"synthesis_{key}.txt").is_file() else "unavailable",
            "error_code": "",
            "detail": "",
        }
        for key in PROVIDERS
    }

    for line in log_text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0].casefold() in {"provider", "---"}:
            continue
        provider_name, model, status, code, detail, _output = cells[:6]
        key = next(
            (candidate for candidate, display in DISPLAY_NAMES.items()
             if display.casefold() in provider_name.casefold()
             or candidate.casefold() in provider_name.casefold()),
            None,
        )
        if key is None:
            continue
        normalized_status = {
            "ok": "success",
            "failed": "failed",
            "skipped": "skipped",
        }.get(status.casefold(), status.casefold() or "unavailable")
        models[key] = {
            "name": DISPLAY_NAMES[key],
            "model": model or "Unknown",
            "status": normalized_status,
            "error_code": "" if code == "-" else code,
            "detail": "" if detail == "-" else compact(detail, 220),
        }

    return models


def technical_summary(folder: Path) -> tuple[str, list[str]]:
    files = sorted(path for path in folder.rglob("*.csv") if path.is_file()) if folder.is_dir() else []
    counts: Counter[str] = Counter()
    rows = 0
    for path in files:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows += 1
                    bias = (row.get("Technical Bias") or row.get("Bias") or "Unknown").strip()
                    if bias:
                        counts[bias] += 1
        except (OSError, csv.Error):
            continue

    if not files:
        return "No R5 technical CSV file was found.", []
    mix = ", ".join(f"{name}: {count}" for name, count in counts.most_common(5))
    summary = f"R5 produced {len(files)} CSV file(s) with {rows} data row(s)."
    if mix:
        summary += f" Technical bias mix: {mix}."
    return compact(summary), [path.name for path in files]


def relative(path: Path | None, repo: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export latest market dashboard JSON")
    parser.add_argument(
        "--week",
        type=normalize_week,
        default=os.environ.get("MARKET_WEEK_LABEL", current_week()),
    )
    parser.add_argument(
        "--week-output-dir",
        default=os.environ.get("MARKET_WEEK_OUTPUT_DIR", ""),
        help="Exact week folder selected by the integrated pipeline",
    )
    parser.add_argument("--docs-dir", default="")
    args = parser.parse_args()

    project = project_root()
    repo = project.parent.resolve()
    week = normalize_week(args.week)
    week_dir = resolve_week_dir(repo, week, args.week_output_dir)
    docs_dir = Path(args.docs_dir).expanduser() if args.docs_dir else repo / "docs"
    if not docs_dir.is_absolute():
        docs_dir = repo / docs_dir
    docs_dir = docs_dir.resolve()

    llm_dir = week_dir / "llm"
    report_path = llm_dir / "llm_comparison.md"
    api_log_path = llm_dir / "api_call_log.md"
    report_text = read_text(report_path)
    api_log_text = read_text(api_log_path)

    regime, confidence, predictions, r8_summary = parse_llm_report(report_text)
    models = parse_api_log(api_log_text, llm_dir)
    success_count = sum(model["status"] == "success" for model in models.values())

    r3_path = newest_file(week_dir / "agents" / "almanac", ("*.md",))
    r4_path = newest_file(week_dir / "agents", ("macro_agent_output*.md", "*macro*.md"))
    r5_summary, r5_files = technical_summary(week_dir / "technical agent")

    r3_summary = (
        markdown_preview(r3_path, ("verdict", "outlook", "seasonal", "summary"))
        if r3_path else "No R3 Almanac output file was found."
    )
    r4_summary = (
        markdown_preview(r4_path, ("regime", "macro", "risk", "summary", "outlook"))
        if r4_path else "No R4 macro output file was found."
    )

    status = (
        f"Completed with {success_count}/3 AI providers"
        if report_path.is_file()
        else f"Partial output with {success_count}/3 AI providers"
    )

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    branch = os.environ.get("GITHUB_REF_NAME", "main").strip() or "main"
    repo_url = f"{server}/{repository}" if repository else ""
    source_url = f"{repo_url}/tree/{branch}/{week}" if repo_url else ""

    payload: dict[str, Any] = {
        "week": week,
        "generated_at": datetime.now(SINGAPORE_TIME).isoformat(timespec="seconds"),
        "pipeline_status": status,
        "regime": regime,
        "confidence": confidence,
        "predictions": predictions,
        "models": models,
        "summaries": {
            "r3": r3_summary,
            "r4": r4_summary,
            "r5": r5_summary,
            "r8": r8_summary,
        },
        "evidence": {
            "r3_file": relative(r3_path, repo),
            "r4_file": relative(r4_path, repo),
            "r5_files": r5_files,
            "llm_comparison": relative(report_path if report_path.is_file() else None, repo),
            "api_call_log": relative(api_log_path if api_log_path.is_file() else None, repo),
        },
        "source_url": source_url,
    }

    output = docs_dir / "data" / "latest_prediction.json"
    atomic_write_json(output, payload)
    print(f"[Dashboard] Week source: {week_dir}")
    print(f"[Dashboard] JSON generated: {output}")
    print(f"[Dashboard] AI providers successful: {success_count}/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
