#!/usr/bin/env python3
"""Scheduled Blooply promo untuk Facebook GROUPS.

Tiap run post ke SEMUA grup di fb_groups_target.txt (default, jeda acak
antargrup biar kena deteksi spam), hook diganti per run (round-robin).
URL pakai * (bukan titik) + keterangan * = titik.
State: .fb_promo_state.json
"""
import json
import random
import time
from pathlib import Path

from fb_post import post_to_group

HERE = Path(__file__).resolve().parent
STATE = HERE / ".fb_promo_state.json"
TARGETS = HERE / "fb_groups_target.txt"
PHOTO = HERE / "media" / "blooply-library.jpg"

HOOKS = [
    "Potong video panjang jadi clip 9:16, tanpa editor ribet.",
    "Masih potong clip manual satu-satu?",
    "Satu video YouTube bisa jadi bahan beberapa clip.",
    "Klip harian gak harus makan seharian.",
    "Video panjang sayang kalau cuma ditonton.",
    "Edit klip itu tugas paling ngebosenin.",
    "Ide konten banyak, waktu edit kurang.",
    "Bikin Shorts/Reels dari video panjang harusnya gampang.",
]

BODY = (
    "Blooply: app PC buat motong video YouTube jadi clip 9:16 siap upload. "
    "Caption karaoke, wajah tetap keikut direframe, hook + watermark. "
    "AI nyari momen atau pilih timestamp sendiri. Semua lokal di PC kamu, "
    "video gak keluar dari komputer.\n\n"
    "Sekali beli, lisensi selamanya + update.\n"
    "Demo UI + hasil clip: app*blooply*id\n"
    "Lisensi: clip*blooply*id\n"
    "(* = titik, ganti * jadi .)\n"
    "Voucher: TDTDGTYGRLD2 (potong 5rb)"
)


def load_targets() -> list[tuple[str, str]]:
    out = []
    for line in TARGETS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        gid, _, name = line.partition("|")
        out.append((gid.strip(), name.strip() or gid.strip()))
    return out


def main() -> None:
    groups = load_targets()
    if not groups:
        raise SystemExit("fb_groups_target.txt kosong")
    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text())
        except Exception:
            st = {}
    hi = int(st.get("h", 0))
    hook = HOOKS[hi % len(HOOKS)]
    st["h"] = hi + 1
    STATE.write_text(json.dumps(st))
    text = f"{hook}\n\n{BODY}"
    print(f"hook[{hi % len(HOOKS)}]: {hook}")
    print(f"targets: {len(groups)} grup")

    results = []
    for idx, (gid, gname) in enumerate(groups, 1):
        print(f"[{idx}/{len(groups)}] {gname} ({gid})")
        try:
            ok = post_to_group(gid, text, media=PHOTO)
            results.append((gname, "ok" if ok else "warn:verify"))
        except SystemExit as e:
            results.append((gname, f"fail: {e}"))
            print(f"  FAIL: {e}")
        except Exception as e:
            results.append((gname, f"fail: {type(e).__name__}"))
            print(f"  FAIL: {type(e).__name__}: {e}")
        if idx < len(groups):
            time.sleep(random.uniform(20, 45))  # jeda antargrup

    ok_n = sum(1 for _, r in results if r == "ok")
    print("--- summary ---")
    for gname, r in results:
        print(f"  {r:12} {gname}")
    print(f"ok {ok_n}/{len(results)}")
    if ok_n == 0:
        raise SystemExit("semua grup gagal")


if __name__ == "__main__":
    main()
