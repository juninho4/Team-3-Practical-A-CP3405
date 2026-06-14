#!/usr/bin/env python3
"""
R8 Evidence Screenshot Tool - v6 No TradingEconomics

Outputs only:
1. evidence/finviz_closing_prices_2026-W24.png
2. evidence/finviz_1W_2026-W24.png
3. evidence/sectors/yahoo_sectors_5D_2026-W24_*.png

TradingEconomics Calendar is removed.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright, TimeoutError as PlaywrightTimeoutError


WEEK = "2026-W24"

FINVIZ_PRICES_1W = "https://finviz.com/futures?p=w"
FINVIZ_PERFORMANCE_1W = "https://finviz.com/futures_performance?v=12"


@dataclass(frozen=True)
class Sector:
    name: str
    filename: str
    url: str


SECTORS = [
    Sector("Technology", "Technology", "https://finance.yahoo.com/sectors/technology/"),
    Sector("Communication Services", "Communication_Services", "https://finance.yahoo.com/sectors/communication-services/"),
    Sector("Consumer Cyclical", "Consumer_Cyclical", "https://finance.yahoo.com/sectors/consumer-cyclical/"),
    Sector("Consumer Defensive", "Consumer_Defensive", "https://finance.yahoo.com/sectors/consumer-defensive/"),
    Sector("Energy", "Energy", "https://finance.yahoo.com/sectors/energy/"),
    Sector("Financial Services", "Financial_Services", "https://finance.yahoo.com/sectors/financial-services/"),
    Sector("Healthcare", "Healthcare", "https://finance.yahoo.com/sectors/healthcare/"),
    Sector("Industrials", "Industrials", "https://finance.yahoo.com/sectors/industrials/"),
    Sector("Basic Materials", "Basic_Materials", "https://finance.yahoo.com/sectors/basic-materials/"),
    Sector("Real Estate", "Real_Estate", "https://finance.yahoo.com/sectors/real-estate/"),
    Sector("Utilities", "Utilities", "https://finance.yahoo.com/sectors/utilities/"),
]


def new_page(context: BrowserContext) -> Page:
    return context.new_page()


def goto(page: Page, url: str, wait_ms: int = 6000) -> None:
    print(f"[R8] Opening: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=70000)
    except PlaywrightTimeoutError:
        print("[R8] Timeout, continuing.")
    page.wait_for_timeout(wait_ms)
    close_popups(page)
    page.wait_for_timeout(1000)


def close_popups(page: Page) -> None:
    for sel in [
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('Reject all')",
        "button:has-text('Reject All')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('Continue')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "[aria-label='Close']",
        "[title='Close']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=400):
                loc.click(timeout=2000)
                page.wait_for_timeout(800)
                return
        except Exception:
            pass


def scroll_top(page: Page) -> None:
    try:
        page.keyboard.press("Home")
        page.evaluate(
            """
            () => {
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
                for (const el of document.querySelectorAll('*')) {
                    try { el.scrollTop = 0; } catch(e) {}
                }
            }
            """
        )
        page.wait_for_timeout(800)
    except Exception:
        pass


def save_viewport(page: Page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    page.screenshot(path=str(path), full_page=False)
    print(f"[R8] Saved: {path}")


def add_time_tag(page: Page, label: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe = label.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    page.evaluate(
        f"""
        () => {{
            const old = document.getElementById('r8-time-tag');
            if (old) old.remove();

            const tag = document.createElement('div');
            tag.id = 'r8-time-tag';
            tag.textContent = 'R8 captured: {now} | {safe}';
            tag.style.position = 'fixed';
            tag.style.left = '10px';
            tag.style.bottom = '10px';
            tag.style.zIndex = '2147483647';
            tag.style.background = 'rgba(255,255,255,0.92)';
            tag.style.color = '#111';
            tag.style.border = '1px solid #333';
            tag.style.padding = '4px 7px';
            tag.style.borderRadius = '4px';
            tag.style.fontFamily = 'Arial, sans-serif';
            tag.style.fontSize = '11px';
            tag.style.fontWeight = '600';
            document.body.appendChild(tag);
        }}
        """
    )


def click_yahoo_5d(page: Page) -> None:
    clicked = False
    try:
        pattern = re.compile(r"^\s*5D\s*$", re.I)
        for tag in ["button", "a", "span"]:
            locs = page.locator(tag).filter(has_text=pattern)
            count = min(locs.count(), 20)
            for i in range(count):
                loc = locs.nth(i)
                if loc.is_visible(timeout=400):
                    loc.click(timeout=2500)
                    clicked = True
                    break
            if clicked:
                break
    except Exception:
        clicked = False

    if not clicked:
        page.mouse.click(306, 392)

    page.wait_for_timeout(2500)


def capture_finviz_prices(context: BrowserContext, week: str, out: Path) -> None:
    page = new_page(context)
    try:
        goto(page, FINVIZ_PRICES_1W)
        scroll_top(page)
        save_viewport(page, out / f"finviz_closing_prices_{week}.png")
    finally:
        page.close()


def capture_finviz_performance(context: BrowserContext, week: str, out: Path) -> None:
    page = new_page(context)
    try:
        goto(page, FINVIZ_PERFORMANCE_1W)

        try:
            page.locator("text=1 Week Performance").first.scroll_into_view_if_needed(timeout=2500)
            page.wait_for_timeout(600)
            page.evaluate("window.scrollBy(0, -140)")
            page.wait_for_timeout(600)
        except Exception:
            try:
                page.locator("text=1 WEEK PERFORMANCE").first.scroll_into_view_if_needed(timeout=2500)
                page.wait_for_timeout(600)
                page.evaluate("window.scrollBy(0, -140)")
                page.wait_for_timeout(600)
            except Exception:
                scroll_top(page)

        save_viewport(page, out / f"finviz_1W_{week}.png")
    finally:
        page.close()


def capture_yahoo(context: BrowserContext, week: str, out: Path) -> None:
    sectors_dir = out / "sectors"
    sectors_dir.mkdir(parents=True, exist_ok=True)

    for sector in SECTORS:
        page = new_page(context)
        try:
            goto(page, sector.url, wait_ms=7000)
            scroll_top(page)
            click_yahoo_5d(page)
            scroll_top(page)
            add_time_tag(page, f"Yahoo Finance {sector.name} 5D")
            save_viewport(page, sectors_dir / f"yahoo_sectors_5D_{week}_{sector.filename}.png")
        finally:
            page.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default=WEEK)
    parser.add_argument("--out", default="evidence")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, slow_mo=100 if not args.headless else 0)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="en-US",
            timezone_id="Asia/Singapore",
        )

        try:
            capture_finviz_prices(context, args.week, out)
            capture_finviz_performance(context, args.week, out)
            capture_yahoo(context, args.week, out)

            print("")
            print("[R8] DONE")
            print(f"[R8] Output folder: {out.resolve()}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
