#!/usr/bin/env python3
"""Ambil pasangan (post utama, reply sendiri) dari halaman profil Threads.

Baca HTML yang sudah di-dump fetch_own_posts.py, lalu parse blok
"thread_items" sebagai JSON sungguhan (bukan regex) supaya urutan dan
batas antar-post tidak kabur.

Output: /tmp/blooply_pairs.json
  [{code, url, text, reply_code, reply_text, media:[...]}]
"""
import json
import re
from pathlib import Path

HTML = Path("/tmp/blooply_profile.html")
USER = "blooplyy_"
OUT = Path("/tmp/blooply_pairs.json")

html = HTML.read_text(errors="replace")
dec = json.JSONDecoder()

threads = []
pos = 0
marker = '"thread_items":'
while True:
    i = html.find(marker, pos)
    if i < 0:
        break
    j = html.find("[", i)
    if j < 0:
        break
    try:
        items, end = dec.raw_decode(html, j)
    except Exception:
        pos = i + len(marker)
        continue
    if isinstance(items, list) and items:
        threads.append(items)
    pos = end

print(f"thread_items blocks: {len(threads)}")


def post_of(item):
    p = (item or {}).get("post") or {}
    return p


def txt_of(p):
    return ((p.get("caption") or {}).get("text") or "").strip()


pairs = {}
order = []
for items in threads:
    if not items:
        continue
    head = post_of(items[0])
    if (head.get("user") or {}).get("username") != USER:
        continue
    code = head.get("code")
    if not code:
        continue
    body = txt_of(head)
    if not body:
        continue
    media = []
    for m in (head.get("image_versions2") or {}).get("candidates", [])[:1]:
        media.append(m.get("url"))
    reply_code, reply_text = None, ""
    for it in items[1:]:
        rp = post_of(it)
        if (rp.get("user") or {}).get("username") == USER and txt_of(rp):
            reply_code, reply_text = rp.get("code"), txt_of(rp)
            break
    if code not in pairs:
        order.append(code)
        pairs[code] = {
            "code": code,
            "url": f"https://www.threads.com/@{USER}/post/{code}",
            "text": body,
            "reply_code": reply_code,
            "reply_text": reply_text,
            "media": [u for u in media if u],
        }

out = [pairs[c] for c in order]
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"post milik @{USER}: {len(out)}")
with_reply = sum(1 for p in out if p["reply_text"])
print(f"punya reply (p2): {with_reply}")
print()
for i, p in enumerate(out[:12], 1):
    head = p["text"].split("\n")[0][:70]
    print(f"[{i:02d}] {p['code']} | {head}")
    if p["reply_text"]:
        print(f"     p2: {p['reply_text'].splitlines()[0][:70]}")
print(f"\ndisimpan: {OUT}")