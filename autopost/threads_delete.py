#!/usr/bin/env python3
"""Hapus 1 post Threads via UI (menu More → Delete → confirm).

Usage: threads_delete.py --state storage_state_p2.json --url https://www.threads.com/@user/post/xxx
"""
import argparse
import time
from pathlib import Path

from cloakbrowser import launch

ROOT = Path(__file__).resolve().parent


def delete_current(page) -> str:
    mores = page.get_by_role("button", name="More")
    for i in range(mores.count()):
        bx = mores.nth(i)
        try:
            if not bx.is_visible():
                continue
            box = bx.bounding_box() or {}
            if not (40 <= box.get("y", 0) <= 400 and box.get("x", 0) > 500):
                continue
            bx.click(force=True)
            time.sleep(1.0)
            body = page.inner_text("body")
            if "Delete" in body:
                page.get_by_text("Delete", exact=True).first.click()
                time.sleep(1.2)
                dlg = page.locator("[role=dialog]")
                if dlg.count():
                    dlg.get_by_role("button", name="Delete").last.click(force=True)
                else:
                    page.get_by_role("button", name="Delete").last.click(force=True)
                time.sleep(3)
                return "ok"
            page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            continue
    return "fail"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="storage_state.json")
    ap.add_argument("--url", required=True, help="permalink post")
    args = ap.parse_args()

    b = launch(headless=True, args=["--disable-dev-shm-usage"])
    c = b.new_context(storage_state=args.state, viewport={"width": 1280, "height": 1200})
    page = c.new_page()
    page.goto(args.url, wait_until="domcontentloaded")
    time.sleep(3)
    if "/post/" not in page.url:
        print("post sudah tidak ada (redirect):", page.url)
        c.close(); b.close(); return
    print("delete:", delete_current(page))
    c.close(); b.close()


if __name__ == "__main__":
    main()
