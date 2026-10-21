#!/usr/bin/env python3
"""@clovebliz queue runner.

Single-media blocks -> HTTP API (curl_cffi, cheap).
Multi-media blocks  -> Playwright post.py (carousel + chain).
One block per run. State: done ids. DRY_RUN=1 prints only.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/home/agentuser/threads-bot-repo/api-experiment")
from api_client import ThreadsAPI  # noqa: E402

BASE = Path("/home/agentuser/clove")
QUEUE = BASE / "clove_queue.json"
STATE = BASE / "queue_state.json"
LOCK = BASE / "runner.lock"
LOG = BASE / "runner.log"
STATE_FILE = "/home/agentuser/threads-playwright/storage_state_clove.json"
POSTER = "/home/agentuser/threads-playwright/post.py"
VPY = "/home/agentuser/threads-playwright/.venv/bin/python"
WIB = timezone(timedelta(hours=7))
OWN_LOCK = False

TEXT = {"muse_id": "Muse ID", "muse_en": "Muse EN", "repo": "Repo"}


def log(msg: str) -> None:
    line = f"{datetime.now(WIB).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def save_state(s):
    STATE.write_text(json.dumps(s, indent=1))


def acquire() -> bool:
    if LOCK.exists():
        try:
            if time.time() - LOCK.stat().st_mtime < 1800:
                return False
        except FileNotFoundError:
            pass
        LOCK.unlink(missing_ok=True)
    try:
        LOCK.write_text(str(os.getpid()))
        return True
    except Exception:
        return False


def post_browser(parts) -> tuple[bool, str]:
    cmd = [VPY, POSTER] + [p["text"] for p in parts]
    for p in parts:
        m = p.get("media") or []
        cmd += ["--media", ",".join(m) if m else "-"]
    cmd += ["--state", STATE_FILE,
            "--profile-url", "https://www.threads.com/@clovebliz"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, env={**os.environ, "BLOOPLY_BROWSER": "stock"})
    except subprocess.TimeoutExpired:
        return False, "timeout 1200s"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, out[-600:]


def post_api(parts) -> tuple[bool, str]:
    api = ThreadsAPI(STATE_FILE)
    pks = []
    out = []
    for i, p in enumerate(parts):
        text = p["text"]
        media = p.get("media") or []
        parent = pks[-1] if pks else None
        if len(media) > 1:
            r = api.post_carousel(text, media, reply_to=parent)
        elif media:
            r = api.post_media(text, media[0], reply_to=parent) if parent else api.post_media(text, media[0])
        else:
            r = api.reply_text(parent, text) if parent else api.post_text(text)
        if not r or r.status_code != 200:
            return False, (out + [f"part {i+1} failed: {getattr(r, 'text', 'none')[:200]}"]).pop()
        d = r.json().get("media", {})
        pks.append(d.get("pk"))
        out.append(f"{d.get('code')} media={len(media)}")
    return True, " | ".join(out)


def main() -> int:
    global OWN_LOCK
    dry = os.environ.get("DRY_RUN") == "1"
    queue = load(QUEUE, [])
    state = load(STATE, {"done": [], "attempts": {}})
    done = set(state.get("done", []))
    now = datetime.now(WIB)
    due = None
    for b in queue:
        if b["id"] in done:
            continue
        t = datetime.fromisoformat(b["due_at"])
        if t <= now + timedelta(minutes=2):
            if now - t > timedelta(hours=2):
                b["due_at"] = (now + timedelta(minutes=30)).isoformat()
                QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1))
                log(f"stale #{b['id']} rescheduled {b['due_at']}")
                return 0
            due = b
            break
    if not due:
        return 0
    if not dry:
        if not acquire():
            return 0
        OWN_LOCK = True

    parts = due["parts"]
    multi = max(len(p.get("media") or []) for p in parts) > 1
    log(f"start #{due['id']} {TEXT.get(due['kind'], due['kind'])} {due['label']} "
        f"parts={len(parts)} mode=api carousel={multi}")
    if dry:
        for p in parts:
            print(len(p.get("media") or []), "media |", p["text"][:70])
        return 0

    try:
        ok, info = post_api(parts)
    except Exception as e:
        ok, info = False, f"exception {e}"
    if not ok:
        att = state.setdefault("attempts", {})
        n = int(att.get(str(due["id"]), 0)) + 1
        att[str(due["id"])] = n
        save_state(state)
        log(f"ERROR #{due['id']} attempt={n} {info}")
        return 1

    done.add(due["id"])
    state["done"] = sorted(done)
    state.setdefault("attempts", {}).pop(str(due["id"]), None)
    save_state(state)
    (BASE / "posted.log").open("a").write(
        f"{datetime.now(WIB).isoformat(timespec='seconds')} {due['id']} {due['kind']} "
        f"{due['label']} mode=api carousel={multi}\n"
    )
    log(f"done #{due['id']} {due['label']} {info}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if OWN_LOCK:
            LOCK.unlink(missing_ok=True)
