#!/usr/bin/env python3
"""Merge comments_new.json (fresh batch from the cron agent) into comments.json.

- drops entries whose URL is already in replied_urls.json
- dedupes by URL
- clears comments_new.json afterwards
Prints: MERGED: +N new, total M in queue
"""
import json
import re
from pathlib import Path

BOT = Path(__file__).resolve().parent


def load(p, default):
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return default


# URL GUARD 2026-11-13: URL post Threads yang valid bentuknya persis
# https://www.threads.com/@<handle>/post/<id> (handle diawali @). Entri dengan
# URL malformed tidak pernah masuk antrean (lihat is_valid_thread_url di
# auto_comment.py — definisi kanonis; regex ini salinan yang sama).
THREAD_URL_RE = re.compile(r"^https://www\.threads\.com/@[A-Za-z0-9_][A-Za-z0-9._]*/post/[A-Za-z0-9_-]+/?$")


def is_valid_thread_url(url) -> bool:
    return isinstance(url, str) and bool(THREAD_URL_RE.match(url))


replied = set(load(BOT / "replied_urls.json", []))
old = load(BOT / "comments.json", [])
new = load(BOT / "comments_new.json", [])

merged = [c for c in old if c.get("url") and c["url"] not in replied]
seen = {c["url"] for c in merged}
added = 0
skipped_bad = 0
for c in new:
    u = c.get("url")
    if not u or not c.get("comment") or u in seen or u in replied:
        continue
    if not is_valid_thread_url(u):
        skipped_bad += 1  # URL GUARD 2026-11-13: malformed URL never enters the queue
        continue
    merged.append(c)
    seen.add(u)
    added += 1

(BOT / "comments.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1))
(BOT / "comments_new.json").write_text("[]")
print(f"MERGED: +{added} new, total {len(merged)} in queue (skipped {skipped_bad} malformed URLs)")
