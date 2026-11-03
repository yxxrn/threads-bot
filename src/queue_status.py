#!/usr/bin/env python3
"""queue_status.py — accurate live-queue status for the refill decision.

Counts only LIVE drafts: not replied, not tombstoned/dead in retry_queue.json.
Tombstones (dead entries kept so drafts can't be re-added) are excluded.

Prints one line:
  STATUS | N live (X ID) | M tombstone | SESSION_OK/NO_SESSION
Exit 0 always. Used by the refill cron prompt.
"""
from __future__ import annotations

import json
from pathlib import Path

BOT = Path(__file__).resolve().parent


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def main() -> int:
    session = load(BOT / "session.json", None)
    queue = load(BOT / "comments.json", [])
    replied = set(load(BOT / "replied_urls.json", []))
    retry = load(BOT / "retry_queue.json", [])
    dead = {r.get("url") for r in retry if isinstance(r, dict) and r.get("dead")}

    live = [c for c in queue if c.get("url") and c.get("url") not in replied and c.get("url") not in dead]
    idn = sum(1 for c in live if c.get("lang") == "id")
    tombstones = sum(1 for r in retry if isinstance(r, dict) and r.get("dead"))

    sess = "SESSION_OK" if session else "NO_SESSION"
    print(f"STATUS | {len(live)} live ({idn} ID) | {tombstones} tombstone | {sess}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
