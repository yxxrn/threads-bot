#!/usr/bin/env python3
"""Capture v2 — reuse post.py's proven composer flow, record ALL api calls.

Usage: capture2.py --post "text"  [--headless]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import post as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--post", required=True)
ap.add_argument("--headless", action="store_true", default=False)
ap.add_argument("--state", default=str(ROOT / "storage_state.json"))
args = ap.parse_args()

events = []
pending = {}


def on_request(req):
    if "/api/" not in req.url:
        return
    try:
        pd = req.post_data
    except Exception:
        pd = None
    rec = {
        "method": req.method,
        "url": req.url,
        "headers": dict(req.headers),
        "post_data": pd[:12000] if pd else None,
    }
    pending[id(req)] = rec
    events.append(rec)


def on_response(resp):
    rec = pending.pop(id(resp.request), None)
    if not rec:
        return
    rec["status"] = resp.status
    try:
        rec["resp"] = resp.text()[:8000]
    except Exception:
        rec["resp"] = None


from cloakbrowser import launch as _cloak_launch  # noqa: E402

browser = _cloak_launch(headless=args.headless, args=["--disable-dev-shm-usage"])
ctx = browser.new_context(
    storage_state=args.state, viewport={"width": 1280, "height": 900})
page = ctx.new_page()
page.on("request", on_request)
page.on("response", on_response)
page.set_default_timeout(45_000)

print("== open home")
page.goto("https://www.threads.com/", wait_until="domcontentloaded")
time.sleep(2.5)
P._dismiss(page)
print("== open composer")
P._open_composer(page)
print("== fill text")
P._fill_slot(page, 0, args.post)
page.locator('[contenteditable="true"]').first.click()
time.sleep(0.4)
print("== wait post enabled")
ok = P._wait_post_enabled(page, 30)
print("   post enabled:", ok)
if ok:
    P._click_post(page)
    print("== clicked post, waiting 15s for publish calls")
    time.sleep(15)
else:
    page.screenshot(path=str(ROOT / "capture2_disabled.png"), full_page=True)

ts = time.strftime("%Y%m%d_%H%M%S")
fp = ROOT / "captures" / f"capture2_{ts}.json"
fp.write_text(json.dumps(events, indent=1))
print(f"== {len(events)} calls → {fp}")
try:
    if page.get_by_role("button", name="New thread").count():
        ctx.storage_state(path=args.state)
except Exception:
    pass
ctx.close()
