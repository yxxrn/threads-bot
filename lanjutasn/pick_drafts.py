#!/usr/bin/env python3
"""pick_drafts.py — deterministic draft selection, ID-only, for @lanjutasn_id.

Replika pick_drafts.py Blooply. Reads pool_ready.json + live queue status,
then writes candidates.json: the exact posts the refill/drafter should
draft comments for.

Selection rules (ID-only):
  - target batch: 12 posts (semua ID)
  - skip authors replied within the last 24h (posted_history.jsonl)
  - skip URLs already in queue/replied/retry
  - skip URLs in skip_urls.txt (one per line, "#" = comment)
  - skip posts matching SKIP_PATTERNS (jualan bimbel/kompetitor, politik,
    duka, giveaway/crypto bait) — post JUALAN jasa/bimbel tidak eligible;
    post yang MENCARI rekomendasi/bantuan justru target utama.

Prints: PICK: N candidates (X ID) -> candidates.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent
BATCH = 12

# Post yang TIDAK eligible untuk balasan softsell. Pembeda utama: post yang
# MENJUAL jasa/bimbel/tryout berbayar (kompetitor) bukan target; post yang
# bertanya/minta rekomendasi justru target utama dan JANGAN di-skip.
SKIP_PATTERNS = [
    # Bimbel: hanya skip bila konteks JUALAN (daftar/promo/diskon/harga/jual/
    # open/cek bio/DM). Post yang BERTANYA soal bimbel ("bimbel apa yang bagus?")
    # atau cerita ikut bimbel adalah target genuine, jangan di-skip.
    re.compile(r"\bbimbel\b.*(daftar|promo|diskon|harga|jual|open|cek bio|link di bio|\bdm\b)", re.I),
    re.compile(r"(daftar|promo|diskon|jual|open).*\bbimbel\b", re.I),
    re.compile(r"\bjoki\b", re.I),
    re.compile(r"open jasa", re.I),
    re.compile(r"pricelist|price list", re.I),
    re.compile(r"kelas cpns|kelas pppk", re.I),
    re.compile(r"\bdiskon\b.*\b(cpns|pppk|bimbel)\b", re.I),
    re.compile(r"\bjasa\b.*\b(cpns|pppk|skd|pembuatan)\b", re.I),
    re.compile(r"\bpilpres\b|\bcapres\b|\bcawapres\b|\bpartai\b", re.I),
    re.compile(r"turut berduka|meninggal dunia|\brip\b", re.I),
    re.compile(r"\bgiveaway\b", re.I),
    re.compile(r"\bcrypto\b|saham.*cuan|cuan.*saham", re.I),
    re.compile(r"jual.*akun|beli.*akun", re.I),
    # Jualan produk belajar (ebook/materi/modul/soal) — kompetitor; post yang
    # MENJUAL bukan target. Pola "aku ada ..." = menawarkan dagangan sendiri.
    re.compile(r"aku ada.*(ebook|e-book|materi|modul|soal try ?out)", re.I),
    re.compile(r"(ebook|e-book).*(dijual|harga|beli|order|\bdm\b|cek)", re.I),
    re.compile(r"link di bio|cek bio|link bio|link di profil", re.I),
    re.compile(r"\bjual\b.*(ebook|materi|soal|modul|bimbel)", re.I),
    re.compile(r"open (po|pre.order)|pre.order", re.I),
]


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def main() -> int:
    pool = load(BOT / "pool_ready.json", [])
    queue = load(BOT / "comments.json", [])
    replied = set(load(BOT / "replied_urls.json", []))
    retry = load(BOT / "retry_queue.json", [])
    dead = {r.get("url") for r in retry if isinstance(r, dict) and r.get("dead")}
    queued = {c.get("url") for c in queue if c.get("url")}
    used = replied | queued | dead
    _n = lambda u: str(u or "").replace("https://www.threads.com/", "https://threads.com/").replace("https://threads.net/", "https://threads.com/").rstrip("/")
    used = {_n(u) for u in used}
    replied_n = {_n(u) for u in replied}
    dead_n = {_n(u) for u in dead}

    # permanent skip list for unsuitable posts (one URL per line, "#" = comment).
    skip_file = BOT / "skip_urls.txt"
    if skip_file.exists():
        for line in skip_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                line = line.lstrip("|")
                url = line.split("|")[0]
                used.add(_n(url))

    # recent authors (24h) from history
    recent_authors = set()
    hf = BOT / "posted_history.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    if hf.exists():
        for line in hf.read_text().splitlines():
            try:
                rec = json.loads(line)
                ts = rec.get("ts") or ""
                if ts:
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if t >= cutoff:
                        a = (rec.get("author") or "").strip().lower()
                        if a:
                            recent_authors.add(a)
            except Exception:
                pass

    candidates = []
    for item in pool:
        if len(candidates) >= BATCH:
            break
        url = item.get("url") or ""
        if not url or _n(url) in used:
            continue
        author = (item.get("author") or "").strip()
        if author.lower() in recent_authors:
            continue
        if author.lower() == "lanjutasn_id":
            continue
        text = item.get("text") or ""
        if any(rx.search(text) for rx in SKIP_PATTERNS):
            continue
        if (item.get("lang") or "") != "id":
            continue
        candidates.append(item)

    (BOT / "candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=1))
    print(f"PICK: {len(candidates)} candidates ({sum(1 for c in candidates if c.get('lang') == 'id')} ID) -> candidates.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
