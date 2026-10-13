#!/usr/bin/env python3
"""Capture media upload flow: post 1 image via browser, record ALL api calls.

Usage: capture_media.py --image /tmp/test.jpg [--state f]
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
ap.add_argument("--image", required=True)
ap.add_argument("--caption", default="[TEST MEDIA API] akan dihapus")
ap.add_argument("--state", default=str(ROOT / "storage_state_p3.json"))
args = ap.parse_args()

events = []
pending = {}


def on_request(req):
    u = req.url
    # capture: graphql, media upload/rupload, configure, rupload.facebook
    if not ("/api/" in u or "rupload" in u or "upload" in u.lower()):
        return
    try:
        pd = req.post_data
    except Exception:
        pd = None
    try:
        body = req.post_data_buffer
    except Exception:
        body = None
    rec = {
        "method": req.method,
        "url": u,
        "headers": {k: v for k, v in req.headers.items()
                    if k.lower().startswith("x-") or k.lower() in
                    ("content-type", "origin", "referer", "content-length",
                     "offset", "x-entity-name", "x-entity-length",
                     "x-entity-type", "x-instagram-rupload-params")},
        "post_data": pd[:8000] if pd else None,
        "body_size": len(body) if body else None,
    }
    pending[id(req)] = rec
    events.append(rec)


def on_response(resp):
    rec = pending.pop(id(resp.request), None)
    if not rec:
        return
    rec["status"] = resp.status
    try:
        rec["resp"] = resp.text()[:5000]
    except Exception:
        rec["resp"] = None


from cloakbrowser import launch as _cloak  # noqa: E402

b = _cloak(headless=True, args=["--disable-dev-shm-usage"])
ctx = b.new_context(storage_state=args.state, viewport={"width": 1280, "height": 950})
page = ctx.new_page()
page.on("request", on_request)
page.on("response", on_response)
page.set_default_timeout(60_000)

page.goto("https://www.threads.com/", wait_until="domcontentloaded")
time.sleep(2.5)
P._dismiss(page)
P._open_composer(page)
P._fill_slot(page, 0, args.caption)
P._attach_media(page, [Path(args.image)], 0)
P._commit_all_slots(page, 1)
page.locator('[contenteditable="true"]').first.click()
time.sleep(0.3)
ok = P._wait_post_enabled(page, 60)
print("post enabled:", ok)
if ok:
    P._click_post(page)
    time.sleep(20)

ts = time.strftime("%Y%m%d_%H%M%S")
fp = ROOT / "captures" / f"capture_media_{ts}.json"
fp.write_text(json.dumps(events, indent=1))
print(f"== {len(events)} calls → {fp}")
for e in events:
    tag = ""
    if "rupload" in e["url"]:
        tag = " <<< UPLOAD"
    elif "configure" in e["url"]:
        tag = " <<< CONFIGURE"
    print(f"  {e['method']} {e.get('status')} {e['url'][:100]}{tag}")
ctx.close()
