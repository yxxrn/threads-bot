#!/usr/bin/env python3
"""Promo @blooplyy_ — 2-part chains, pure HTTP API (curl_cffi).

Rotasi varian dari variants.json. Part 1 = gambar + caption,
Part 2 = reply text (CTA lisensi/voucher). State index di promo_state.json.
"""
import json
import hashlib
import io
import os
import random
import re
import sys
import time
from pathlib import Path

from PIL import Image
from curl_cffi import requests as creq

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


def validate(v: dict) -> str | None:
    chain = v.get("chain")
    if chain:
        tag = f"/chain{chain}/"
        if tag not in v["media"] or tag not in v["p2_media"]:
            return f"media chain mismatch {v['key']} chain={chain}"
    for fld in ("media", "p2_media"):
        p = Path(v[fld])
        head = p.open("rb").read(4) if p.exists() else b""
        if not p.exists() or p.stat().st_size < 5000 or head[:3] not in (b"\xff\xd8\xff", b"\x89PN"):
            return f"media invalid {v['key']} {fld}={p}"
    manifest = json.loads((BASE / "media_manifest.json").read_text())
    for fld in ("media", "p2_media"):
        p = Path(v[fld])
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        approved = manifest.get(f"{v['key']}:{fld}", {}).get("sha256")
        if not approved or approved != digest:
            return f"media not approved {v['key']} {fld}={p.name}"
    return None


def _dhash(im, size: int = 16) -> int:
    im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits


def verify_post(api, code: str, path: str, tries: int = 3):
    """True/False kalau gambar bisa dicek, None kalau halaman tak tersedia."""
    want = _dhash(Image.open(path))
    last = "no attempt"
    for attempt in range(tries):
        try:
            h = api.s.get(f"https://www.threads.com/@blooplyy_/post/{code}",
                          cookies=api.cookies, headers={"user-agent": "Mozilla/5.0"},
                          timeout=30).text
            for u in re.findall(r'https://scontent[^"\\]+\.(?:jpg|webp)[^"\\]*', h):
                u = u.replace("\\u0026", "&").replace("\\/", "/").replace("&amp;", "&").split('"')[0]
                if "t51.82787" not in u:
                    continue
                r = creq.get(u, timeout=30, impersonate="chrome",
                             headers={"referer": "https://www.threads.com/"})
                if r.status_code != 200:
                    continue
                im = Image.open(io.BytesIO(r.content))
                if min(im.size) < 500:
                    continue
                dist = bin(want ^ _dhash(im)).count("1")
                if dist <= 25:
                    return True, f"dist={dist}"
                return False, f"dist={dist}"
            last = "no image on page"
        except Exception as e:
            last = str(e)[:80]
        time.sleep(20)
    return None, last


def main() -> int:
    if "--check" in sys.argv:
        st = load_state()
        v = VARIANTS[st["i"] % len(VARIANTS)]
        err = validate(v)
        log(f"check {v['key']}: {err or 'OK'}")
        return 1 if err else 0
    if not acquire():
        return 0
    try:
        st = load_state()
        idx = st["i"] % len(VARIANTS)
        v = VARIANTS[idx]
        err = validate(v)
        if err:
            log("ERROR " + err)
            return 1
        log(f"start #{idx+1}/{len(VARIANTS)} {v['key']} chain={v.get('chain')} {Path(v['media']).name}")

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
        pk2 = r2.json()["media"].get("pk")

        ok1, info1 = verify_post(api, code, v["media"])
        if p2m:
            ok2, info2 = verify_post(api, code2, p2m)
        else:
            ok2, info2 = True, "text"
        log(f"verify {v['key']} part1={ok1}:{info1} part2={ok2}:{info2}")
        if ok1 is False or ok2 is False:
            log(f"ERROR media salah terbit {v['key']} → hapus {code}/{code2}")
            for dead in (pk, pk2):
                if dead:
                    try:
                        api.delete_post(str(dead))
                    except Exception as e:
                        log(f"WARN delete {dead}: {e}")
            return 1

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
