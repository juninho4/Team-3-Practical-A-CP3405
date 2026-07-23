#!/usr/bin/env python3
"""Integrated project launcher.

Execution order:
    R6 screenshots/CSV -> R3 -> R4 -> R5 -> organize R3/R5 -> R8

R8 uses Groq, Gemini, and OpenRouter APIs by default.

This file belongs at:
    project/app/run_integrated_pipeline.py
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from week_context import WeekContext, resolve_week_context, singapore_today


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
PY_DIR = PROJECT_ROOT / "py"

R3_SCRIPT = PY_DIR / "r3_almanac_agent.py"
R4_SCRIPT = PY_DIR / "r4_macro_agent.py"
R5_SCRIPT = PY_DIR / "fetch_market_data.py"
R6_SCRIPT = PY_DIR / "r6_data_collector.py"
R8_SCRIPT = PY_DIR / "r8_llm_operator.py"
ORGANIZER_SCRIPT = APP_DIR / "organize_r3_r5_outputs.py"
R5_ADAPTER_SCRIPT = APP_DIR / "run_r5_adapter.py"
EXPECTED_PDF_NAME = "Stock Trader's Almanac 2026_L.pdf"

API_KEY_NAMES = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class PipelineError(RuntimeError):
    pass


def heading(step: int, total: int, title: str) -> None:
    print("")
    print("=" * 76)
    print(f"[{step}/{total}] {title}")
    print("=" * 76)


def verify_files() -> None:
    required = [
        R3_SCRIPT,
        R4_SCRIPT,
        R5_SCRIPT,
        R6_SCRIPT,
        R8_SCRIPT,
        ORGANIZER_SCRIPT,
        R5_ADAPTER_SCRIPT,
        PROJECT_ROOT / "information" / EXPECTED_PDF_NAME,
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        details = "\n".join(f"- {path}" for path in missing)
        raise PipelineError(f"Required project files are missing:\n{details}")


def load_project_env() -> Path:
    """Load project/.env without replacing variables set in Windows."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return env_path
    for raw_line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if value and value[0:1] == value[-1:] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name and name not in os.environ:
            os.environ[name] = value
    return env_path


def verify_api_configuration(only: str) -> None:
    env_path = load_project_env()
    enabled = API_KEY_NAMES if only == "all" else {only: API_KEY_NAMES[only]}
    configured = [
        model for model, key_name in enabled.items() if os.environ.get(key_name, "").strip()
    ]
    required = len(enabled)
    if len(configured) >= required:
        print(f"R8 API preflight: {len(configured)} configured provider(s) found.")
        return

    missing_names = [
        key_name for key_name in enabled.values() if not os.environ.get(key_name, "").strip()
    ]
    template = PROJECT_ROOT / ".env.example"
    raise PipelineError(
        f"R8 API mode needs at least {required} configured API key(s), but found "
        f"{len(configured)}. Copy {template} to {env_path}, fill in the keys, and "
        f"run again. Missing variables: {', '.join(missing_names)}"
    )


def run_python(script: Path, arguments: list[str] | None = None) -> None:
    command = [sys.executable, str(script), *(arguments or [])]
    print("Command:", " ".join(f'"{part}"' if " " in part else part for part in command))
    completed = subprocess.run(command, cwd=PY_DIR, check=False)
    if completed.returncode != 0:
        raise PipelineError(
            f"{script.name} failed with exit code {completed.returncode}"
        )


