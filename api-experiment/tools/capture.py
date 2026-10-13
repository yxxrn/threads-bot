#!/usr/bin/env python3
"""Capture Threads web API calls: record every /api/ request + response.

Usage:
  capture.py                # browse only (no post)
  capture.py --post "text"  # also post a test text, capture publish call
  capture.py --post-file f  # post from file

Output: capture_<ts>.json (list of {method,url,headers,post_data,status,resp})
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "storage_state.json"
OUT = ROOT / "captures"
OUT.mkdir(exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--post", default=None, help="text to post as test")
ap.add_argument("--post-file", default=None)
ap.add_argument("--headless", action="store_true")
ap.add_argument("--wait", type=int, default=8, help="seconds to browse before post")
args = ap.parse_args()

text = args.post
if args.post_file:
    text = Path(args.post_file).read_text()

events = []
pending = {}


def _norm_headers(h):
    keep = {
        "x-ig-app-id", "x-csrftoken", "x-asbd-id", "x-fb-lsd", "x-web-session-id",
        "content-type", "origin", "referer", "x-ig-www-claim", "x-bloks-version-id",
    }
    return {k: v for k, v in h.items() if k.lower() in keep or k.lower().startswith("x-")}


def on_request(req):
    if "/api/" not in req.url:
        return
    rid = req.url + str(time.time())
    try:
        pd = req.post_data
    except Exception:
        pd = None
    pending[rid] = {
        "method": req.method,
        "url": req.url,
        "headers": _norm_headers(req.headers),
        "post_data": pd[:8000] if pd else None,
        "ts": time.time(),
    }
    req._cap_rid = rid


def on_response(resp):
    try:
        req = resp.request
        rid = getattr(req, "_cap_rid", None)
        if not rid or rid not in pending:
            return
        rec = pending.pop(rid)
        rec["status"] = resp.status
        try:
            body = resp.text()
            rec["resp"] = body[:6000]
        except Exception:
            rec["resp"] = None
        events.append(rec)
    except Exception:
        pass


def main():
    from cloakbrowser import launch as _cloak_launch

    browser = _cloak_launch(headless=args.headless, args=["--disable-dev-shm-usage"])
    ctx = browser.new_context(
        storage_state=str(STATE) if STATE.exists() else None,
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    page.on("request", on_request)
    page.on("response", on_response)

    print("== browse homepage")
    page.goto("https://www.threads.com/", wait_until="domcontentloaded")
    time.sleep(args.wait)

    # scroll feed to trigger timeline calls
    for _ in range(3):
        page.mouse.wheel(0, 2000)
        time.sleep(2)

    # open profile
    print("== browse profile")
    page.goto("https://www.threads.com/@blooplyy_", wait_until="domcontentloaded")
    time.sleep(5)

    if text:
        print(f"== post test: {text[:60]!r}")
        # open composer
        opened = False
        for loc in (
            page.get_by_role("button", name="New thread"),
            page.get_by_role("link", name="New thread"),
            page.locator('[aria-label="New thread"]'),
        ):
            try:
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=5000)
                    time.sleep(2)
                    opened = True
                    break
            except Exception:
                continue
        if not opened:
            print("!! composer not found")
        else:
            # type into first contenteditable
            ed = page.locator('[contenteditable="true"]').first
            ed.click()
            time.sleep(0.5)
            page.keyboard.type(text, delay=15)
            time.sleep(1.5)
            # find Post button
            posted = False
            for name in ("Post", "Post now"):
                try:
                    b = page.get_by_role("button", name=name)
                    if b.count():
                        b.last.click(timeout=5000)
                        posted = True
                        break
                except Exception:
                    continue
            print("posted:", posted)
            time.sleep(12)
            page.screenshot(path=str(ROOT / "capture_after_post.png"))

    # save
    ts = time.strftime("%Y%m%d_%H%M%S")
    fp = OUT / f"capture_{ts}.json"
    fp.write_text(json.dumps(events, indent=1))
    print(f"== {len(events)} api calls → {fp}")
    for e in events:
        print(f"  {e['method']:4s} {e.get('status')} {e['url'][:110]}")

    try:
        if page.get_by_role("button", name="New thread").count():
            ctx.storage_state(path=str(STATE))
    except Exception:
        pass
    ctx.close()


main()
