#!/usr/bin/env python3
"""Capture delete call: open post URL, click More → Delete, record api calls.

Usage: capture_delete.py --url https://www.threads.com/@user/post/xxx [--state f]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
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
    rec = {"method": req.method, "url": req.url,
           "headers": dict(req.headers),
           "post_data": pd[:12000] if pd else None}
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


from cloakbrowser import launch as _cloak  # noqa: E402

b = _cloak(headless=True, args=["--disable-dev-shm-usage"])
ctx = b.new_context(storage_state=args.state, viewport={"width": 1280, "height": 1000})
page = ctx.new_page()
page.on("request", on_request)
page.on("response", on_response)

print("== open", args.url)
page.goto(args.url, wait_until="domcontentloaded")
time.sleep(4)
if "/post/" not in page.url:
    print("!! post already gone:", page.url)
else:
    # click More (the one near the post header)
    done = False
    mores = page.get_by_role("button", name="More")
    for i in range(mores.count()):
        bx = mores.nth(i)
        try:
            if not bx.is_visible():
                continue
            box = bx.bounding_box() or {}
            if not (30 <= box.get("y", 0) <= 500 and box.get("x", 0) > 500):
                continue
            bx.click(force=True)
            time.sleep(1.2)
            body = page.inner_text("body")
            if "Delete" in body:
                page.get_by_text("Delete", exact=True).first.click()
                time.sleep(1.5)
                dlg = page.locator("[role=dialog]")
                if dlg.count():
                    dlg.get_by_role("button", name="Delete").last.click(force=True)
                else:
                    page.get_by_role("button", name="Delete").last.click(force=True)
                time.sleep(5)
                print("== delete clicked")
                done = True
                break
            page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception as e:
            print("   more fail:", e)
    print("delete done:", done)

ts = time.strftime("%Y%m%d_%H%M%S")
fp = ROOT / "captures" / f"capture_delete_{ts}.json"
fp.write_text(json.dumps(events, indent=1))
print(f"== {len(events)} calls → {fp}")
for e in events:
    if "/api/" in e["url"] and ("delete" in e["url"].lower() or "graphql" not in e["url"]):
        print("   >>", e["method"], e.get("status"), e["url"])
ctx.close()
