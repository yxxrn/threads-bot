#!/usr/bin/env python3
"""Merge comments_new.json (fresh batch from the cron agent) into comments.json.

Model v2: each item carries a main comment plus an optional extra_comment.
Dedup is PER PART: main key = plain URL, extra key = URL + "#top_reply".
A part already in replied_urls.json is dropped; an item survives when at
least one part is fresh. Parts from duplicate URLs in the same batch are
merged into one item. Legacy v1 items with target=top_reply (extra text
stored as comment) are treated as extra-only items.

Prints: MERGED: +N items (+M parts), total T items in queue
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


def main_key(url):
    return url


def extra_key(url):
    return url + "#top_reply"

# GENERIC-REACTION BAN (2026-11-01, Amad: no generic sentences like
# "Thanks for sharing"). KEEP IN SYNC: auto_comment.py + merge_comments.py
# in BOTH instances. A reaction is banned when its FIRST sentence, after
# stripping punctuation/emoji and lowercasing, EQUALS a banned phrase, or
# starts with one followed only by short fillers (no word >= 4 chars).
# A phrase followed by real content words is NOT banned (it carries detail).
GENERIC_BANNED = [
    "thanks for sharing",
    "topiknya menarik banget",
    "interesting post",
    "wah menarik juga pembahasan ini",
    "kontennya menarik",
    "setuju banget sama komentar tadi",
    "isi kontennya bikin gue mikir",
    "wah ini sesuai banget sama yang lagi gue bahas",
    "postingannya bikin guampang baca",
    "ini cocok banget buat diobrolin bareng teman-teman",
    "ini mah ga kebohongan",
    "seru ya diskusiannya",
]

def is_generic_reaction(text):
    t = (text or "").strip()
    if not t:
        return False
    first = re.split(r"[.!?\n]+", t, maxsplit=1)[0].strip().lower()
    s = re.sub(r"[^\w\s]", "", first, flags=re.UNICODE).strip()
    s = re.sub(r"\s+", " ", s)
    for b in GENERIC_BANNED:
        if s == b:
            return True
        if s.startswith(b + " "):
            rest = s[len(b):].strip()
            if not any(len(w) >= 4 for w in rest.split()):
                return True
            return False
    return False


def normalize(c, replied):
    """Return (item, main_fresh, extra_fresh) with stale parts blanked."""
    url = c.get("url", "")
    if c.get("target") == "top_reply" and not c.get("extra_comment"):
        c = dict(c, extra_comment=c.get("comment", ""), comment="")
    main_fresh = bool(c.get("comment")) and main_key(url) not in replied
    extra_fresh = bool(c.get("extra_comment")) and extra_key(url) not in replied
    item = dict(c)
    if not main_fresh:
        item["comment"] = ""
    if not extra_fresh:
        item["extra_comment"] = ""
    if main_fresh and is_generic_reaction(item.get("comment", "")):
        print(f"DROP_GENERIC main: {url}")
        item["comment"] = ""
        main_fresh = False
    if extra_fresh and is_generic_reaction(item.get("extra_comment", "")):
        print(f"DROP_GENERIC extra: {url}")
        item["extra_comment"] = ""
        extra_fresh = False
    item.pop("target", None)
    return item, main_fresh, extra_fresh


replied = set(load(BOT / "replied_urls.json", []))
old = load(BOT / "comments.json", [])
new = load(BOT / "comments_new.json", [])

merged = []
by_url = {}
for c in old:
    if not c.get("url"):
        continue
    item, mf, ef = normalize(c, replied)
    if not mf and not ef:
        continue
    merged.append(item)
    by_url[item["url"]] = item

added_items = 0
added_parts = 0
for c in new:
    if not c.get("url"):
        continue
    item, mf, ef = normalize(c, replied)
    if not mf and not ef:
        continue
    cur = by_url.get(item["url"])
    if cur is None:
        merged.append(item)
        by_url[item["url"]] = item
        added_items += 1
        added_parts += (1 if mf else 0) + (1 if ef else 0)
    else:
        if mf and not cur.get("comment"):
            cur["comment"] = item["comment"]
            added_parts += 1
        if ef and not cur.get("extra_comment"):
            cur["extra_comment"] = item["extra_comment"]
            if not cur.get("top_reply") and item.get("top_reply"):
                cur["top_reply"] = item["top_reply"]
            added_parts += 1

(BOT / "comments.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1))
(BOT / "comments_new.json").write_text("[]")
print(f"MERGED: +{added_items} items (+{added_parts} parts), total {len(merged)} items in queue")
