#!/usr/bin/env python3
"""Capture chain post (2 parts) — reuse post.py flow, record api calls.

Usage: capture_chain.py --part "text1" --part "text2" [--state f] [--headless]
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
ap.add_argument("--part", action="append", required=True)
ap.add_argument("--state", default=str(ROOT / "storage_state_p3.json"))
ap.add_argument("--headless", action="store_true", default=True)
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
    rec = {"method": req.method, "url": req.url,
           "post_data": pd[:15000] if pd else None}
    pending[id(req)] = rec
    events.append(rec)


def on_response(resp):
    rec = pending.pop(id(resp.request), None)
    if not rec:
        return
    rec["status"] = resp.status
    try:
        rec["resp"] = resp.text()[:3000]
    except Exception:
        rec["resp"] = None


from cloakbrowser import launch as _cloak  # noqa: E402

b = _cloak(headless=args.headless, args=["--disable-dev-shm-usage"])
ctx = b.new_context(storage_state=args.state, viewport={"width": 1280, "height": 950})
page = ctx.new_page()
page.on("request", on_request)
page.on("response", on_response)
page.set_default_timeout(45_000)

page.goto("https://www.threads.com/", wait_until="domcontentloaded")
time.sleep(2.5)
P._dismiss(page)
P._open_composer(page)
parts = args.part
P._fill_slot(page, 0, parts[0])
for i, part in enumerate(parts[1:], start=1):
    P._add_slot(page)
    P._fill_slot(page, i, part)
P._commit_all_slots(page, len(parts))
page.locator('[contenteditable="true"]').first.click()
time.sleep(0.3)
ok = P._wait_post_enabled(page, 30)
print("post enabled:", ok)
if ok:
    P._click_post(page)
    time.sleep(18)
    print("clicked + waited")

ts = time.strftime("%Y%m%d_%H%M%S")
fp = ROOT / "captures" / f"capture_chain_{ts}.json"
fp.write_text(json.dumps(events, indent=1))
print(f"== {len(events)} calls → {fp}")
for e in events:
    if "configure" in e["url"]:
        print("   >> configure:", e.get("status"))
        print("      ", (e.get("post_data") or "")[:300])
ctx.close()
