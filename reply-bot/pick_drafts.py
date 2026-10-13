#!/usr/bin/env python3
"""pick_drafts.py — deterministic draft selection with ID priority.

Reads pool_ready.json + live queue status, then writes candidates.json:
the exact posts the refill agent should draft comments for.

Selection rules (ID-first):
  - target batch: 12 posts (ID >= 8 when supply allows)
  - if live queue already has >= 8 ID: relaxed (6 ID + 6 EN)
  - skip authors replied within the last 24h (posted_history.jsonl)
  - skip URLs already in queue/replied/retry

Prints: PICK: N candidates (X ID, Y EN) -> candidates.json
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent
BATCH = 12
ID_MIN_WHEN_LOW = 10   # ID-dominant: 10 of 12 when queue ID supply is low


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
    # r308: solicitation posts must never get a promo reply; without this they
    # reappear in every pool rebuild and get re-picked on every refill run.
    skip_file = BOT / "skip_urls.txt"
    if skip_file.exists():
        for line in skip_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                used.add(_n(line))

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

    # live queue ID count decides the mix
    live = [c for c in queue if c.get("url") and _n(c.get("url")) not in replied_n and _n(c.get("url")) not in dead_n]
    live_id = sum(1 for c in live if c.get("lang") == "id")

    id_quota = ID_MIN_WHEN_LOW if live_id < 8 else 6
    en_quota = BATCH - id_quota

    def dedupe(cands):
        seen_t = set()
        seen_a = set()
        out = []
        for p in cands:
            norm = " ".join((p.get("text") or "").strip().lower().split())[:100]
            a = (p.get("author") or "").strip().lower()
            if norm and norm in seen_t:
                continue
            if a and a in seen_a:
                continue
            seen_t.add(norm)
            if a:
                seen_a.add(a)
            out.append(p)
        return out

    id_cands = dedupe([p for p in pool if p.get("lang") == "id"
                       and _n(p.get("url")) not in used and (p.get("author") or "").strip().lower() not in recent_authors])
    en_cands = dedupe([p for p in pool if p.get("lang") == "en"
                       and _n(p.get("url")) not in used and (p.get("author") or "").strip().lower() not in recent_authors])

    picked = id_cands[:id_quota] + en_cands[:en_quota]
    # if ID supply ran short, top up with EN
    if len(picked) < BATCH:
        picked += en_cands[en_quota:en_quota + (BATCH - len(picked))]
    # if still short, fill remaining slots from the rest of the ID pool.
    # NOTE: keep the 24h recent-author filter here too. The old fallback
    # re-added authors replied hours ago (duplicate twin posts, manually
    # dropped r303-r306); fresh supply beats duplicate coverage.
    if len(picked) < BATCH:
        picked_authors = {(p.get("author") or "").strip().lower() for p in picked}
        extra = dedupe([p for p in pool if p.get("lang") == "id" and _n(p.get("url")) not in used
                        and p not in picked
                        and (p.get("author") or "").strip().lower() not in recent_authors
                        and (p.get("author") or "").strip().lower() not in picked_authors])
        picked += extra[: BATCH - len(picked)]

    out = [{"url": p["url"], "author": p.get("author", ""), "lang": p["lang"],
            "text": p.get("text", "")[:800]} for p in picked]
    (BOT / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    xn = sum(1 for c in out if c["lang"] == "id")
    yn = sum(1 for c in out if c["lang"] == "en")
    print(f"PICK: {len(out)} candidates ({xn} ID, {yn} EN) -> candidates.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
