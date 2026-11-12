#!/usr/bin/env python3
"""draft_comments.py — tulis draf balasan untuk candidates.json (template).

Drafter TAHAP AWAL untuk @lanjutasn_id (dry-run + produksi awal).
Untuk setiap kandidat di candidates.json: tentukan intent dari isi post,
ambil reaksi + softsell rotasi dari lanjut asn_identity.py, validasi dengan
check_identity, tulis ke comments_new.json: array [{url, author, lang,
comment, intent}].

Draf yang gagal validasi TIDAK ditulis (dicetak sebagai DROPPED + alasan).
Jalur produksi nanti: refill LLM Hermes (lanjutasn-auto-cycle) menggantikan
script ini dengan draf kontekstual; aturan identitasnya SAMA (modul ini).

Usage:
  ./venv/bin/python draft_comments.py            # tulis comments_new.json
  ./venv/bin/python draft_comments.py --print    # + cetak semua draf
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT))

import lanjutasn_identity as ident

# URL GUARD 2026-11-13: URL post Threads yang valid bentuknya persis
# https://www.threads.com/@<handle>/post/<id> (handle diawali @). Entri dengan
# URL malformed tidak pernah masuk antrean (lihat is_valid_thread_url di
# auto_comment.py — definisi kanonis; regex ini salinan yang sama).
THREAD_URL_RE = re.compile(r"^https://www\.threads\.com/@[A-Za-z0-9_][A-Za-z0-9._]*/post/[A-Za-z0-9_-]+/?$")


def is_valid_thread_url(url) -> bool:
    return isinstance(url, str) and bool(THREAD_URL_RE.match(url))




def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="cetak semua draf")
    a = ap.parse_args()

    candidates = load(BOT / "candidates.json", [])
    if not candidates:
        print("DRAFT: 0 candidates (candidates.json kosong — jalankan pick_drafts.py dulu)")
        return 0

    drafts, dropped = [], []
    for i, c in enumerate(candidates):
        if not is_valid_thread_url(c.get("url")):
            dropped.append((c.get("url"), ["malformed_url"]))
            continue  # URL GUARD 2026-11-13: malformed URL never enters the queue
        text = c.get("text") or ""
        comment, intent = ident.draft_for(text, i)
        problems = ident.check_identity(comment)
        if problems:
            dropped.append((c.get("url"), problems))
            continue
        drafts.append({
            "url": c.get("url"),
            "author": c.get("author", ""),
            "lang": "id",
            "comment": comment,
            "intent": intent,
        })

    (BOT / "comments_new.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=1))
    print(f"DRAFT: {len(drafts)} drafted, {len(dropped)} dropped -> comments_new.json")
    for url, problems in dropped:
        print(f"  DROPPED {url}: {'; '.join(problems)}")
    if a.print:
        for d in drafts:
            print("=" * 70)
            print(f"URL: {d['url']}")
            print(f"author: @{d['author']} | intent: {d['intent']}")
            print("-" * 70)
            print(d["comment"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
