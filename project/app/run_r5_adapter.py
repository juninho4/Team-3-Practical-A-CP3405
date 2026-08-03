#!/usr/bin/env python3
"""Compatibility runner for the unchanged R5 script.

The current yfinance release may return a MultiIndex even for one ticker.
R5 expects flat columns such as Close, EMA20 and EMA50. This adapter patches
yfinance.download at runtime, flattens the returned columns, replaces any
hard-coded WXX label in memory with the current pipeline week, and then
executes the original project/py/fetch_market_data.py without editing it.

Expected location:
    project/app/run_r5_adapter.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from week_context import resolve_week_context

try:
    import pandas as pd
    import yfinance as yf
except ImportError as exc:
    raise SystemExit(
        "R5 adapter requires pandas and yfinance. Run project/RUN_PROJECT.bat."
    ) from exc


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PY_DIR = PROJECT_ROOT / "py"
R5_SCRIPT = PY_DIR / "fetch_market_data.py"


def flatten_single_ticker_columns(frame: Any) -> Any:
    """Return yfinance data with ordinary Close/High/Low columns."""
    if not isinstance(frame, pd.DataFrame):
        return frame
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    level_zero = list(frame.columns.get_level_values(0))
    level_one = list(frame.columns.get_level_values(1))

    if "Close" in level_zero:
        flat_columns = level_zero
    elif "Close" in level_one:
        flat_columns = level_one
    else:
        raise RuntimeError(
            "R5 adapter received MultiIndex data but could not identify the price level"
        )

    result = frame.copy()
    result.columns = flat_columns
    return result


def adapt_source_week(source: str, runtime_week: str) -> str:
    """Replace WXX tokens only in the in-memory runtime copy of R5."""
    return re.sub(r"W\d{2}", runtime_week, source)


def main() -> int:
    if not R5_SCRIPT.is_file():
        print(f"R5 script was not found: {R5_SCRIPT}", file=sys.stderr)
        return 1

    original_download = yf.download

    def compatible_download(*args: Any, **kwargs: Any) -> Any:
        downloaded = original_download(*args, **kwargs)
        return flatten_single_ticker_columns(downloaded)

    yf.download = compatible_download

    week = resolve_week_context(os.environ.get("MARKET_WEEK_LABEL") or None)
    runtime_week = f"W{week.iso_week:02d}"

    print(f"[R5 Adapter] Original R5: {R5_SCRIPT}")
    print("[R5 Adapter] yfinance MultiIndex compatibility enabled.")
    print(
        f"[R5 Adapter] Runtime week: {runtime_week} "
        "(the original R5 source file remains unchanged)."
    )

    previous_directory = Path.cwd()
    previous_argv = sys.argv[:]
    try:
        os.chdir(PY_DIR)
        sys.argv = [str(R5_SCRIPT)]
        original_source = R5_SCRIPT.read_text(encoding="utf-8-sig")
        runtime_source = adapt_source_week(original_source, runtime_week)
        namespace = {
            "__name__": "__main__",
            "__file__": str(R5_SCRIPT),
            "__package__": None,
            "__cached__": None,
        }
        exec(compile(runtime_source, str(R5_SCRIPT), "exec"), namespace)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"[R5 Adapter] R5 failed: {exc}", file=sys.stderr)
        return 1
    finally:
        yf.download = original_download
        sys.argv = previous_argv
        os.chdir(previous_directory)

    print("[R5 Adapter] R5 completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
