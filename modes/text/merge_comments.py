#!/usr/bin/env python3
"""Merge comments_new.json (fresh batch from the cron agent) into comments.json.

- drops entries whose URL is already in replied_urls.json
- dedupes by URL
- clears comments_new.json afterwards
Prints: MERGED: +N new, total M in queue
"""
import json
from pathlib import Path

BOT = Path(__file__).resolve().parent


def load(p, default):
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return default


replied = set(load(BOT / "replied_urls.json", []))
old = load(BOT / "comments.json", [])
new = load(BOT / "comments_new.json", [])

merged = [c for c in old if c.get("url") and c["url"] not in replied]
seen = {c["url"] for c in merged}
added = 0
for c in new:
    u = c.get("url")
    if not u or not c.get("comment") or u in seen or u in replied:
        continue
    merged.append(c)
    seen.add(u)
    added += 1

(BOT / "comments.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1))
(BOT / "comments_new.json").write_text("[]")
print(f"MERGED: +{added} new, total {len(merged)} in queue")
