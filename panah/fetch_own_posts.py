#!/usr/bin/env python3
"""Tarik post sendiri (@blooplyy_) dari halaman profil Threads.

Output: /tmp/blooply_posts.json  -> [{code, url, caption, is_reply, parent_code, media:[...]}]
Juga dump HTML mentah ke /tmp/blooply_profile.html untuk diagnosa.
"""
import json
import re
import sys
from pathlib import Path

from curl_cffi import requests as creq

BOT = Path(__file__).resolve().parent

STATE = str(BOT / "state.json")
USER = sys.argv[1] if len(sys.argv) > 1 else "blooplyy_"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

st = json.loads(Path(STATE).read_text())
cookies = {c["name"]: c["value"] for c in st["cookies"] if "threads.com" in c["domain"]}

s = creq.Session(impersonate="chrome")
r = s.get(f"https://www.threads.com/@{USER}",
          cookies=cookies, headers={"user-agent": UA}, timeout=45)
html = r.text
Path("/tmp/blooply_profile.html").write_text(html)

print("status:", r.status_code, "| bytes:", len(html))
print("login wall:", "Log in" in html[:4000])
print("csrf:", cookies.get("csrftoken", "")[:12], "| ds_user_id:", cookies.get("ds_user_id"))

# caption texts in document order
caps = []
for m in re.finditer(r'"caption":\{"text":"((?:[^"\\]|\\.)*)"', html):
    try:
        caps.append(json.loads('"' + m.group(1) + '"'))
    except Exception:
        caps.append(m.group(1))

# codes in document order (first code per post block is the post itself)
codes = re.findall(r'"code":"([A-Za-z0-9_-]{8,})"', html)
print("\ncaption blobs:", len(caps), "| code hits:", len(codes))

print("\n=== 20 caption pertama (urutan dokumen) ===")
for i, c in enumerate(caps[:20], 1):
    one = c.replace("\n", " ⏎ ")
    print(f"[{i:02d}] {one[:180]}")

Path("/tmp/blooply_caps.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1))
Path("/tmp/blooply_codes.json").write_text(json.dumps(codes, ensure_ascii=False, indent=1))
print("\ndisimpan: /tmp/blooply_caps.json /tmp/blooply_codes.json /tmp/blooply_profile.html")