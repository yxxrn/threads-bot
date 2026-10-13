#!/usr/bin/env python3
"""Continuous posting daemon for the Threads bot.

Posts queued replies (comments.json + retry_queue.json) with random 2-3 min
gaps, continuously, until session.json expires. The cron agent
(threads-auto-cycle) only REFILLS the queue (finds posts + drafts comments);
this daemon does all actual posting, so the cadence is continuous instead of
batched.

Run:  cd ~/threads-bot && ./venv/bin/python poster_daemon.py
Logs: daemon.log
"""
from __future__ import annotations

import fcntl
import importlib.util
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BOT = Path(__file__).resolve().parent

# Reuse the verified posting logic from auto_comment.py.
spec = importlib.util.spec_from_file_location("ac", BOT / "auto_comment.py")
ac = importlib.util.module_from_spec(spec)
sys.modules["ac"] = ac
spec.loader.exec_module(ac)

LOG = BOT / "daemon.log"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def session_status():
    sess = ac.load_json(ac.SESSION_FILE, None)
    if not sess or not sess.get("started_at"):
        return False, "SESSION_MISSING"
    try:
        started = datetime.fromisoformat(sess["started_at"])
        elapsed = (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
        dur = sess.get("duration_hours")
        if dur is None:
            # unlimited session: runs until the user says stop
            return True, f"active unlimited ({elapsed:.1f}h)"
        dur = float(dur)
        if elapsed >= dur:
            return False, f"SESSION_EXPIRED elapsed={elapsed:.1f}h"
        return True, f"active {elapsed:.1f}h/{dur:g}h"
    except Exception as e:
        return False, f"SESSION_BROKEN {e}"


def main() -> int:
    # Pakai lock yang SAMA dengan auto_comment.py (.auto_comment.lock) supaya
    # tidak mungkin ada dua poster jalan bersamaan (double-post).
    lock_fh = (BOT / ".auto_comment.lock").open("w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("DAEMON_ALREADY_RUNNING")
        return 4

    ok, why = session_status()
    if not ok:
        log(f"not starting: {why}")
        return 5

    from cloakbrowser import launch

    def new_ctx():
        b = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
        c = b.new_context(storage_state=str(ac.STATE))
        p = c.new_page()
        return b, c, p

    browser, ctx, page = new_ctx()
    log(f"daemon started ({why})")

    results = []
    retry_state = {r["url"]: r for r in ac.load_json(ac.RETRY_FILE, []) if r.get("url")}
    consec_fail = 0
    exc_streak = 0
    posted = 0

    try:
        while True:
            ok, why = session_status()
            if not ok:
                log(f"STOP: {why}")
                break

            queue = ac.build_queue()
            if not queue:
                log("queue empty, waiting 45s for the refill cycle")
                time.sleep(45)
                continue

            item = queue[0]
            log(f"posting @{item.get('author')} [{item.get('lang')}] {item['url']}")
            try:
                rec = ac.post_reply(ctx, page, item["url"], item["comment"], posted)
                exc_streak = 0
            except Exception as e:
                rec = {"url": item["url"], "ts": datetime.now(timezone.utc).isoformat(),
                       "ok": False, "error": f"exc:{type(e).__name__}"}
                exc_streak += 1
                log(f"EXCEPTION: {type(e).__name__}: {e}")
                if exc_streak >= 2:
                    log("recreating browser after repeated exceptions")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    try:
                        browser, ctx, page = new_ctx()
                        exc_streak = 0
                    except Exception as e2:
                        log(f"relaunch failed: {e2}; cooling down 5 min")
                        time.sleep(300)
                        continue

            rec["comment"] = item["comment"]
            rec["author"] = item.get("author", "")
            rec["lang"] = item.get("lang", "")
            results.append(rec)
            ac.save_json(ac.LOG_FILE, results[-50:])
            ac.append_history(rec)

            if rec.get("ok"):
                consec_fail = 0
                posted += 1
                ac.mark_replied(item["url"])
                retry_state.pop(item["url"], None)
                log(f"OK @{item.get('author')} (total this run: {posted})")
            else:
                err = rec.get("error", "?")
                if rec.get("skipped") == "pending_author_approval":
                    # Author-gated thread: not a real failure, do not count
                    # toward the consecutive-failure cooldown.
                    log(f"SKIP @{item.get('author')}: pending_author_approval (author-gated)")
                else:
                    consec_fail += 1
                    log(f"FAIL @{item.get('author')}: {err}")
                fails = item.get("fails", 0) + 1
                entry = {
                    "url": item["url"], "author": item.get("author", ""),
                    "comment": item.get("comment"), "lang": item.get("lang", ""),
                    "fails": fails,
                }
                if rec.get("skipped") == "pending_author_approval":
                    # intentional skip: author-gated thread; never retry
                    entry["skip_reason"] = "pending_author_approval"
                if rec.get("error") == "post_deleted":
                    # post deleted between scrape and post; expected, not alertable
                    entry["skip_reason"] = "post_deleted"
                if not (err in ac.RETRYABLE and fails < ac.MAX_RETRIES):
                    # keep a tombstone so build_queue() cannot re-add this draft
                    # from comments.json (retry-loop bug 2026-09-29)
                    entry["dead"] = True
                retry_state[item["url"]] = entry
            ac.save_json(ac.RETRY_FILE, list(retry_state.values()))

            if consec_fail >= 3:
                log("3 consecutive failures; cooling down 12 min")
                consec_fail = 0
                time.sleep(720)
            else:
                gap = random.uniform(ac.GAP_MIN, ac.GAP_MAX)
                log(f"gap {gap:.0f}s")
                time.sleep(gap)
    finally:
        try:
            browser.close()
        except Exception:
            pass
        log(f"daemon exited (posted this run: {posted})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
