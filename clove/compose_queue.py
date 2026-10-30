#!/usr/bin/env python3
"""Susun clove_queue.json: tutorial Muse ID/EN selang-seling dengan repo GitHub.

Semua teks dan path media bisa dipindah mesin lewat argumen --media.
Contoh:
  python compose_queue.py --media ~/clove/media --out ~/clove/clove_queue.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIB = timezone(timedelta(hours=7))

MUSE = {
 "t1": {
  "label": "Muse token tidak kedaluwarsa",
  "id": (
   "Ada satu bagian di Muse yang jarang dibuka: Penggunaan.\n\n"
   "Di situ kelihatan paket gratis, batas mingguan, dan token tambahan. Token tambahan nggak pernah kedaluwarsa, "
   "jadi tetap ada walaupun kuota mingguan reset.\n\n"
   "1. Buka Muse, masuk ke Pengaturan\n"
   "2. Pilih Penggunaan\n"
   "3. Lihat baris Token tambahan, ada sisa token dan statusnya\n"
   "4. Bandingkan dengan kuota mingguan yang reset tiap pekan\n\n"
   "Sisanya di bawah."),
  "en": (
   "There is one Muse section most people never open: Usage.\n\n"
   "It shows the free plan, the weekly limit, and extra tokens. Extra tokens never expire, "
   "so they stay even when the weekly quota resets.\n\n"
   "1. Open Muse, go to Settings\n"
   "2. Pick Usage\n"
   "3. Look at the Extra tokens row, it shows the balance and its status\n"
   "4. Compare it with the weekly quota that resets every week\n\n"
   "More below."),
  "id2": (
   "5. Kalau punya kode referral teman, tukar di halaman yang sama\n"
   "6. Setelah ditukar, token langsung masuk dan berlaku permanen\n"
   "7. Cek lagi seminggu kemudian, angkanya harus tetap sama\n\n"
   "Token tambahan aman selama akun aktif, nggak perlu buru-buru dihabiskan."),
  "en2": (
   "5. If you have a friend's referral code, redeem it on the same page\n"
   "6. Once redeemed the tokens land instantly and stay permanent\n"
   "7. Check again a week later, the number should be unchanged\n\n"
   "Extra tokens are safe as long as the account is active, no rush to burn them."),
  "media": "muse-settings.jpg", "media2": "p2-muse-4-token.jpg",
 },
 "t2": {
  "label": "Muse undang teman 1 miliar token",
  "id": (
   "Di Muse ada menu Undang teman. Tiap teman yang menukar kode, kalian berdua dapat token Muse senilai 1 miliar.\n\n"
   "Syaratnya cuma satu: kode harus ditukar di Pengaturan dalam 48 jam setelah teman bergabung.\n\n"
   "1. Buka Undang teman di Muse\n"
   "2. Salin kode yang muncul\n"
   "3. Kirim lewat WhatsApp atau Messenger\n"
   "4. Minta teman tukar kode di Pengaturan sebelum 48 jam\n\n"
   "Sisanya di bawah."),
  "en": (
   "Muse has an Invite friends menu. For every friend who redeems your code, both of you get 1 billion Muse tokens.\n\n"
   "Only one catch: the code must be redeemed in Settings within 48 hours of the friend joining.\n\n"
   "1. Open Invite friends in Muse\n"
   "2. Copy the code shown there\n"
   "3. Send it over WhatsApp or Messenger\n"
   "4. Ask them to redeem it in Settings before 48 hours pass\n\n"
   "More below."),
  "id2": (
   "5. Token masuk ke akun kalian berdua setelah kode ditukar\n"
   "6. Di halaman itu kelihatan berapa teman yang sudah menukar dan total token yang didapat\n"
   "7. Sisa slot penggunaan juga tertera, jadi tahu kapan berhenti\n\n"
   "Kode yang sudah dipakai nggak bisa dipakai dua kali."),
  "en2": (
   "5. Tokens land in both accounts once the code is redeemed\n"
   "6. That page also shows how many friends redeemed and the total tokens earned\n"
   "7. Remaining invite slots are listed too, so you know when to stop\n\n"
   "A code that has been used cannot be reused."),
  "media": "muse-latest-4.jpg", "media2": "p2-muse-3-kode.jpg",
 },
 "t3": {
  "label": "Muse goals dan ide feed",
  "id": (
   "Selain chat, Muse punya dua bagian yang sering kelewat: Tujuan dan Ide & feed.\n\n"
   "Tujuan buat ngerencanain target jangka panjang, Ide & feed ngasih saran hal yang bisa dibangun plus ringkasan berkala.\n\n"
   "1. Buka Muse, pilih bagian Tujuan\n"
   "2. Isi target yang mau dicapai\n"
   "3. Buka Ide & feed buat lihat saran\n"
   "4. Baca dulu kalau ada permintaan akses akun\n\n"
   "Sisanya di bawah."),
  "en": (
   "Beyond chat, Muse has two sections most people skip: Goals and Ideas & feed.\n\n"
   "Goals is for long-term targets, Ideas & feed suggests things to build and sends periodic summaries.\n\n"
   "1. Open Muse, pick Goals\n"
   "2. Fill in the target you want to hit\n"
   "3. Open Ideas & feed to see suggestions\n"
   "4. Read carefully whenever it asks for account access\n\n"
   "More below."),
  "id2": (
   "5. Yang butuh akses kayak Gmail selalu minta izin lewat persetujuan\n"
   "6. Izin bisa dicabut kapan saja di pengaturan akun\n"
   "7. Ringkasan berkala muncul otomatis kalau feed-nya aktif\n\n"
   "Nggak ada akses yang jalan diam-diam."),
  "en2": (
   "5. Anything that needs access like Gmail always asks through an approval prompt\n"
   "6. Permissions can be revoked anytime in account settings\n"
   "7. Periodic summaries arrive automatically once the feed is on\n\n"
   "Nothing runs in the background without approval."),
  "media": "muse-specs.jpg", "media2": "p2-muse-5-spek-vps.jpg",
 },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", default="~/clove/media", help="folder media clove")
    ap.add_argument("--out", default="~/clove/clove_queue.json")
    ap.add_argument("--start", default="", help="ISO start time (default: sekarang WIB)")
    ap.add_argument("--interval", type=int, default=180, help="menit antar post")
    ap.add_argument("--skip-muse", action="store_true", help="hanya post repo")
    a = ap.parse_args()

    media = Path(a.media).expanduser()
    out = Path(a.out).expanduser()
    repos = json.loads((HERE / "repos.json").read_text())
    caps = json.loads((HERE / "captions.json").read_text())

    def muse_parts(k, lang):
        t = MUSE[k]
        p1 = t["id"] if lang == "id" else t["en"]
        p2 = t["id2"] if lang == "id" else t["en2"]
        return [{"text": p1, "media": [str(media / t["media"])]},
                {"text": p2, "media": [str(media / t["media2"])]}]

    seq = []
    ri = 0

    def add_muse(k, lang):
        seq.append({"kind": f"muse_{lang}", "label": f"{MUSE[k]['label']} ({lang.upper()})",
                    "parts": muse_parts(k, lang)})

    def add_repo():
        nonlocal ri
        ri += 1
        r = repos[ri - 1]
        seq.append({"kind": "repo", "label": r["full_name"],
                    "parts": [{"text": caps[r["full_name"]],
                               "media": [str(media / f"repo-{ri:02d}.jpg")]}]})

    muse_seq = [("t1", "id"), ("t1", "en"), ("t2", "id"), ("t2", "en"), ("t3", "id"), ("t3", "en")]
    total = len(repos) + len(muse_seq)
    muse_pos = {round(i * (total - 1) / (len(muse_seq) - 1)) for i in range(len(muse_seq))}
    mi = 0
    for pos in range(total):
        if pos in muse_pos and mi < len(muse_seq):
            add_muse(*muse_seq[mi])
            mi += 1
        elif ri < len(repos):
            add_repo()
    while mi < len(muse_seq):
        add_muse(*muse_seq[mi])
        mi += 1
    while ri < len(repos):
        add_repo()

    if a.skip_muse:
        seq = [s for s in seq if s["kind"] == "repo"]

    start = datetime.fromisoformat(a.start) if a.start else datetime.now(WIB)
    start = start.replace(second=0, microsecond=0)
    queue = []
    for i, s in enumerate(seq, 1):
        queue.append({
            "id": i,
            "due_at": (start + timedelta(minutes=a.interval * (i - 1))).isoformat(),
            "kind": s["kind"],
            "label": s["label"],
            "parts": s["parts"],
            "status": "pending",
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=1))
    print(f"posts {len(queue)} | repo {ri} | muse {len(queue) - ri} | out {out}")
    print(f"mulai {queue[0]['due_at']} | selesai {queue[-1]['due_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
