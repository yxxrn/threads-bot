#!/usr/bin/env python3
"""check_dry_run.py — dry-run end-to-end bot @lanjutasn_id TANPA posting.

Langkah:
  1. scraper_cycle.py --groups 1 --limit 5 --max-age-hours 24 (scrape live,
     read-only; memakai sesi @lanjutasn_id yang sudah terverifikasi)
  2. build_pool.py (pool ID-only + keyword ASN)
  3. pick_drafts.py (pilih kandidat, filter author 24 jam + skip patterns)
  4. draft_comments.py --print (buat draf + validasi identitas, cetak draf)
  5. queue_status.py (status antrean)

TIDAK ADA posting, TIDAK ADA merge ke comments.json (draf berhenti di
comments_new.json). Jalankan dengan venv python Blooply:
  /home/ubuntu/threads-bot/venv/bin/python check_dry_run.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
PY = sys.executable


def run(args, label):
    print(f"\n===== {label} =====", flush=True)
    proc = subprocess.run([PY] + args, cwd=str(BOT), text=True,
                          capture_output=False)
    print(f"[{label}] exit={proc.returncode}", flush=True)
    return proc.returncode


def main() -> int:
    rc = run([str(BOT / "scraper_cycle.py"), "--groups", "1",
              "--limit", "5", "--max-age-hours", "24"], "1. SCRAPE")
    if rc != 0:
        print("DRY-RUN: scrape gagal, berhenti")
        return rc
    rc = run([str(BOT / "build_pool.py")], "2. BUILD POOL")
    if rc != 0:
        print("DRY-RUN: build_pool gagal, berhenti")
        return rc
    rc = run([str(BOT / "pick_drafts.py")], "3. PICK DRAFTS")
    if rc != 0:
        print("DRY-RUN: pick_drafts gagal, berhenti")
        return rc
    rc = run([str(BOT / "draft_comments.py"), "--print"], "4. DRAFT + VALIDATE")
    if rc != 0:
        print("DRY-RUN: draft_comments gagal, berhenti")
        return rc
    run([str(BOT / "queue_status.py")], "5. QUEUE STATUS")
    print("\nDRY-RUN SELESAI: tidak ada posting. Draf ada di comments_new.json.")
    print("Untuk memasukkan draf ke antrean live (hanya setelah persetujuan):")
    print("  ./venv/bin/python merge_comments.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
