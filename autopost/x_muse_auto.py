#!/usr/bin/env python3
"""muse referral tweet untuk X — interval acak 90-120 menit.

Cron tick tiap 30 menit; script gating sendiri (stdout kosong = silent,
tidak kirim pesan ke chat). Opener ganti tiap post, EN/ID selang-seling
mulai EN. 1 tweet (X tanpa chain), weighted <=280 (domain dihitung URL).
Media: 1 foto (sheet kode KGG3P8). State: .x_muse_state.json {i, last_ts,
gap_s}; i%2==0 = EN. Manual paksa post: x_muse_auto.py --force
"""
import argparse
import json
import random
import time
from pathlib import Path

from x_post import _weighted_len, post_tweet

HERE = Path(__file__).resolve().parent
STATE = HERE / ".x_muse_state.json"
PHOTO = HERE / "media" / "p2-muse-3-kode.jpg"

OPENERS_EN = [
    "Skip the muse.ai waiting list.",
    "muse.ai is still waitlist-only.",
    "Got into muse.ai early, here's how.",
    "The muse.ai waitlist is optional.",
    "How to enter muse.ai without waiting.",
]

OPENERS_ID = [
    "Cara masuk muse.ai tanpa waiting list.",
    "muse.ai masih pakai waiting list.",
    "Udah masuk muse.ai duluan, ini caranya.",
    "Waiting list muse.ai itu opsional.",
    "Masuk muse.ai tanpa antre, 5 menit doang.",
]

STEPS_EN = (
    "1) Pawxy from the Play Store\n"
    "2) Connect via US VPN\n"
    "3) Have an IG account ready (or a Visa/MC card)\n"
    "4) Sign in at muse.ai, enter code KGG3P8\n"
    "5) Bonus 3B tokens: t.me/satudigitalbot?start=ref1323141169"
)

TAIL_EN = "1B tokens + free VPS."

STEPS_ID = (
    "1) Pawxy di Play Store\n"
    "2) Connect VPN region US\n"
    "3) Siapkan akun IG (atau kartu debit Visa/MC)\n"
    "4) Login muse.ai, masukin kode KGG3P8\n"
    "5) Bonus 3 Milyar token: t.me/satudigitalbot?start=ref1323141169"
)

TAIL_ID = "1 Milyar token + VPS."


def build(i: int) -> tuple[str, str, int]:
    """Return (lang, text, opener_idx) untuk post ke-i."""
    lang = "en" if i % 2 == 0 else "id"
    pool = OPENERS_EN if lang == "en" else OPENERS_ID
    oi = (i // 2) % len(pool)
    steps = STEPS_EN if lang == "en" else STEPS_ID
    tail = TAIL_EN if lang == "en" else TAIL_ID
    return lang, f"{pool[oi]}\n\n{steps}\n\n{tail}", oi


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
    lang, text, oi = build(i)
    w = _weighted_len(text)
    if w > 280:
        raise SystemExit(f"muse tweet too long: weighted {w} > 280 (lang={lang}, opener#{oi})")
    new_gap = random.uniform(90, 120) * 60
    post_tweet(text, media=PHOTO)
    st["i"] = i + 1
    st["last_ts"] = now
    st["gap_s"] = new_gap
    STATE.write_text(json.dumps(st))
    print(f"muse tweet ok: lang={lang} opener#{oi} ({w}/280), next in {new_gap / 60:.0f} min")


if __name__ == "__main__":
    main()
