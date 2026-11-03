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

    # Stop sengaja (2026-11-03): file STOPPED berarti pemilik menghentikan
    # instance ini; daemon tidak boleh jalan apa pun alasannya sampai file
    # ini dihapus atas perintah pemilik.
    if (BOT / "STOPPED").exists():
        log("not starting: STOPPED file present (intentionally stopped)")
        return 8

    # Penjaga identitas akun (insiden 2026-11-03): daemon tidak boleh jalan
    # tanpa account.json dan tanpa state.json. Verifikasi sesi penuh terjadi
    # di bawah, tepat setelah konteks browser pertama dibuat.
    sys.path.insert(0, str(BOT))
    import account_guard
    expected = account_guard.load_expected(BOT)
    if not expected:
        log("not starting: account.json hilang/rusak (tidak bisa verifikasi akun)")
        return 6
    if not ac.STATE.exists():
        log(f"not starting: state.json hilang untuk @{expected} (pasang sesi akun ini dulu)")
        return 6

    from cloakbrowser import launch

    def new_ctx():
        b = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
        c = b.new_context(storage_state=str(ac.STATE))
        p = c.new_page()
        return b, c, p

    browser, ctx, page = new_ctx()
    ok_g, exp_g, found_g, via_g = account_guard.verify(page, BOT)
    if not ok_g:
        log(f"ACCOUNT_GUARD REFUSED: expected=@{exp_g} found={found_g} via={via_g} (tidak posting apa pun)")
        try:
            browser.close()
        except Exception:
            pass
        return 7
    log(f"account guard OK: sesi terverifikasi sebagai @{found_g} (via={via_g})")
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
            log(f"posting @{item.get('author')} [{item.get('lang')}] extra={'ya' if item.get('extra_comment') else 'tidak'} {item['url']}")
            try:
                main_rec, extra_rec = ac.post_item(ctx, page, item, posted)
                exc_streak = 0
            except Exception as e:
                main_rec = {"url": item["url"], "ts": datetime.now(timezone.utc).isoformat(),
                            "ok": False, "error": f"exc:{type(e).__name__}"}
                extra_rec = None
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
                        ok_g, exp_g, found_g, via_g = account_guard.verify(page, BOT)
                        if not ok_g:
                            log(f"ACCOUNT_GUARD REFUSED after relaunch: expected=@{exp_g} found={found_g} via={via_g}")
                            try:
                                browser.close()
                            except Exception:
                                pass
                            return 7
                        log(f"account guard OK after relaunch: @{found_g} (via={via_g})")
                        exc_streak = 0
                    except Exception as e2:
                        log(f"relaunch failed: {e2}; cooling down 5 min")
                        time.sleep(300)
                        continue

            for rec in (main_rec, extra_rec):
                if rec is None:
                    continue
                results.append(rec)
                results = results[-50:]
                ac.save_json(ac.LOG_FILE, results)
                ac.append_history(rec)

            entry = ac.advance_item(item, main_rec, extra_rec)
            if entry is None:
                retry_state.pop(item["url"], None)
                consec_fail = 0
                posted += 1
                log(f"OK @{item.get('author')} main + extra={extra_rec.get('ok') if extra_rec else 'tidak ada'} (total this run: {posted})")
            else:
                if main_rec.get("skipped") == "pending_author_approval":
                    # Author-gated thread: not a real failure, do not count
                    # toward the consecutive-failure cooldown.
                    log(f"SKIP @{item.get('author')}: pending_author_approval (author-gated)")
                else:
                    consec_fail += 1
                    log(f"FAIL @{item.get('author')}: main={main_rec.get('error')} extra={extra_rec.get('error') if extra_rec else 'tidak ada'}")
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
