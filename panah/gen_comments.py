#!/usr/bin/env python3
"""Generate comments for candidates and write to comments_new.json."""
import json
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Load candidates
candidates = json.loads((BOT / "candidates.json").read_text())

# Generate comments
comments = []
for c in candidates:
    url = c["url"]
    author = c["author"]
    lang = c["lang"]

    if lang == "id":
        comment = "Latihan speaking bareng teman seru juga ya, jadi gak cuma teori doang.\n\nKalau video bahasanya mau lebih rapi, Blooply bisa bantu potong video panjang jadi shorts otomatis, ada di profil."
    else:
        comment = "This is super helpful for UGC creators looking for inspiration. Having everything in one library saves so much research time.\n\nIf you ever need to cut long recordings into shorts, Blooply does it automatically, it's on my profile."

    comments.append({"url": url, "author": author, "lang": lang, "comment": comment})

# Write comments_new.json
(BOT / "comments_new.json").write_text(json.dumps(comments, ensure_ascii=False, indent=2))
print(f"Written {len(comments)} comments to comments_new.json")
