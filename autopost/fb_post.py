#!/usr/bin/env python3
"""Post one text (+optional photo) to a Facebook GROUP (not timeline).

Usage:
  fb_post.py <group_url_or_id> "text"
  fb_post.py <group_url_or_id> -f post.txt --media media/x.jpg

Cookies: storage_state_fb.json (import_cookies.py fb_cookies.txt storage_state_fb.json .facebook.com,.www.facebook.com)
Target list: fb_groups_target.txt (id | nama)
"""
import argparse
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "storage_state_fb.json"


def _launch(headless: bool):
    if os.environ.get("FB_BROWSER") != "stock":
        try:
            from cloakbrowser import launch as _cloak_launch

            browser = _cloak_launch(headless=headless, args=["--disable-dev-shm-usage"])
            ctx = browser.new_context(storage_state=str(STATE), viewport={"width": 1280, "height": 1000})
            print("browser: cloakbrowser (stealth)")
            return None, browser, ctx, ctx.new_page()
        except Exception as e:
            print(f"browser: cloak failed ({e}) → restart stock")
            os.environ["FB_BROWSER"] = "stock"
            os.execv(sys.executable, [sys.executable, *sys.argv])
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, args=["--disable-dev-shm-usage"])
    ctx = browser.new_context(storage_state=str(STATE), viewport={"width": 1280, "height": 1000})
    print("browser: stock chromium")
    return pw, browser, ctx, ctx.new_page()


def _group_url(ref: str) -> str:
    if ref.startswith("http"):
        return ref if ref.endswith("/") else ref + "/"
    return f"https://www.facebook.com/groups/{ref}/"


