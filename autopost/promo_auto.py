#!/usr/bin/env python3
"""Scheduled Blooply promo: 2-part chain, hook rotates every post.

Hook di bagian 1 berganti round-robin (state di .promo_state.json)
biar tiap post tidak identik. Isi + link + voucher tetap.
"""
import json
from pathlib import Path

from post import post_parts

HERE = Path(__file__).resolve().parent
STATE = HERE / ".promo_state.json"

HOOKS = [
    "Video panjang tapi males ngedit klipnya? 😅",
    "Satu video YouTube bisa jadi bahan beberapa clip, lho.",
    "Masih potong clip manual satu-satu?",
    "Ide kontennya banyak, waktu ngeditnya yang kurang.",
    "Klip buat Shorts harusnya nggak bikin seharian.",
    "Jangan biarkan video panjang cuma ditonton orang.",
    "Clip harian itu harusnya cepat, bukan tugas sampingan.",
    "Buka editor berat-berat cuma buat potong video? Skip.",
]

BODY1 = (
    "Blooply: app PC buat motong video YouTube jadi clip 9:16 siap upload. "
    "Caption karaoke, wajah tetap keikut direframe, hook + watermark, tinggal render. "
    "Mau AI cariin momennya atau pilih timestamp sendiri, dua-duanya bisa. "
    "Lokal semua di PC kamu, video nggak keluar dari komputer."
)

PART2 = (
    "Sekali beli, lisensi berlaku selamanya, plus update berkala.\n\n"
    "Demo UI + hasil clip: app.blooply.id\n"
    "Lisensi: clip.blooply.id\n\n"
    "Voucher:\n"
    "TDTDGTYGRLD2 (potong 5rb)"
)

PHOTO = HERE / "media" / "blooply-library.jpg"


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
    parts = [f"{hook}\n\n{BODY1}", PART2]
    post_parts(parts, media=[PHOTO, None])
    print(f"hook[{i}]: {hook}")


if __name__ == "__main__":
    main()
