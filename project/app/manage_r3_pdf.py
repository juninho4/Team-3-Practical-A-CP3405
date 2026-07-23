#!/usr/bin/env python3
"""Prepare and clean up R3's temporary Almanac PDF dependency.

Permanent source location:
    project/information/Stock Trader's Almanac 2026_L*.pdf

Temporary R3 location:
    project/py/Stock Trader's Almanac 2026_L.pdf
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
INFORMATION_DIR = PROJECT_ROOT / "information"
PY_DIR = PROJECT_ROOT / "py"
EXPECTED_PDF_NAME = "Stock Trader's Almanac 2026_L.pdf"
TARGET_PDF = PY_DIR / EXPECTED_PDF_NAME
STATE_FILE = APP_DIR / ".r3_pdf_copy_state.json"


class R3PDFError(RuntimeError):
    pass


def find_source_pdf() -> Path:
    if not INFORMATION_DIR.is_dir():
        raise R3PDFError(
            f"R3 information folder does not exist: {INFORMATION_DIR}"
        )

    exact = INFORMATION_DIR / EXPECTED_PDF_NAME
    if exact.is_file():
        return exact

    candidates = [
        path
        for path in INFORMATION_DIR.glob("Stock Trader's Almanac 2026_L*.pdf")
        if path.is_file()
    ]
    if not candidates:
        raise R3PDFError(
            "R3 PDF was not found. Put Stock Trader's Almanac 2026_L(1).pdf "
            f"or {EXPECTED_PDF_NAME} in {INFORMATION_DIR}."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def prepare() -> None:
    source = find_source_pdf()
    PY_DIR.mkdir(parents=True, exist_ok=True)
    temporary = TARGET_PDF.with_suffix(TARGET_PDF.suffix + ".copying")

    if temporary.exists():
        temporary.unlink()

    try:
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source.stat().st_size:
            raise R3PDFError("The copied R3 PDF size does not match the source")
        temporary.replace(TARGET_PDF)
    finally:
        if temporary.exists():
            temporary.unlink()

    state = {
        "source": str(source.resolve()),
        "target": str(TARGET_PDF.resolve()),
        "size_bytes": TARGET_PDF.stat().st_size,
        "prepared_at": datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
    }
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[R3 PDF] Source preserved: {source}")
    print(f"[R3 PDF] Temporary copy prepared: {TARGET_PDF}")


def cleanup() -> None:
    if TARGET_PDF.is_file():
        TARGET_PDF.unlink()
        print(f"[R3 PDF] Temporary copy deleted: {TARGET_PDF}")
    else:
        print(f"[R3 PDF] No temporary copy to delete: {TARGET_PDF}")

    if STATE_FILE.is_file():
        STATE_FILE.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy or remove R3's temporary Almanac PDF dependency"
    )
    parser.add_argument("action", choices=["prepare", "cleanup"])
    args = parser.parse_args()

    try:
        if args.action == "prepare":
            prepare()
        else:
            cleanup()
    except (R3PDFError, OSError) as exc:
        print(f"[R3 PDF] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