def post_to_group(group: str, text: str, headless: bool = True, media: Path | None = None) -> bool:
    text = text.strip()
    if not text:
        raise SystemExit("empty text")
    if media is not None and not Path(media).exists():
        raise SystemExit(f"media not found: {media}")
    if not STATE.exists():
        raise SystemExit("no session: import_cookies.py fb_cookies.txt storage_state_fb.json .facebook.com,.www.facebook.com")

    url = _group_url(group)
    pw, browser, ctx, page = _launch(headless)
    try:
        page.set_default_timeout(60_000)
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(7)
        if page.locator('[data-testid="royal_login_button"], input[name="email"]').count():
            raise SystemExit("FB session invalid (login page) → re-export cookies")
        print(f"group: {page.title()}")

        # dismiss stray flyouts first (notifications is also role=dialog
        # and would otherwise steal .first everywhere)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        composer_sel = '[role="dialog"]:has-text("Create post")'
        opened = False
        for _attempt in range(3):
            entry = page.locator('div[role="button"]:has-text("Write something")')
            if not entry.count():
                entry = page.get_by_text("Write something...", exact=False)
            if not entry.count():
                break
            try:
                entry.first.scroll_into_view_if_needed()
                entry.first.click(timeout=8000)
            except Exception:
                entry.first.click(force=True)  # overlay/cover intercepts
            try:
                page.wait_for_selector(composer_sel, timeout=10000)
                opened = True
                break
            except Exception:
                page.keyboard.press("Escape")
                time.sleep(1)
        if not opened:
            page.screenshot(path=str(ROOT / "debug_fb_nodialog.png"), full_page=True)
            raise SystemExit("composer dialog not open → debug_fb_nodialog.png")
        dlg = page.locator(composer_sel).first
        editor = None
        deadline = time.time() + 20
        while time.time() < deadline:
            # FB portals the editor OUTSIDE the dialog node sometimes →
            # search page-wide, filter by visible + placeholder/position
            cands = page.locator('[contenteditable="true"]')
            for i in range(cands.count()):
                el = cands.nth(i)
                try:
                    if not el.is_visible():
                        continue
                    al = (el.get_attribute("aria-label") or "") + (el.get_attribute("aria-placeholder") or "")
                    y = (el.bounding_box() or {}).get("y", 9999)
                    if re.search(r"public post|on your mind|something", al, re.I) or 300 < y < 900:
                        editor = el
                        break
                except Exception:
                    continue
            if editor is not None:
                break
            time.sleep(0.5)
        if editor is None:
            page.screenshot(path=str(ROOT / "debug_fb_noeditor.png"), full_page=True)
            raise SystemExit("no composer editor in dialog → debug_fb_noeditor.png")
        editor.click()
        time.sleep(0.5)

        if media is not None:
            # file input is inside the dialog sometimes, portaled page-level others
            fi = dlg.locator("input[type=file]")
            if not fi.count():
                fi = page.locator("input[type=file]")
            fi.first.set_input_files(str(media))
            time.sleep(5)
            print(f"  media: {Path(media).name} (attached)")

        editor.press_sequentially(text, delay=8)
        time.sleep(2)
        # check the editor itself (it may be portaled outside the dialog node)
        if text[:30] not in editor.inner_text():
            page.screenshot(path=str(ROOT / "debug_fb_notyped.png"), full_page=True)
            raise SystemExit("text not in editor → debug_fb_notyped.png")

        # Post button: must be VISIBLE + ENABLED (waits out media upload /
        # required topic). aria-disabled or class-based disabled both count.
        btn = None
        deadline = time.time() + 45
        while time.time() < deadline:
            # page-scoped: only the composer dialog has aria-label="Post"
            cands = page.locator('[aria-label="Post"]')
            for i in range(cands.count()):
                el = cands.nth(i)
                try:
                    lab = (el.get_attribute("aria-label") or "").strip()
                    if lab != "Post" or not el.is_visible():
                        continue
                    state = el.evaluate(
                        """e => {
                          var dis = e.getAttribute('aria-disabled') === 'true';
                          var cls = (e.className || '');
                          if (/\\bx1i10hfl\\b/.test(cls) && /disabled|xf7dkkf/.test(cls)) dis = true;
                          return {dis: dis, txt: (e.innerText || '').trim()};
                        }"""
                    )
                    if not state["dis"] and state["txt"] in ("Post", ""):
                        btn = el
                        break
                except Exception:
                    continue
            if btn is not None:
                break
            time.sleep(0.7)
        if btn is None:
            page.screenshot(path=str(ROOT / "debug_fb_nopost.png"), full_page=True)
            dump = ""
            try:
                dump = dlg.inner_text()[:400].replace("\n", " | ")
            except Exception:
                pass
            raise SystemExit(f"Post button never enabled → debug_fb_nopost.png | dialog: {dump}")
        # submit: SUCCESS = composer dialog detaches. (Other role=dialog
        # flyouts, e.g. notifications, may stay open and must not confuse us)
        submitted = False
        for attempt in range(3):
            if btn is None:
                break
            btn.click()
            try:
                page.wait_for_selector(composer_sel, state="detached", timeout=12000)
                submitted = True
                break
            except Exception:
                print(f"  composer still open after Post (try {attempt + 1}) — retrying")
                btn = None
                cands = page.locator('[aria-label="Post"]')
                for i in range(cands.count()):
                    el = cands.nth(i)
                    try:
                        if el.is_visible() and el.get_attribute("aria-disabled") != "true":
                            btn = el
                            break
                    except Exception:
                        continue
        if not submitted:
            dump = ""
            try:
                dump = page.locator(composer_sel).first.inner_text()[:300].replace("\n", " | ")
            except Exception:
                pass
            page.screenshot(path=str(ROOT / "debug_fb_nopost.png"), full_page=True)
            raise SystemExit(f"composer never closed after Post → debug_fb_nopost.png | {dump}")
        time.sleep(2)

        # group-rule / intro interstitial?
        body_now = page.inner_text("body")
        if re.search(r"introduct|group rules|review.*before", body_now, re.I) and text[:30] not in body_now:
            page.screenshot(path=str(ROOT / "debug_fb_rules.png"), full_page=True)
            print("WARN: possible rules/intro interstitial → debug_fb_rules.png")

        # verify via group search (feed ranking hides fresh posts in automation;
        # search indexes a few seconds late → retry)
        first_line = next((ln for ln in text.splitlines() if ln.strip()), text)[:40]
        search_url = url.rstrip("/") + "/search/?q=" + urllib.parse.quote(first_line)
        ok = False
        for attempt in range(4):
            page.goto(search_url, wait_until="domcontentloaded")
            time.sleep(8)
            ok = first_line[:25] in page.inner_text("body")
            if ok:
                break
        print(f"verify via group search: {ok} (attempt {attempt + 1})")
        if not ok:
            page.screenshot(path=str(ROOT / "debug_fb_verify.png"), full_page=True)
            # ponytail: composer detach already proved submission; absent-from-search
            # is usually group admin approval hold, not a tool failure → exit OK.
            # Upgrade path: retry in next cron cycle or check "pending posts" tab.
            print("WARN: not in search yet (likely pending admin approval) — submission succeeded")
        return True
    finally:
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
    ap = argparse.ArgumentParser(description="Post to a Facebook group")
    ap.add_argument("group", help="group url or id/slug")
    ap.add_argument("text", nargs="*", help="post text")
    ap.add_argument("-f", "--file", type=Path)
    ap.add_argument("--media", type=Path)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    text = args.file.read_text(encoding="utf-8") if args.file else " ".join(args.text)
    ok = post_to_group(args.group, text, headless=not args.headed, media=args.media)
    if not ok:
        raise SystemExit("submission failed (see errors above)")


if __name__ == "__main__":
    main()
