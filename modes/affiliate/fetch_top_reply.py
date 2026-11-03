#!/usr/bin/env python3
"""Read-only helper: fetch the current top reply of a Threads post.

Usage: fetch_top_reply.py <post_url>
Prints one JSON line:
  {"url": ..., "has_replies": true, "top_reply_url": ..., "top_reply_author": ...,
   "top_reply_text": ..., "reply_button": "svg"|"position"|null,
   "reply_count": <distinct reply permalinks rendered>}
or {"url": ..., "has_replies": false, "reason": ...} when there is no reply
(or the main post cannot be located).

Model v2: used by the refill agent to write the EXTRA comment of an item
(main reply is always written; extra is only attempted at posting time when
the thread is busy). The top_reply snapshot is context only: at posting
time the extra falls back to whatever top reply is visible then, so the
snapshot is never used as a guard. NEVER posts, likes, follows, or writes
any queue file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("ac", BOT / "auto_comment.py")
ac = importlib.util.module_from_spec(spec)
sys.modules["ac"] = ac
spec.loader.exec_module(ac)


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: fetch_top_reply.py <post_url>"}))
        return 2
    url = sys.argv[1]
    from cloakbrowser import launch

    browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
    try:
        ctx = browser.new_context(storage_state=str(ac.STATE))
        page = ctx.new_page()
        page.goto(url, timeout=90000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        try:
            n = ac.count_replies(page, url)
        except Exception:
            n = 0
        info = ac.find_top_reply_info(page, url)
        info["reply_count"] = n
    finally:
        try:
            browser.close()
        except Exception:
            pass
    out = {"url": url}
    out.update(info)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
