#!/usr/bin/env python3
"""Queue akun ketiga (@panahberuang): 50 repo, jeda 3 jam.

Contoh:
  python compose_queue.py --media ~/panahberuang/media \
      --out ~/panahberuang/panah_queue.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIB = timezone(timedelta(hours=7))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", default="~/panahberuang/media")
    ap.add_argument("--out", default="~/panahberuang/panah_queue.json")
    ap.add_argument("--start", default="")
    ap.add_argument("--interval", type=int, default=180)
    a = ap.parse_args()

    media = Path(a.media).expanduser()
    out = Path(a.out).expanduser()
    repos = json.loads((HERE / "repos.json").read_text())
    caps = json.loads((HERE / "captions.json").read_text())
    missing = [r["full_name"] for r in repos if r["full_name"] not in caps]
    if missing:
        raise SystemExit(f"caption kurang: {missing}")

    start = datetime.fromisoformat(a.start) if a.start else datetime.now(WIB)
    start = start.replace(second=0, microsecond=0)
    queue = []
    for i, r in enumerate(repos, 1):
        queue.append({
            "id": i,
            "due_at": (start + timedelta(minutes=a.interval * (i - 1))).isoformat(),
            "kind": "repo",
            "label": r["full_name"],
            "parts": [{"text": caps[r["full_name"]],
                       "media": [str(media / f"repo-{i:02d}.jpg")]}],
            "status": "pending",
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=1))
    print(f"posts {len(queue)} | mulai {queue[0]['due_at']} | akhir {queue[-1]['due_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
