#!/usr/bin/env python3
"""Post a single tweet to X (Twitter) via CloakBrowser.

X has no chain/threads composer in this workflow — one call = one post.

Usage:
  x_post.py "tweet text"
  x_post.py -f tweet.txt

Cookies: storage_state_x.json (import: import_cookies.py x_cookies.txt storage_state_x.json .x.com,.twitter.com)
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "storage_state_x.json"
HOME = "https://x.com/home"
MAX_LEN = 280


def _weighted_len(text: str) -> int:
    """X counts every URL as 23 chars (t.co), regardless of raw length."""
    urls = re.findall(r"(?:https?://|www\.)\S+|[a-z0-9][a-z0-9.-]*\.[a-z]{2,}\S*", text, re.I)
    raw = len(text)
    saved = sum(len(u) for u in urls)
    return raw - saved + 23 * len(urls)


def _launch(headless: bool):
    """Cloak first; stock fallback via one-shot re-exec (cloak leaves an
    asyncio loop that breaks sync_playwright in the same process)."""
    if os.environ.get("X_BROWSER") != "stock":
        try:
            from cloakbrowser import launch as _cloak_launch

            browser = _cloak_launch(headless=headless, args=["--disable-dev-shm-usage"])
            ctx = browser.new_context(storage_state=str(STATE), viewport={"width": 1280, "height": 900})
            print("browser: cloakbrowser (stealth)")
            return None, browser, ctx, ctx.new_page()
        except Exception as e:
            print(f"browser: cloak failed ({e}) → restart stock")
            os.environ["X_BROWSER"] = "stock"
            os.execv(sys.executable, [sys.executable, *sys.argv])
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, args=["--disable-dev-shm-usage"])
    ctx = browser.new_context(storage_state=str(STATE), viewport={"width": 1280, "height": 900})
    print("browser: stock chromium")
    return pw, browser, ctx, ctx.new_page()


def post_tweet(text: str, headless: bool = True, media: Path | None = None) -> str:
    text = text.strip()
    if not text:
        raise SystemExit("empty text")
    if media is not None and not Path(media).exists():
        raise SystemExit(f"media not found: {media}")
    w = _weighted_len(text)
    if w > MAX_LEN:
        raise SystemExit(f"text too long for X: weighted {w} > {MAX_LEN} (URLs count 23 each)")
    if not STATE.exists():
        raise SystemExit("no session: import_cookies.py x_cookies.txt storage_state_x.json .x.com,.twitter.com")

    pw, browser, ctx, page = _launch(headless)
    try:
        page.set_default_timeout(60_000)
        page.goto(HOME, wait_until="domcontentloaded")
        time.sleep(6)
        if not page.locator('a[data-testid="AppTabBar_Profile_Link"]').count():
            page.screenshot(path=str(ROOT / "debug_x_login.png"), full_page=True)
            raise SystemExit("X session invalid (no profile link) → debug_x_login.png")

        box = page.locator('[role="textbox"][data-testid]').first
        box.click()
        time.sleep(0.4)
        if media is not None:
            # single global input on X (no chain here) → attaches to this tweet
            page.locator("input[type=file]").first.set_input_files(str(media))
            deadline = time.time() + 40
            while time.time() < deadline:
                if page.evaluate(
                    "() => [...document.querySelectorAll('img')].some(i => (i.src||'').startsWith('blob:'))"
                ):
                    break
                time.sleep(0.5)
            else:
                page.screenshot(path=str(ROOT / "debug_x_media.png"), full_page=True)
                raise SystemExit("media preview never appeared → debug_x_media.png")
            print(f"  media: {Path(media).name} (preview ok)")
            box.click()
            time.sleep(0.4)
        box.press_sequentially(text, delay=15)
        time.sleep(1.5)

        # sanity: text landed
        if text[:30] not in page.inner_text("body"):
            page.screenshot(path=str(ROOT / "debug_x_notyped.png"), full_page=True)
            raise SystemExit("text not in composer → debug_x_notyped.png")

        btn = page.locator('[data-testid="tweetButtonInline"]')
        if not btn.count():
            btn = page.locator('[data-testid="tweetButton"]')
        btn = btn.first
        for _ in range(40):
            try:
                if btn.is_enabled():
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            page.screenshot(path=str(ROOT / "debug_x_btn.png"), full_page=True)
            raise SystemExit("Post button never enabled → debug_x_btn.png")
        btn.click()
        time.sleep(6)

        # find the new tweet: profile → first /status/ link
        page.goto(HOME, wait_until="domcontentloaded")
        time.sleep(3)
        page.locator('a[data-testid="AppTabBar_Profile_Link"]').click()
        time.sleep(5)
        url = ""
        for _ in range(10):
            hrefs = page.eval_on_selector_all(
                'a[href*="/status/"]', "els => els.map(e => e.href)"
            )
            if hrefs:
                url = hrefs[0]
                break
            time.sleep(1)
        # verify text on that tweet. X auto-linkifies domains ("muse.ai" →
        # "https://\nmuse.ai" in innerText) → strip "https://" FIRST, lalu
        # collapse whitespace, baru bandingkan (false-negative seen 2026-10-06)
        body = page.inner_text("body")
        norm = lambda s: re.sub(r"\s+", " ", re.sub(r"https?://", "", s)).strip()
        ok = norm(text[:40]) in norm(body)
        print(f"verify text on profile: {ok}")
        print(f"url {url}")
        return url
    finally:
        try:
            ctx.storage_state(path=str(STATE))
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if pw is not None:
            pw.stop()


def main() -> None:
    ap = argparse.ArgumentParser(description="Post single tweet to X")
    ap.add_argument("text", nargs="*", help="tweet text")
    ap.add_argument("-f", "--file", type=Path, help="read text from file")
    ap.add_argument("--media", type=Path, help="attach image/video to the tweet")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    if args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = " ".join(args.text)
    post_tweet(text, headless=not args.headed, media=args.media)


if __name__ == "__main__":
    main()
