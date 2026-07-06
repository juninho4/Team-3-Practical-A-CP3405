#!/usr/bin/env python3
"""
R6 Integrated One-Click Workflow - Generic Weekly Version

Folder structure:
- RUN_R6_ONE_CLICK_W24.bat                    root shortcut
- app/                                       program files
- input/                                     3 input evidence files
- output/Q/                                  generated shared prompt
- output/llm_raw_responses/                  raw AI responses
- output/llm/                                final comparison report

One run:
1. Read three input evidence files from input/
2. Generate output/Q/shared_prompt.md
3. Open Edge and ask ChatGPT / DeepSeek / Gemini / Claude
4. Save raw AI answers into output/llm_raw_responses/
5. Generate output/llm/llm_comparison.md

No file upload:
- The script pastes prompt content into each AI site.

Claude only:
- Appends this final line:
  一次性回答每个问题，纯文字，英文
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from ctypes import wintypes
from typing import Optional

from playwright.sync_api import BrowserContext, Page, sync_playwright


CLAUDE_EXTRA_INSTRUCTION = "一次性回答每个问题，纯文字，英文"

MODELS = ["chatgpt", "claude", "gemini", "deepseek"]
DISPLAY = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
}


@dataclass(frozen=True)
class AISite:
    key: str
    name: str
    url: str
    output_filename: str


AI_SITES = [
    AISite("chatgpt", "ChatGPT", "https://chatgpt.com/", "synthesis_chatgpt.txt"),
    AISite("deepseek", "DeepSeek", "https://chat.deepseek.com/", "synthesis_deepseek.txt"),
    AISite("gemini", "Gemini", "https://gemini.google.com/app", "synthesis_gemini.txt"),
    AISite("claude", "Claude", "https://claude.ai/new", "synthesis_claude.txt"),
]


INPUT_SELECTORS = [
    "textarea",
    "div[contenteditable='true']",
    "[role='textbox']",
    "div.ProseMirror",
]

SEND_SELECTORS = [
    "button[data-testid='send-button']",
    "button[aria-label*='Send']",
    "button[aria-label*='send']",
    "button:has-text('Send')",
    "button:has-text('发送')",
    "button[type='submit']",
]


@dataclass
class ModelResult:
    model_key: str
    model_name: str
    raw_text: str
    weekly_regime: str = "Not found"
    confidence: str = "Not found"
    spx_range: str = "Not found"
    ndx_range: str = "Not found"
    iwm_range: str = "Not found"
    spx_direction: str = "Not found"
    ndx_direction: str = "Not found"
    iwm_direction: str = "Not found"
    supporting: str = "Not found"
    contradictions: str = "Not found"
    invalidation: str = "Not found"
    plain_english: str = "Not found"


def project_root_from_app() -> Path:
    """
    app/r6_integrated_one_click.py -> project root is parent of app/.
    """
    script_path = Path(__file__).resolve()
    if script_path.parent.name.lower() == "app":
        return script_path.parent.parent
    return script_path.parent


def ensure_dirs(root: Path) -> None:
    folders = [
        root / "input",
        root / "output" / "Q",
        root / "output" / "llm_raw_responses",
        root / "output" / "llm",
        root / "app",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def input_file_candidates(root: Path, sprint: str) -> dict[str, list[Path]]:
    inp = root / "input"
    return {
        "r3": [
            inp / "r3_almanac.md",
            inp / "almanac.md",
            inp / f"r3_almanac_{sprint}.md",
            inp / f"almanac_{sprint}.md",
        ],
        "r4": [
            inp / "r4_macro_news.md",
            inp / "macro_news.md",
            inp / f"r4_macro_news_{sprint}.md",
            inp / f"macro_news_{sprint}.md",
        ],
        "r5": [
            inp / "r5_technical.md",
            inp / "technical.md",
            inp / f"r5_technical_{sprint}.md",
            inp / f"technical_{sprint}.md",
        ],
    }


def find_input_file(root: Path, sprint: str, key: str) -> Optional[Path]:
    inp = root / "input"
    candidates = input_file_candidates(root, sprint)[key]

    for path in candidates:
        if path.exists():
            return path

    # Flexible fallback.
    patterns = {
        "r3": ["*r3*.md", "*almanac*.md", "*R3*.md", "*Almanac*.md"],
        "r4": ["*r4*.md", "*macro*.md", "*news*.md", "*R4*.md", "*Macro*.md", "*News*.md"],
        "r5": ["*r5*.md", "*technical*.md", "*tech*.md", "*R5*.md", "*Technical*.md"],
    }

    for pattern in patterns[key]:
        matches = sorted(inp.glob(pattern))
        if matches:
            return matches[0]

    return None


def load_inputs(root: Path, sprint: str) -> tuple[str, str, str, list[str]]:
    labels = {
        "r3": "R3 Almanac",
        "r4": "R4 Macro / News",
        "r5": "R5 Technical",
    }

    contents = {}
    missing = []

    for key, label in labels.items():
        path = find_input_file(root, sprint, key)
        if path is None:
            missing.append(f"{label}: missing from input/")
            contents[key] = f"[Missing {label} evidence. Put this file in input/ before final submission.]"
        else:
            text = read_text(path)
            if not text:
                missing.append(f"{label}: found but empty - {path.name}")
                contents[key] = f"[Empty {label} evidence file: {path.name}]"
            else:
                print(f"[R6] Loaded {label}: input/{path.name}")
                contents[key] = text

    return contents["r3"], contents["r4"], contents["r5"], missing


def build_shared_prompt(root: Path, sprint: str) -> str:
    r3, r4, r5, missing = load_inputs(root, sprint)

    prompt = (
        "You are a market intelligence synthesis assistant. Given the evidence below, produce a weekly market regime recommendation.\n\n"
        f"ALMANAC EVIDENCE:\n{r3}\n\n"
        f"MACRO / NEWS EVIDENCE:\n{r4}\n\n"
        f"TECHNICAL EVIDENCE:\n{r5}\n\n"
        "REQUIRED OUTPUT - respond in exactly this structure:\n\n"
        "1. Weekly Regime: [Bullish / Bearish / Neutral / Uncertain]\n"
        "2. Confidence Score: [Low / Medium / High] + brief justification\n"
        "3. Key Supporting Evidence: (3 points max)\n"
        "4. Key Contradictions: (2 points max)\n"
        "5. Invalidation Conditions: what would change this view\n"
        "6. Predicted % move - SPX (S&P 500): [+X.X% to +X.X%] - direction + range\n"
        "   Predicted % move - NDX (Nasdaq 100): [+X.X% to +X.X%] - direction + range\n"
        "   Predicted % move - IWM (Russell 2000): [+X.X% to +X.X%] - direction + range\n"
        "7. Plain-English brief: 2-3 sentences a non-expert can understand\n"
        "8. Disclaimer: remind the reader this is not financial advice\n"
    )

    if missing:
        prompt += "\n\nINPUT FILE WARNINGS:\n"
        prompt += "\n".join(f"- {item}" for item in missing)
        prompt += "\n"

    return prompt


def generate_question(root: Path, sprint: str) -> Path:
    print("")
    print("=" * 70)
    print("[R6] Step 1: Generate shared prompt")
    print("=" * 70)

    prompt = build_shared_prompt(root, sprint)
    path = root / "output" / "Q" / "shared_prompt.md"
    write_text(path, prompt)

    print(f"[R6] Generated question file: {path}")
    return path


def set_windows_clipboard_text_utf8(text: str) -> bool:
    """
    Copy Unicode text to Windows clipboard using Win32 API.
    This avoids PowerShell argument/path issues and does not put NULL bytes
    inside the Python source code.
    """
    try:
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Define argument / return types for 64-bit safety.
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.restype = wintypes.HGLOBAL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL

        data = (text + chr(0)).encode("utf-16-le")

        h_global_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_global_mem:
            print("[R6] Clipboard error: GlobalAlloc failed.")
            return False

        locked_mem = kernel32.GlobalLock(h_global_mem)
        if not locked_mem:
            print("[R6] Clipboard error: GlobalLock failed.")
            kernel32.GlobalFree(h_global_mem)
            return False

        ctypes.memmove(locked_mem, data, len(data))
        kernel32.GlobalUnlock(h_global_mem)

        if not user32.OpenClipboard(None):
            print("[R6] Clipboard error: OpenClipboard failed.")
            kernel32.GlobalFree(h_global_mem)
            return False

        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_UNICODETEXT, h_global_mem):
                print("[R6] Clipboard error: SetClipboardData failed.")
                kernel32.GlobalFree(h_global_mem)
                return False

            # After SetClipboardData succeeds, Windows owns h_global_mem.
            return True

        finally:
            user32.CloseClipboard()

    except Exception as exc:
        print(f"[R6] Clipboard copy failed: {exc}")
        return False


def wait_for_login_if_needed(page: Page, site: AISite, wait_seconds: int) -> None:
    login_markers = [
        "Sign in",
        "Log in",
        "Login",
        "Continue with Google",
        "Continue with Microsoft",
        "登录",
        "登入",
    ]

    try:
        text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = ""

    if any(marker.lower() in text.lower() for marker in login_markers):
        print(f"[R6] {site.name}: login may be required.")
        print(f"[R6] Please login in Edge. Waiting {wait_seconds} seconds...")
        page.wait_for_timeout(wait_seconds * 1000)


def find_input_box(page: Page):
    for selector in INPUT_SELECTORS:
        try:
            loc = page.locator(selector).last
            if loc.is_visible(timeout=2500):
                return loc
        except Exception:
            pass
    return None


def paste_prompt_content(page: Page, prompt_text_for_site: str) -> bool:
    loc = find_input_box(page)

    if loc is None:
        try:
            page.mouse.click(700, 850)
            page.wait_for_timeout(1200)
            loc = find_input_box(page)
        except Exception:
            pass

    if loc is None:
        print("[R6] Input box not found.")
        return False

    try:
        loc.click(timeout=5000)
    except Exception:
        try:
            page.mouse.click(700, 850)
        except Exception:
            pass

    copied = set_windows_clipboard_text_utf8(prompt_text_for_site)

    if copied:
        try:
            page.keyboard.press("Control+V")
            page.wait_for_timeout(2500)
            print("[R6] Prompt pasted.")
            return True
        except Exception as exc:
            print(f"[R6] Ctrl+V failed: {exc}")

    print("[R6] Falling back to direct text insertion. This may take longer.")

    try:
        chunks = [prompt_text_for_site[i:i + 3000] for i in range(0, len(prompt_text_for_site), 3000)]
        for chunk in chunks:
            page.keyboard.insert_text(chunk)
            page.wait_for_timeout(200)
        print("[R6] Prompt inserted directly.")
        return True
    except Exception as exc:
        print(f"[R6] Direct insertion failed: {exc}")
        return False


def click_send(page: Page) -> bool:
    for selector in SEND_SELECTORS:
        try:
            btn = page.locator(selector).last
            if btn.is_visible(timeout=2000):
                for _ in range(12):
                    disabled = None
                    aria_disabled = None

                    try:
                        disabled = btn.get_attribute("disabled", timeout=500)
                        aria_disabled = btn.get_attribute("aria-disabled", timeout=500)
                    except Exception:
                        pass

                    if disabled is None and aria_disabled not in ("true", "True"):
                        btn.click(timeout=5000)
                        print(f"[R6] Send clicked: {selector}")
                        return True

                    page.wait_for_timeout(1000)

        except Exception:
            pass

    for key in ["Enter", "Control+Enter"]:
        try:
            page.keyboard.press(key)
            page.wait_for_timeout(1500)
            print(f"[R6] Send attempted with {key}.")
            return True
        except Exception:
            pass

    print("[R6] Could not send.")
    return False


def wait_for_answer(page: Page, site: AISite, max_wait: int) -> None:
    print(f"[R6] {site.name}: waiting for answer up to {max_wait} seconds...")

    start = time.time()
    last_text = ""
    stable_count = 0

    while time.time() - start < max_wait:
        try:
            text = page.locator("body").inner_text(timeout=4000)
        except Exception:
            text = ""

        lower = text.lower()
        still_running = any(
            marker in lower
            for marker in [
                "stop generating",
                "stop responding",
                "generating",
                "thinking",
                "停止生成",
                "正在生成",
            ]
        )

        if text == last_text and len(text) > 800 and not still_running:
            stable_count += 1
        else:
            stable_count = 0
            last_text = text

        if stable_count >= 5:
            print(f"[R6] {site.name}: answer appears stable.")
            return

        page.wait_for_timeout(3000)

    print(f"[R6] {site.name}: max wait reached. Saving current text.")


def clean_captured_text(site: AISite, page_text: str, prompt_text_for_site: str) -> str:
    text = page_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n") if line.strip()]

    cleaned_lines = []
    last = None
    for line in lines:
        if line == last:
            continue
        cleaned_lines.append(line)
        last = line

    cleaned = "\n".join(cleaned_lines)

    first_part = prompt_text_for_site[:300]
    idx = cleaned.find(first_part)

    if idx != -1:
        candidate = cleaned[idx + len(first_part):].strip()
        if len(candidate) > 300:
            cleaned = candidate

    header = (
        f"# {site.name} response\n\n"
        f"Captured automatically from {site.name} web page.\n"
        "----- CAPTURED TEXT -----\n\n"
    )

    return header + cleaned.strip() + "\n"


def site_prompt(site: AISite, base_prompt: str) -> str:
    if site.key == "claude":
        return base_prompt.rstrip() + "\n\n" + CLAUDE_EXTRA_INSTRUCTION
    return base_prompt



def remove_prompt_echo(answer: str, prompt_text_for_site: str) -> str:
    """
    Remove obvious echoed prompt fragments if the page selector accidentally includes them.
    """
    answer = answer.replace("\r\n", "\n").replace("\r", "\n").strip()
    prompt_start = prompt_text_for_site[:300].strip()

    if prompt_start and prompt_start in answer:
        idx = answer.find(prompt_start)
        candidate = answer[idx + len(prompt_start):].strip()
        if len(candidate) > 100:
            answer = candidate

    # Remove common UI leftovers at the beginning/end.
    ui_lines = {
        "copy", "copied", "regenerate", "share", "edit", "retry", "like", "dislike",
        "thumbs up", "thumbs down", "read aloud", "new chat", "send", "stop generating",
        "stop responding", "sources", "thinking", "thoughts", "search", "deep think",
        "复制", "已复制", "重新生成", "分享", "编辑", "发送", "停止生成"
    }

    lines = []
    for line in answer.splitlines():
        cleaned = line.strip()
        if not cleaned:
            lines.append("")
            continue
        if cleaned.lower() in ui_lines:
            continue
        lines.append(line.rstrip())

    # Collapse too many blank lines.
    out_lines = []
    blank = 0
    for line in lines:
        if line.strip():
            blank = 0
            out_lines.append(line)
        else:
            blank += 1
            if blank <= 1:
                out_lines.append("")

    return "\n".join(out_lines).strip()


def extract_answer_from_candidates(page: Page, selectors: list[str], prompt_text_for_site: str) -> str:
    """
    Best-effort extraction of the last assistant answer block only.
    It avoids body.inner_text because that captures sidebars, prompts, buttons, and other UI text.
    """
    js = """
    (selectors) => {
        function visible(el) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.display !== 'none' && style.visibility !== 'hidden'
                && rect.width > 10 && rect.height > 10;
        }

        const items = [];
        const seen = new Set();

        for (const sel of selectors) {
            let nodes = [];
            try {
                nodes = Array.from(document.querySelectorAll(sel));
            } catch (e) {
                continue;
            }

            for (const el of nodes) {
                if (!visible(el)) continue;
                const text = (el.innerText || el.textContent || '').trim();
                if (!text || text.length < 80) continue;
                const key = text.slice(0, 300);
                if (seen.has(key)) continue;
                seen.add(key);

                const rect = el.getBoundingClientRect();
                items.push({
                    text,
                    top: rect.top + window.scrollY,
                    height: rect.height,
                    length: text.length,
                    selector: sel
                });
            }
        }

        items.sort((a, b) => {
            if (a.top !== b.top) return a.top - b.top;
            return a.length - b.length;
        });

        return items;
    }
    """

    try:
        candidates = page.evaluate(js, selectors)
    except Exception:
        candidates = []

    if not candidates:
        return ""

    prompt_head = prompt_text_for_site[:250].strip()

    # Prefer the last candidate that does not look like the user prompt.
    filtered = []
    for item in candidates:
        text = item.get("text", "").strip()
        if not text:
            continue
        if prompt_head and prompt_head in text and len(text) < len(prompt_text_for_site) + 500:
            continue
        filtered.append(item)

    if not filtered:
        filtered = candidates

    # Use the last visible answer-like block. If the last one is tiny, use the longest among the last few.
    tail = filtered[-5:]
    chosen = max(tail, key=lambda x: len(x.get("text", "")))
    return remove_prompt_echo(chosen.get("text", ""), prompt_text_for_site)


def extract_ai_answer_only(page: Page, site: AISite, prompt_text_for_site: str) -> str:
    """
    Extract only the AI answer, with site-specific selectors first and generic selectors second.
    """
    selector_map = {
        "chatgpt": [
            "[data-message-author-role='assistant']",
            "article:has([data-message-author-role='assistant'])",
            "[data-testid*='conversation-turn'] [data-message-author-role='assistant']",
            ".markdown",
        ],
        "deepseek": [
            ".ds-markdown",
            "[class*='ds-markdown']",
            "[class*='markdown']",
            "[class*='message'] [class*='content']",
            "[class*='answer']",
        ],
        "gemini": [
            "message-content",
            ".model-response-text",
            "[class*='model-response']",
            "[class*='response-content']",
            "[data-response-index]",
            "[class*='markdown']",
        ],
        "claude": [
            "[class*='font-claude-message']",
            "[data-testid*='message']",
            "[class*='prose']",
            "[class*='message'] [class*='content']",
        ],
    }

    generic = [
        "main article",
        "main [class*='markdown']",
        "main [class*='prose']",
        "main [class*='message']",
        "[role='article']",
    ]

    answer = extract_answer_from_candidates(
        page,
        selector_map.get(site.key, []) + generic,
        prompt_text_for_site,
    )

    if answer:
        return answer.strip()

    # Last fallback: try browser selection around assistant blocks, but still do not add headers.
    try:
        body_text = page.locator("body").inner_text(timeout=8000)
    except Exception:
        body_text = ""

    return remove_prompt_echo(body_text, prompt_text_for_site)


def save_answer(root: Path, site: AISite, sprint: str, page: Page, prompt_text_for_site: str) -> None:
    output_path = root / "output" / "llm_raw_responses" / site.output_filename

    answer_only = extract_ai_answer_only(page, site, prompt_text_for_site)

    write_text(output_path, answer_only)

    print(f"[R6] Saved answer only: {output_path}")

def run_one_site(
    context: BrowserContext,
    root: Path,
    site: AISite,
    sprint: str,
    base_prompt_text: str,
    max_wait: int,
    login_wait: int,
) -> None:
    print("")
    print("=" * 70)
    print(f"[R6] Asking {site.name}")
    print("=" * 70)

    prompt_text_for_site = site_prompt(site, base_prompt_text)

    if site.key == "claude":
        print(f"[R6] Claude extra instruction appended: {CLAUDE_EXTRA_INSTRUCTION}")

    page = context.new_page()
    page.set_default_timeout(15000)

    try:
        page.goto(site.url, wait_until="domcontentloaded", timeout=80000)
        page.wait_for_timeout(7000)

        wait_for_login_if_needed(page, site, login_wait)
        page.wait_for_timeout(4000)

        pasted = paste_prompt_content(page, prompt_text_for_site)
        if not pasted:
            raise RuntimeError("Could not paste prompt.")

        sent = click_send(page)
        if not sent:
            raise RuntimeError("Could not send prompt.")

        wait_for_answer(page, site, max_wait=max_wait)
        save_answer(root, site, sprint, page, prompt_text_for_site)

    except Exception as exc:
        print(f"[R6] ERROR on {site.name}: {exc}")

    finally:
        page.wait_for_timeout(2000)


def ask_all_ai(root: Path, sprint: str, base_prompt_text: str, max_wait: int, login_wait: int, only: str, headless: bool) -> None:
    print("")
    print("=" * 70)
    print("[R6] Step 2: Ask AI websites in your Microsoft Edge")
    print("=" * 70)

    print("[R6] Connecting to Edge on http://127.0.0.1:9222")
    print("[R6] If this fails, close Edge and run RUN_R6_ONE_CLICK.bat again.")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

        try:
            # Use the existing Edge context if available.
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = browser.new_context(
                    viewport={"width": 1400, "height": 950},
                    locale="en-US",
                    timezone_id="Asia/Singapore",
                    permissions=["clipboard-read", "clipboard-write"],
                )

            for site in AI_SITES:
                if only != "all" and only != site.key:
                    continue

                run_one_site(
                    context=context,
                    root=root,
                    site=site,
                    sprint=sprint,
                    base_prompt_text=base_prompt_text,
                    max_wait=max_wait,
                    login_wait=login_wait,
                )

        finally:
            browser.close()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def replace_all(text: str, old: str, new: str) -> str:
    return text.replace(old, new)


def find_label_value(labels: list[str], text: str) -> str:
    for line in text.splitlines():
        low = line.lower()
        for label in labels:
            low_label = label.lower()
            pos = low.find(low_label)
            if pos == -1:
                continue
            colon = line.find(":", pos)
            if colon != -1:
                value = line[colon + 1 :]
            else:
                value = line[pos + len(label) :]
            value = normalize_space(value).rstrip(".;:").strip()
            if value:
                return value
    return "Not found"


def find_line_value(patterns: list[str], text: str) -> str:
    for pat in patterns:
        try:
            match = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
            if match and len(match.groups()) >= 1:
                value = normalize_space(match.group(1)).rstrip(".;:").strip()
                return value or "Not found"
        except re.error:
            continue
    return "Not found"


def line_matches_any(line: str, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            if re.search(pat, line, flags=re.IGNORECASE):
                return True
        except re.error:
            pass
    return False


def strip_bullet_prefix(line: str) -> str:
    line = line.strip()
    while line and (line[0] in "-*:" or line[0].isspace()):
        line = line[1:].strip()
    return line


def find_section(start_patterns: list[str], end_patterns: list[str], text: str) -> str:
    collecting = False
    collected: list[str] = []

    for line in text.splitlines():
        if not collecting:
            if line_matches_any(line, start_patterns):
                collecting = True
                if ":" in line:
                    remainder = strip_bullet_prefix(line.split(":", 1)[1])
                    if remainder:
                        collected.append(remainder)
        else:
            if line_matches_any(line, end_patterns):
                break
            cleaned = strip_bullet_prefix(line)
            if cleaned:
                collected.append(cleaned)
            if len(collected) >= 4:
                break

    if not collected:
        return "Not found"
    return "<br>".join(collected)


def parse_range_for_asset(asset: str, text: str) -> str:
    patterns = [
        rf"Predicted\s*%\s*move\s*[-:]*\s*{re.escape(asset)}\b[^:\n]*:\s*([^\n]+)",
        rf"{re.escape(asset)}\s*\([^\)]*\)\s*:\s*([^\n]+)",
        rf"{re.escape(asset)}\s*:\s*([^\n]+)",
    ]
    raw = find_line_value(patterns, text)
    if raw == "Not found":
        return raw

    bracket = re.search(r"(\[[^\]]*?%[^\]]*\])", raw)
    if bracket:
        return bracket.group(1)

    rng = re.search(
        r"([+-]?\d+(?:\.\d+)?%?\s*(?:to|--|---|-)\s*[+-]?\d+(?:\.\d+)?%?)",
        raw,
        flags=re.IGNORECASE,
    )
    if rng:
        return rng.group(1)

    return raw


def numbers_from_range(range_text: str) -> list[float]:
    nums: list[float] = []
    for match in re.finditer(r"[+-]?\d+(?:\.\d+)?", range_text):
        if len(nums) >= 2:
            break
        try:
            nums.append(float(match.group(0)))
        except ValueError:
            pass
    return nums


def direction_from_range(range_text: str) -> str:
    nums = numbers_from_range(range_text)
    if len(nums) >= 2:
        midpoint = (nums[0] + nums[1]) / 2.0
        if midpoint > 0.05:
            return "Bullish / Up"
        if midpoint < -0.05:
            return "Bearish / Down"
        return "Neutral / Flat"

    low = range_text.lower()
    if "bullish" in low or "up" in low or "positive" in low or "+" in range_text:
        return "Bullish / Up"
    if "bearish" in low or "down" in low or "negative" in low:
        return "Bearish / Down"
    return "Not found"


def parse_model_result(model_key: str, raw_text: str) -> ModelResult:
    result = ModelResult(model_key=model_key, model_name=DISPLAY[model_key], raw_text=raw_text)

    result.weekly_regime = find_label_value(["Weekly Regime"], raw_text)
    result.confidence = find_label_value(["Confidence Score", "Confidence"], raw_text)

    result.spx_range = parse_range_for_asset("SPX", raw_text)
    result.ndx_range = parse_range_for_asset("NDX", raw_text)
    result.iwm_range = parse_range_for_asset("IWM", raw_text)
    result.spx_direction = direction_from_range(result.spx_range)
    result.ndx_direction = direction_from_range(result.ndx_range)
    result.iwm_direction = direction_from_range(result.iwm_range)

    result.supporting = find_section(
        [r"^\s*3\.?\s*Key\s+Supporting\s+Evidence\s*:?.*"],
        [r"^\s*4\.?\s*Key\s+Contradictions", r"^\s*5\.?\s*Invalidation", r"^\s*6\.?\s*Predicted"],
        raw_text,
    )
    result.contradictions = find_section(
        [r"^\s*4\.?\s*Key\s+Contradictions\s*:?.*"],
        [r"^\s*5\.?\s*Invalidation", r"^\s*6\.?\s*Predicted", r"^\s*7\.?\s*Plain"],
        raw_text,
    )
    result.invalidation = find_section(
        [r"^\s*5\.?\s*Invalidation\s+Conditions\s*:?.*"],
        [r"^\s*6\.?\s*Predicted", r"^\s*7\.?\s*Plain", r"^\s*8\.?\s*Disclaimer"],
        raw_text,
    )
    result.plain_english = find_section(
        [r"^\s*7\.?\s*Plain-English\s+brief\s*:?.*"],
        [r"^\s*8\.?\s*Disclaimer"],
        raw_text,
    )
    return result


def load_model_results(root: Path, sprint: str) -> list[ModelResult]:
    results: list[ModelResult] = []
    missing: list[Path] = []

    for model in MODELS:
        path = root / "output" / "llm_raw_responses" / f"synthesis_{model}.txt"
        if not path.exists():
            missing.append(path)
            continue
        results.append(parse_model_result(model, read_text(path)))

    if missing:
        print("WARNING: Missing AI response txt files:")
        for path in missing:
            print(f"- {path}")

    return results


def clean_regime(value: str) -> str:
    low = value.lower()
    if "bullish" in low:
        return "Bullish"
    if "bearish" in low:
        return "Bearish"
    if "neutral" in low:
        return "Neutral"
    if "uncertain" in low:
        return "Uncertain"
    return "Uncertain"


def clean_confidence(value: str) -> str:
    low = value.lower()
    if "high" in low:
        return "High"
    if "medium" in low:
        return "Medium"
    if "low" in low:
        return "Low"
    return "Medium"


def majority(values: list[str], fallback: str) -> str:
    counts: dict[str, int] = {}
    for value in values:
        if value and value != "Not found":
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return fallback
    return max(counts.items(), key=lambda item: item[1])[0]


def avg_midpoint(result: ModelResult) -> Optional[float]:
    mids: list[float] = []
    for rng in [result.spx_range, result.ndx_range, result.iwm_range]:
        nums = numbers_from_range(rng)
        if len(nums) >= 2:
            mids.append((nums[0] + nums[1]) / 2.0)
    if not mids:
        return None
    return sum(mids) / len(mids)


def most_cautious(midpoints: list[tuple[str, Optional[float]]]) -> str:
    best = "Not clear from available model outputs"
    best_abs = float("inf")
    for name, midpoint in midpoints:
        if midpoint is not None and abs(midpoint) < best_abs:
            best_abs = abs(midpoint)
            best = name
    return best


def agreement_points(results: list[ModelResult]) -> list[str]:
    regimes: list[str] = []
    spx_dirs: list[str] = []
    ndx_dirs: list[str] = []
    iwm_dirs: list[str] = []

    for r in results:
        regimes.append(clean_regime(r.weekly_regime))
        if r.spx_direction != "Not found":
            spx_dirs.append(r.spx_direction)
        if r.ndx_direction != "Not found":
            ndx_dirs.append(r.ndx_direction)
        if r.iwm_direction != "Not found":
            iwm_dirs.append(r.iwm_direction)

    points: list[str] = []
    if regimes:
        points.append(f"Most models leaned toward a {majority(regimes, 'Uncertain')} weekly regime.")
    if spx_dirs:
        points.append(f"SPX direction consensus was closest to {majority(spx_dirs, 'Not found')}.")
    if ndx_dirs:
        points.append(f"NDX direction consensus was closest to {majority(ndx_dirs, 'Not found')}.")
    if iwm_dirs:
        points.append(f"IWM direction consensus was closest to {majority(iwm_dirs, 'Not found')}.")
    while len(points) < 4:
        points.append("All models used the same R3/R4/R5 evidence package and shared prompt.")
    return points[:4]


def disagreement_points(results: list[ModelResult]) -> list[str]:
    regimes = [clean_regime(r.weekly_regime) for r in results]
    confidences = [clean_confidence(r.confidence) for r in results]
    spx_ranges = [r.spx_range for r in results if r.spx_range != "Not found"]

    points: list[str] = []
    if len(set(regimes)) > 1:
        points.append("Models did not fully agree on the weekly regime label.")
    if len(set(confidences)) > 1:
        points.append("Models assigned different confidence levels.")
    if len(set(spx_ranges)) > 1:
        points.append("Predicted percentage ranges differed, especially around the size of the expected move.")
    if not points:
        points.append("No major disagreement was detected from the structured fields.")
    while len(points) < 4:
        points.append("Individual models weighted the same evidence differently.")
    return points[:4]


def bulletize(points: list[str], max_items: int) -> str:
    return "".join(f"- {point}\n" for point in points[:max_items])


def compact_cell(text: str, max_chars: int = 180) -> str:
    if not text or text == "Not found":
        return "Not found"
    text = replace_all(text, "|", "/")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def get_field(by_model: dict[str, ModelResult], model: str, field: str) -> str:
    r = by_model.get(model)
    if r is None:
        return "Missing"
    return getattr(r, field, "Not found")


def generate_comparison_md(sprint: str, results: list[ModelResult]) -> str:
    by_model = {r.model_key: r for r in results}

    regimes = [clean_regime(r.weekly_regime) for r in results]
    confidences = [clean_confidence(r.confidence) for r in results]
    overall_regime = majority(regimes, "Uncertain")
    overall_confidence = majority(confidences, "Medium")

    midpoint_list = [(r.model_name, avg_midpoint(r)) for r in results]

    most_bullish_model = "Not clear from available model outputs"
    most_bearish_model = "Not clear from available model outputs"
    max_mid = -float("inf")
    min_mid = float("inf")

    for name, midpoint in midpoint_list:
        if midpoint is None:
            continue
        if midpoint > max_mid:
            max_mid = midpoint
            most_bullish_model = name
        if midpoint < min_mid:
            min_mid = midpoint
            most_bearish_model = name

    cautious_model = most_cautious(midpoint_list)
    agreement = agreement_points(results)
    disagreement = disagreement_points(results)

    table_rows = [
        ("Weekly Regime", "weekly_regime"),
        ("Confidence", "confidence"),
        ("SPX Direction", "spx_direction"),
        ("SPX % Range", "spx_range"),
        ("NDX Direction", "ndx_direction"),
        ("NDX % Range", "ndx_range"),
        ("IWM Direction", "iwm_direction"),
        ("IWM % Range", "iwm_range"),
        ("Main Bullish / Stabilising Evidence", "contradictions"),
        ("Main Bearish Evidence", "supporting"),
        ("Invalidation Condition", "invalidation"),
    ]

    table_lines = [
        "| Dimension | ChatGPT | Claude | Gemini | DeepSeek |",
        "|---|---|---|---|---|",
    ]

    for label, field in table_rows:
        table_lines.append(
            "| "
            + label
            + " | "
            + " | ".join(compact_cell(get_field(by_model, model, field)) for model in MODELS)
            + " |"
        )

    table = "\n".join(table_lines) + "\n"

    notes = []

    for model in MODELS:
        name = DISPLAY[model]
        r = by_model.get(model)
        if r is None:
            notes.append(f"### {name}\n\nNo saved response file was found for {name}.\n")
            continue

        notes.append(
            f"### {name}\n\n"
            f"{name} suggested a **{r.weekly_regime}** regime with **{r.confidence}** confidence.\n\n"
            "Predicted ranges:\n\n"
            f"- SPX: {r.spx_range}\n"
            f"- NDX: {r.ndx_range}\n"
            f"- IWM: {r.iwm_range}\n\n"
            "Main reasoning:\n\n"
            f"- {r.supporting}\n\n"
            "Key risk / invalidation:\n\n"
            f"- {r.invalidation}\n"
        )

    notes_text = "\n".join(notes)

    def values_for(field: str) -> list[str]:
        values = []
        for r in results:
            value = get_field(by_model, r.model_key, field)
            if value != "Not found":
                values.append(value)
        return values

    spx_suggested = majority(values_for("spx_range"), "Not found")
    ndx_suggested = majority(values_for("ndx_range"), "Not found")
    iwm_suggested = majority(values_for("iwm_range"), "Not found")
    key_risk = majority(values_for("invalidation"), "Not clear from available model outputs")

    raw_paths = "\n".join(f"- `output/llm_raw_responses/synthesis_{model}.txt`" for model in MODELS)

    return (
        f"# LLM Comparison {sprint}\n\n"
        "## Role\n\nR6 LLM Synthesis Operator\n\n"
        "## Models Used\n\n- ChatGPT\n- Claude\n- Gemini\n- DeepSeek\n\n"
        "All four models were given the same shared prompt and the same evidence package, including:\n\n"
        "- Almanac evidence\n- Macro / News evidence\n- Technical evidence\n\n---\n\n"
        "## Shared Prompt\n\n"
        "- `output/Q/shared_prompt.md`\n\n"
        "---\n\n"
        "## Raw LLM Responses\n\n"
        "Raw AI responses are saved in:\n\n"
        f"{raw_paths}\n\n"
        "---\n\n"
        "## Comparison Table\n\n"
        f"{table}\n"
        "---\n\n"
        "## Agreement Between Models\n\nThe models mostly agreed that:\n\n"
        f"{bulletize(agreement, 4)}\n"
        "---\n\n"
        "## Disagreement Between Models\n\nThe models disagreed on:\n\n"
        f"{bulletize(disagreement, 4)}\n"
        "---\n\n"
        "## Model-by-Model Notes\n\n"
        f"{notes_text}\n"
        "---\n\n"
        "## R6 Synthesis Summary\n\n"
        f"The overall AI view is **{overall_regime}** with **{overall_confidence}** confidence.\n\n"
        "The strongest common argument is that:\n\n"
        f"{bulletize(agreement, 3)}\n"
        "The biggest uncertainty is:\n\n"
        f"- {key_risk}\n\n"
        "The most bullish model is:\n\n"
        f"- {most_bullish_model}\n\n"
        "The most bearish model is:\n\n"
        f"- {most_bearish_model}\n\n"
        "The most cautious model is:\n\n"
        f"- {cautious_model}\n\n"
        "This output will be passed to R7 Human Score Analyst for final human judgement.\n\n"
        "---\n\n"
        "## R6 Recommendation to R7\n\n"
        "Suggested regime for human review:\n\n"
        f"**{overall_regime}**\n\n"
        "Suggested confidence:\n\n"
        f"**{overall_confidence}**\n\n"
        "Suggested relative strength / weakness:\n\n"
        f"1. SPX: {majority(values_for('spx_direction'), 'Not found')}\n"
        f"2. NDX: {majority(values_for('ndx_direction'), 'Not found')}\n"
        f"3. IWM: {majority(values_for('iwm_direction'), 'Not found')}\n\n"
        "Suggested predicted ranges for human review:\n\n"
        f"- SPX: {spx_suggested}\n"
        f"- NDX: {ndx_suggested}\n"
        f"- IWM: {iwm_suggested}\n\n"
        "Suggested key risk:\n\n"
        f"- {key_risk}\n\n"
        "Suggested invalidation condition:\n\n"
        f"- {key_risk}\n"
    )


def generate_report(root: Path, sprint: str) -> Path:
    print("")
    print("=" * 70)
    print("[R6] Step 3: Generate final comparison report")
    print("=" * 70)

    results = load_model_results(root, sprint)

    if not results:
        raise RuntimeError("No AI response files found. Cannot generate final report.")

    output = root / "output" / "llm" / "llm_comparison.md"
    write_text(output, generate_comparison_md(sprint, results))

    print(f"[R6] Final report generated: {output}")
    return output


def summarize(root: Path, sprint: str) -> None:
    print("")
    print("=" * 70)
    print("[R6] DONE")
    print("=" * 70)

    paths = [
        root / "output" / "Q" / "shared_prompt.md",
        root / "output" / "llm_raw_responses" / f"synthesis_chatgpt.txt",
        root / "output" / "llm_raw_responses" / f"synthesis_deepseek.txt",
        root / "output" / "llm_raw_responses" / f"synthesis_gemini.txt",
        root / "output" / "llm_raw_responses" / f"synthesis_claude.txt",
        root / "output" / "llm" / "llm_comparison.md",
    ]

    for path in paths:
        status = "OK" if path.exists() else "MISSING"
        print(f"[{status}] {path}")

    print("")
    print("Folder summary:")
    print(f"- Input evidence:       {root / 'input'}")
    print(f"- Generated question:   {root / 'output' / 'Q'}")
    print(f"- Raw AI responses:     {root / 'output' / 'llm_raw_responses'}")
    print(f"- Final report:         {root / 'output' / 'llm'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="R6 integrated one-click workflow")
    parser.add_argument("--sprint", default="Current Week")
    parser.add_argument("--only", choices=["all", "chatgpt", "deepseek", "gemini", "claude"], default="all")
    parser.add_argument("--max-wait", type=int, default=180)
    parser.add_argument("--login-wait", type=int, default=120)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    args = parser.parse_args()

    root = project_root_from_app()
    ensure_dirs(root)

    print(f"[R6] Project root: {root}")
    print(f"[R6] Sprint: {args.sprint}")

    question_path = generate_question(root, args.sprint)
    base_prompt_text = read_text(question_path)

    if not args.skip_ai:
        ask_all_ai(
            root=root,
            sprint=args.sprint,
            base_prompt_text=base_prompt_text,
            max_wait=args.max_wait,
            login_wait=args.login_wait,
            only=args.only,
            headless=args.headless,
        )

    if not args.skip_report:
        generate_report(root, args.sprint)

    summarize(root, args.sprint)

    input("\nPress ENTER to close...")


if __name__ == "__main__":
    main()