def r6_week_arguments(week: WeekContext) -> list[str]:
    """Use one sprint week for R6 labels and cap data at that week's Sunday."""
    week_end = week.monday + timedelta(days=6)
    as_of = min(week_end, singapore_today())
    return [
        "--as-of",
        as_of.isoformat(),
        "--week",
        f"{week.iso_year}-W{week.iso_week:02d}",
    ]


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def find_edge() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def ensure_edge_debugging() -> None:
    if port_open("127.0.0.1", 9222):
        print("Edge remote-debugging session already available on port 9222.")
        return

    if os.name != "nt":
        raise PipelineError(
            "R8 browser mode requires Microsoft Edge on Windows at port 9222."
        )

    edge = find_edge()
    if edge is None:
        raise PipelineError("Microsoft Edge executable was not found")

    profile = APP_DIR / "edge_profile"
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        str(edge),
        "--remote-debugging-port=9222",
        f"--user-data-dir={profile}",
        "--start-maximized",
        "https://chatgpt.com/",
    ]
    subprocess.Popen(command, cwd=PROJECT_ROOT)
    print("Started a dedicated Edge profile for R8. Log in when requested.")

    deadline = time.time() + 30
    while time.time() < deadline:
        if port_open("127.0.0.1", 9222):
            return
        time.sleep(1)
    raise PipelineError("Edge started, but remote-debugging port 9222 did not open")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete market pipeline")
    parser.add_argument(
        "--week",
        help="Optional results week such as vW29; default: current Singapore ISO week",
    )
    parser.add_argument(
        "--headless-r6",
        action="store_true",
        help=(
            "Hide the optional R6 webpage browser; only used together with "
            "--r6-web-screenshots."
        ),
    )
    parser.add_argument(
        "--r6-web-screenshots",
        action="store_true",
        help="Also capture the legacy Finviz/Yahoo webpages (not used by default)",
    )
    parser.add_argument(
        "--r8-only",
        choices=["all", "groq", "gemini", "openrouter"],
        default="all",
        help="AI provider used by R8 (default: all three)",
    )
    parser.add_argument(
        "--r8-mode",
        choices=["api"],
        default="api",
        help="Use model APIs",
    )
    args = parser.parse_args()

    try:
        verify_files()
        week = resolve_week_context(args.week)
        week_output = REPOSITORY_ROOT / week.label
        week_output.mkdir(parents=True, exist_ok=True)
        os.environ["MARKET_WEEK_LABEL"] = week.label

        print(f"Pipeline week: {week.label} (ISO {week.iso_year}-W{week.iso_week:02d})")
        print(f"Weekly results folder: {week_output}")
        total = 6

        heading(1, total, "R6 — generate CSV and hidden-browser evidence screenshots")
        r6_arguments: list[str] = [
            *r6_week_arguments(week),
            "--out",
            str(week_output / "evidence"),
        ]
        if args.r6_web_screenshots:
            r6_arguments.append("--web-screenshots")
            if args.headless_r6:
                r6_arguments.append("--headless")
        run_python(R6_SCRIPT, r6_arguments)

        heading(2, total, "R3 — generate weekly Almanac evidence")
        run_python(
            R3_SCRIPT,
            [
                "--week-start",
                week.monday.isoformat(),
                "--week-label",
                week.label,
                "--pdf",
                str(PROJECT_ROOT / "information" / EXPECTED_PDF_NAME),
                "--output-dir",
                str(week_output / "agents" / "almanac"),
            ],
        )

        heading(3, total, "R4 — generate macro evidence")
        run_python(
            R4_SCRIPT,
            [
                "--week-start",
                week.monday.isoformat(),
                "--output-dir",
                str(week_output / "agents"),
            ],
        )

        heading(4, total, "R5 — generate technical data and charts")
        run_python(R5_ADAPTER_SCRIPT)

        heading(5, total, "Organize R5 outputs and verify R3 evidence")
        run_python(ORGANIZER_SCRIPT, ["--week", week.label])

        heading(6, total, "R8 — synthesize R3/R4/R5 with Groq, Gemini, and OpenRouter")
        verify_api_configuration(args.r8_only)
        run_python(
            R8_SCRIPT,
            [
                "--sprint",
                week.label,
                "--mode",
                args.r8_mode,
                "--only",
                args.r8_only,
                "--min-api-success",
                "3" if args.r8_only == "all" else "1",
                "--no-pause",
            ],
        )

    except (PipelineError, OSError, subprocess.SubprocessError) as exc:
        print("")
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        return 1

    print("")
    print("=" * 76)
    print("PIPELINE COMPLETED")
    print(f"Results folder: {week_output}")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
