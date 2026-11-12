#!/usr/bin/env python3
"""validate_comments.py - validasi draf di comments_new.json dgn check_identity.

Dipakai job refill LLM Hermes lanjut asn-auto-cycle (langkah 4) SEBELUM merge.
- Baca comments_new.json, jalankan check_identity() per komentar.
- Entri yang gagal validasi DIBUANG dari comments_new.json (dicetak DROPPED + alasan).
- Cetak ringkasan: VALID: N, DROPPED: M.
- Exit 0 selalu (kecuali file tidak terbaca).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT))

from lanjutasn_identity import check_identity


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def main() -> int:
    items = load(BOT / "comments_new.json", [])
    kept = []
    dropped = 0
    for it in items:
        problems = check_identity(it.get("comment", ""))
        if problems:
            dropped += 1
            print("DROPPED " + str(it.get("url")) + " :: " + "; ".join(problems), flush=True)
            continue
        kept.append(it)
    (BOT / "comments_new.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=1)
    )
    print("VALID: " + str(len(kept)) + ", DROPPED: " + str(dropped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
