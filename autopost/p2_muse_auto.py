#!/usr/bin/env python3
"""muse referral post — akun Threads (sekarang @clovebliz, state p3).

Interval acak 90-120 menit: cron tick tiap 30 menit, script gating sendiri
(stdout kosong = silent, tidak kirim apa-apa ke chat).
Hook bagian1 ganti tiap post (pool terpisah ID & EN), bahasa selang-seling
mulai dari EN: EN → ID → EN → ...
Media carousel tetap: 3 gambar (bagian1) + 2 gambar (bagian2).
State: .p2_muse_state.json {i, last_ts, gap_s}; i%2==0 → EN.
Cron: p2-muse (every 30m). Manual paksa post: p2_muse_auto.py --force
"""
import argparse
import json
import random
import time
from pathlib import Path

import post

HERE = Path(__file__).resolve().parent
STATE = HERE / ".p2_muse_state.json"
MEDIA = HERE / "media"

post.STATE = HERE / "storage_state_p3.json"
post.PROFILE_URL = "https://www.threads.com/@clovebliz"

HOOKS_ID = [
    "Masih nunggu waiting list muse.ai? Bisa di-skip kok.",
    "Masuk muse.ai tanpa antre waiting list, setup-nya cuma sekitar 5 menit.",
    "Banyak yang nanya gimana aku bisa masuk muse.ai lebih awal.",
    "Kalau kamu masih nunggu undangan muse.ai, mending baca ini.",
    "1 Milyar token muse masih bisa digratiskan, plus dapet VPS.",
    "Ternyata waiting list muse.ai itu opsional.",
]

HOOKS_EN = [
    "Still waiting on the muse.ai waiting list? You can skip it.",
    "Getting into muse.ai early takes about 5 minutes, no waiting list.",
    "A few people asked how I got into muse.ai this early.",
    "If you're still waiting for a muse.ai invite, read this instead.",
    "1 Billion muse tokens are still free to claim, and a VPS comes with it.",
    "Turns out the muse.ai waiting list is optional.",
]

BODY1_ID = (
    "Caranya:\n\n"
    "1. Download Pawxy di Play Store\n"
    "2. Connect ke VPN bawaan Pawxy, pilih region US\n"
    "3. Siapkan akun IG buat konfirmasi umur. Kalau gak punya IG, bisa pakai kartu debit Visa/MC (Jago, blu, bebas)\n"
    "4. Login ke muse.ai, masukin kode FB6X3E, dan 1 Milyar token gratis langsung masuk"
)

PART2_ID = (
    "5. Selain token, kalian juga dapat VPS gratis bawaan muse. Speknya CPU 2 vCPU AMD EPYC 9D25, RAM 7,7 GB\n"
    "6. Tokennya berlaku selamanya. Selama akun kalian hidup, VPS-nya ikut hidup terus, tanpa biaya bulanan\n\n"
    "Kodenya FB6X3E, masukin pas daftar biar tokennya langsung masuk akun kalian."
)

BODY1_EN = (
    "Here's how:\n\n"
    "1. Download Pawxy from the Play Store\n"
    "2. Connect to the VPN inside Pawxy and pick the US region\n"
    "3. Have an IG account ready for age verification. If you don't have one, a Visa/MC debit card works too (Jago, blu, any card)\n"
    "4. Log in to muse.ai, enter code FB6X3E, and 1 Billion free tokens land in your account"
)

PART2_EN = (
    "5. You also get a free VPS included with muse. Specs: 2 vCPU AMD EPYC 9D25, 7.7 GB RAM\n"
    "6. The free tokens never expire. As long as your account stays active, the VPS stays up too, with no monthly fees\n\n"
    "The code's FB6X3E, enter it when you sign up so the tokens go straight to your account."
)

MEDIA_PARTS = [
    [MEDIA / "p2-muse-1-pawxy.jpg", MEDIA / "p2-muse-2-vpn-us.jpg", MEDIA / "p2-muse-3-kode.jpg"],
    [MEDIA / "p2-muse-4-token.jpg", MEDIA / "p2-muse-5-spek-vps.jpg"],
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="post sekarang walau belum jatuh tempo")
    args = ap.parse_args()

    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text())
        except Exception:
            st = {}
    now = time.time()
    last = float(st.get("last_ts", 0) or 0)
    gap = float(st.get("gap_s", 0) or 0)
    if not args.force and last and (now - last) < gap:
        return  # belum jatuh tempo — silent (stdout kosong = tidak kirim pesan)

    i = int(st.get("i", 0))
    lang = "en" if i % 2 == 0 else "id"
    hook_pool = HOOKS_EN if lang == "en" else HOOKS_ID
    hook_i = (i // 2) % len(hook_pool)
    hook = hook_pool[hook_i]
    part1 = f"{hook}\n\n{BODY1_EN if lang == 'en' else BODY1_ID}"
    part2 = PART2_EN if lang == "en" else PART2_ID
    new_gap = random.uniform(90, 120) * 60

    print(f"lang: {lang} (i={i}, hook #{hook_i})")
    post.post_parts([part1, part2], media=MEDIA_PARTS)

    st["i"] = i + 1
    st["last_ts"] = now
    st["gap_s"] = new_gap
    STATE.write_text(json.dumps(st))
    print(f"posted ok. next in {new_gap / 60:.0f} min")


if __name__ == "__main__":
    main()
