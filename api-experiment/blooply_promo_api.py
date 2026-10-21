#!/usr/bin/env python3
"""Promo @blooplyy_ — 2-part chains, pure HTTP API (curl_cffi).

Rotasi varian dari variants.json. Part 1 = gambar + caption,
Part 2 = reply text (CTA lisensi/voucher). State index di promo_state.json.
"""
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/agentuser/threads-bot-repo/api-experiment")
from api_client import ThreadsAPI

BASE = Path("/home/agentuser/blooply_promo")
VARIANTS = json.loads((BASE / "variants.json").read_text())
STATE = BASE / "promo_state.json"
LOCK = BASE / "promo.lock"
STATE_FILE = "/home/agentuser/threads-playwright/storage_state.json"
LOG = BASE / "promo.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def acquire() -> bool:
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < 3600:
            log(f"skip: lock aktif ({int(age)}s)")
            return False
        LOCK.unlink(missing_ok=True)
    LOCK.write_text(str(os.getpid()))
    return True


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"i": 0, "done": []}


def main() -> int:
    if not acquire():
        return 0
    try:
        st = load_state()
        idx = st["i"] % len(VARIANTS)
        v = VARIANTS[idx]
        log(f"start #{idx+1}/{len(VARIANTS)} {v['key']} {Path(v['media']).name}")

        api = ThreadsAPI(STATE_FILE)
        r1 = api.post_media(v["p1"], v["media"])
        if not r1 or r1.status_code != 200:
            log(f"ERROR part1 {v['key']}: {getattr(r1,'status_code','none')} {getattr(r1,'text','')[:200]}")
            return 1
        d1 = r1.json()["media"]
        pk, code = d1["pk"], d1["code"]
        log(f"part1 {code} pk={pk}")

        time.sleep(random.randint(70, 95))
        p2m = v.get("p2_media")
        if p2m:
            r2 = api.post_media(v["p2"], p2m, reply_to=pk)
        else:
            r2 = api.reply_text(pk, v["p2"])
        if not r2 or r2.status_code != 200:
            time.sleep(20)
            if p2m:
                r2 = api.post_media(v["p2"], p2m, reply_to=pk)
            else:
                r2 = api.reply_text(pk, v["p2"])
        if not r2 or r2.status_code != 200:
            log(f"WARN part2 gagal {v['key']}: {getattr(r2,'status_code','none')}")
            return 1
        code2 = r2.json()["media"]["code"]

        st["i"] = idx + 1
        st.setdefault("done", []).append({"key": v["key"], "code": code, "reply": code2,
                                          "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        st["done"] = st["done"][-40:]
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))
        log(f"done {v['key']} part1={code} part2={code2} next={st['i'] % len(VARIANTS) + 1}")
        print(f"Promo {v['key']} terbit\nhttps://www.threads.com/@blooplyy_/post/{code}")
        return 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
