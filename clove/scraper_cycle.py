#!/usr/bin/env python3
"""scraper_cycle.py — siklus scrape Threads utk refill bot (VM 1-18).

Tiap siklus: ambil N grup keyword berikutnya dari scraper_keywords.json
(rotasi maju, state di scraper_state.json), jalankan find_posts.py per grup
(max umur 96 jam, limit 20), simpan stdout ke found_posts_auto_<TS>_a.json / _b.json
(file-file inilah bahan build_pool.py).

Dipanggil oleh threads_scraper.sh (cron threads-scraper c19db75e7751, tiap 30 menit).
Mode tes: --groups 1 --limit 5 --max-age-hours 48
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent
POOL_FILE = BOT / "scraper_keywords.json"
STATE_FILE = BOT / "scraper_state.json"
LOCK_FILE = BOT / ".scraper_cycle.lock"
LOG_FILE = BOT / "scraper.log"

PER_GROUP_TIMEOUT = 600
SUFFIXES = "abcdefgh"


def load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1))


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=2,
                    help="jumlah grup keyword per siklus (default 2)")
    ap.add_argument("--limit", type=int, default=20,
                    help="max post per grup (default 20)")
    ap.add_argument("--max-age-hours", type=float, default=96,
                    help="umur maksimum post (default 96 jam)")
    a = ap.parse_args()

    lock_fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("skip: cycle lain masih jalan")
        return 0

    groups = [g for g in load(POOL_FILE, []) if isinstance(g, list) and g]
    if not groups:
        log("ERROR: scraper_keywords.json kosong")
        return 1

    state = load(STATE_FILE, {"idx": 0})
    try:
        idx = int(state.get("idx", 0)) % len(groups)
    except Exception:
        idx = 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    written = []
    n_groups = max(1, a.groups)
    for slot in range(n_groups):
        group = groups[(idx + slot) % len(groups)]
        kw = ",".join(group)
        suffix = SUFFIXES[slot % len(SUFFIXES)]
        try:
            proc = subprocess.run(
                [sys.executable, str(BOT / "find_posts.py"),
                 "--keywords", kw,
                 "--max-age-hours", str(a.max_age_hours),
                 "--limit", str(a.limit)],
                capture_output=True, text=True, cwd=str(BOT),
                timeout=PER_GROUP_TIMEOUT,
            )
            out = (proc.stdout or "").strip()
            if out.startswith("["):
                fp = BOT / f"found_posts_auto_{ts}_{suffix}.json"
                fp.write_text(out + "\n")
                n = 0
                try:
                    n = len(json.loads(out))
                except Exception:
                    pass
                written.append(f"{fp.name} ({n} posts, kw: {kw})")
            else:
                log(f"WARN grup '{kw}': output bukan JSON (rc={proc.returncode})")
        except subprocess.TimeoutExpired:
            log(f"WARN grup '{kw}': timeout {PER_GROUP_TIMEOUT}s")
        except Exception as e:
            log(f"WARN grup '{kw}': {type(e).__name__}: {e}")

    state["idx"] = (idx + n_groups) % len(groups)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save(STATE_FILE, state)

    log("selesai: " + ("; ".join(written) if written else "tidak ada file baru"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
