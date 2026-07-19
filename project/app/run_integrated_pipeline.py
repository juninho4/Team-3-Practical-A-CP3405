#!/usr/bin/env python3
"""Integrated project launcher.

Execution order:
    R6 screenshots/CSV -> R3 -> R4 -> R5 -> organize R3/R5 -> R8

R8 uses the Gemini API by default. Other providers remain available only when
explicitly selected from the command line.

This file belongs at:
    project/app/run_integrated_pipeline.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PY_DIR = PROJECT_ROOT / "py"

R3_NOTEBOOK = PY_DIR / "R3 Almanac System.ipynb"
R4_SCRIPT = PY_DIR / "r4_macro_agent.py"
R5_SCRIPT = PY_DIR / "fetch_market_data.py"
R6_SCRIPT = PY_DIR / "r6_data_collector.py"
R8_SCRIPT = PY_DIR / "r8_llm_operator.py"
ORGANIZER_SCRIPT = APP_DIR / "organize_r3_r5_outputs.py"
R5_ADAPTER_SCRIPT = APP_DIR / "run_r5_adapter.py"
R3_PDF_MANAGER = APP_DIR / "manage_r3_pdf.py"

EXPECTED_PDF_NAME = "Stock Trader's Almanac 2026_L.pdf"

API_KEY_NAMES = {
    "chatgpt": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
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
        R3_NOTEBOOK,
        R4_SCRIPT,
        R5_SCRIPT,
        R6_SCRIPT,
        R8_SCRIPT,
        ORGANIZER_SCRIPT,
        R5_ADAPTER_SCRIPT,
        R3_PDF_MANAGER,
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
    required = 2 if only == "all" else 1
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


def find_almanac_pdf() -> Path:
    exact = PY_DIR / EXPECTED_PDF_NAME
    if exact.is_file():
        return exact

    candidates: list[Path] = []
    for directory in [PY_DIR, PROJECT_ROOT]:
        candidates.extend(
            path
            for path in directory.glob("Stock Trader's Almanac 2026_L*.pdf")
            if path.is_file()
        )
    if not candidates:
        raise PipelineError(
            "R3 PDF was not found. Put Stock Trader's Almanac 2026_L(1).pdf "
            "or Stock Trader's Almanac 2026_L.pdf in project/py/."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def run_r3_notebook() -> None:
    """Execute an in-memory adapted copy; never rewrite the original notebook."""
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError as exc:
        raise PipelineError(
            "R3 runner needs nbformat and nbclient. Run the root BAT file so "
            "requirements are installed."
        ) from exc

    source_pdf = find_almanac_pdf()
    expected_pdf = PY_DIR / EXPECTED_PDF_NAME
    temporary_pdf_alias = source_pdf.resolve() != expected_pdf.resolve()

    if temporary_pdf_alias:
        shutil.copy2(source_pdf, expected_pdf)
        print(f"Temporary R3 PDF alias: {expected_pdf.name}")

    try:
        with R3_NOTEBOOK.open("r", encoding="utf-8") as handle:
            notebook = nbformat.read(handle, as_version=4)

        injection_index: int | None = None
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue
            source = str(cell.source)
            if "def find_line(keyword)" in source:
                injection_index = index
                # The original contains an accidental trailing plus. Fix only
                # this in-memory runtime copy; the original file stays unchanged.
                cell.source = source.replace(
                    'print("Average Return:", avg_return)+\n',
                    'print("Average Return:", avg_return)\n',
                )
                break

        if injection_index is None:
            raise PipelineError("Could not find the R3 extraction cell")

        notebook.cells.insert(
            injection_index,
            nbformat.v4.new_code_cell(
                "# Added by the external launcher; original notebook is unchanged.\n"
                "lines = [line.strip() for line in text.splitlines() if line.strip()]"
            ),
        )

        client = NotebookClient(
            notebook,
            timeout=300,
            kernel_name="python3",
            resources={"metadata": {"path": str(PY_DIR)}},
            allow_errors=False,
        )
        try:
            client.execute()
        except Exception as exc:
            raise PipelineError(f"R3 notebook execution failed: {exc}") from exc
        print("R3 notebook completed. Original notebook was not modified.")
    finally:
        if temporary_pdf_alias:
            try:
                expected_pdf.unlink()
            except FileNotFoundError:
                pass


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
        choices=["all", "chatgpt", "deepseek", "gemini", "claude"],
        default="gemini",
        help="AI provider used by R8 (default: Gemini only)",
    )
    parser.add_argument(
        "--r8-mode",
        choices=["api", "browser"],
        default="api",
        help="Use model APIs (default) or the legacy Edge browser workflow",
    )
    args = parser.parse_args()

    try:
        verify_files()
        total = 6

        heading(1, total, "R6 — generate CSV and hidden-browser evidence screenshots")
        r6_arguments: list[str] = []
        if args.r6_web_screenshots:
            r6_arguments.append("--web-screenshots")
            if args.headless_r6:
                r6_arguments.append("--headless")
        run_python(R6_SCRIPT, r6_arguments)

        heading(2, total, "R3 — run Almanac notebook")
        run_python(R3_PDF_MANAGER, ["prepare"])
        try:
            run_r3_notebook()
        finally:
            # Cleanup runs even if the notebook raises an exception.
            run_python(R3_PDF_MANAGER, ["cleanup"])

        heading(3, total, "R4 — generate macro evidence")
        run_python(R4_SCRIPT)

        heading(4, total, "R5 — generate technical data and charts")
        run_python(R5_ADAPTER_SCRIPT)

        heading(5, total, "Organize unchanged R3 and R5 outputs")
        run_python(ORGANIZER_SCRIPT)

        heading(6, total, "R8 — synthesize R3/R4/R5 with Gemini")
        if args.r8_mode == "api":
            verify_api_configuration(args.r8_only)
        if args.r8_mode == "browser":
            ensure_edge_debugging()
        run_python(
            R8_SCRIPT,
            [
                "--sprint",
                "Current Week",
                "--mode",
                args.r8_mode,
                "--only",
                args.r8_only,
                "--min-api-success",
                "1",
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
    print(f"Output folder: {PROJECT_ROOT / 'output'}")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
