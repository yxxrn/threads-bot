#!/usr/bin/env python3
"""Scheduled Blooply promo for X: single tweet + photo, hook rotates each post.

Round-robin state di .x_promo_state.json (independen dari Threads).
X = 1 post (tidak ada chain); weighted length dijaga <=280 (URL =23 char).
"""
import json
from pathlib import Path

from x_post import _weighted_len, post_tweet

HERE = Path(__file__).resolve().parent
STATE = HERE / ".x_promo_state.json"
PHOTO = HERE / "media" / "blooply-library.jpg"

HOOKS = [
    "Potong video panjang jadi clip 9:16.",
    "Masih potong clip manual satu-satu?",
    "Satu video, jadi bahan beberapa clip.",
    "Klip harian gak harus makan seharian.",
    "Video panjang sayang kalau cuma ditonton.",
    "Edit klip itu tugas paling ngebosenin.",
    "Ide konten banyak, waktu edit kurang.",
    "Bikin Shorts dari video panjang harusnya gampang.",
]

BODY = (
    "Blooply di PC kamu: caption karaoke, hook, watermark, "
    "upload ke Shorts/Reels/TikTok. AI atau timestamp manual."
)

TAIL = (
    "Lisensi selamanya + update berkala.\n"
    "app.blooply.id · clip.blooply.id\n"
    "Voucher TDTDGTYGRLD2 (5rb off)"
)


def main() -> None:
    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text())
        except Exception:
            st = {}
    i = int(st.get("i", 0)) % len(HOOKS)
    st["i"] = i + 1
    STATE.write_text(json.dumps(st))
    hook = HOOKS[i]
    text = f"{hook}\n\n{BODY}\n\n{TAIL}"
    w = _weighted_len(text)
    if w > 280:
        raise SystemExit(f"hook[{i}] weighted {w} > 280 — trim HOOKS/BODY")
    post_tweet(text, media=PHOTO)
    print(f"hook[{i}]: {hook}")


if __name__ == "__main__":
    main()
