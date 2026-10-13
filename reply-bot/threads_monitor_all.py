#!/usr/bin/env python3
"""threads_monitor_all.py — monitor gabungan Threads reply bot (VM 1-18).

Output DETERMINISTIK (tanpa timestamp): cetak alert hanya saat ada yang perlu
ditindak; output kosong = sehat. Dipakai sebagai monitor_script cron job
threads-watchdog (bc7c73d3b4c0) — output yang tidak berubah akan men-skip run
agent, jadi jaga output tetap stabil untuk kondisi yang sama.

Cek: daemon poster hidup; sesi bot; antrian macet (>3 jam kosong); cron worker
stuck >45 menit; reply gagal beruntun >=3 akun/2 jam; retry dead; umur sesi
browser; job refill ada & tidak paused saat sesi aktif.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Portable: folder bot = lokasi file ini. Override lewat env kalau perlu.
BOT = Path(os.environ.get("THREADS_BOT_DIR", Path(__file__).resolve().parent))
# Penjadwal Hermes menyimpan jobs.json di sini; kalau tidak dipakai,
# folder ini tidak ada dan cek terkait cron otomatis di-skip (aman).
CRON_DIR = Path(os.environ.get("HERMES_CRON_DIR", Path.home() / ".hermes2" / "cron"))
JOB_ID = os.environ.get("REFILL_JOB_ID", "d2992793f4bd")
STALE_QUEUE_HOURS = 3.0


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def main() -> None:
    alerts: list[str] = []

    # 0) Daemon poster hidup?
    try:
        out = subprocess.run(
            ["pgrep", "-f", "poster_daemon.py"],
            capture_output=True, text=True, timeout=10,
        )
        if not out.stdout.strip():
            alerts.append("WATCHDOG: daemon poster TIDAK jalan.")
    except Exception:
        alerts.append("WATCHDOG: daemon poster TIDAK jalan.")

    # 1) Sesi
    sess = load_json(BOT / "session.json", None)
    session_active = False
    if not sess or not sess.get("started_at"):
        alerts.append(
            "WATCHDOG: tidak ada sesi aktif (session.json). Bot tidak akan posting. "
            "Bilang 'mulai' untuk sesi baru."
        )
    else:
        try:
            started = datetime.fromisoformat(sess["started_at"])
            elapsed_h = (datetime.now(timezone.utc) - started).total_seconds() / 3600.0
            dur = sess.get("duration_hours", 24)
            dur = float("inf") if dur is None else float(dur)
            if elapsed_h >= dur:
                alerts.append(
                    "WATCHDOG: sesi sudah habis. Bot berhenti otomatis. "
                    "Bilang 'mulai' untuk sesi baru."
                )
            else:
                session_active = True
        except Exception:
            alerts.append("WATCHDOG: session.json rusak / tidak bisa dibaca.")

    # 2) Antrian macet: sesi aktif, antrian kosong, tidak ada post sukses >3 jam
    if session_active:
        try:
            queue = load_json(BOT / "comments.json", [])
            replied = set(load_json(BOT / "replied_urls.json", []))
            retry = load_json(BOT / "retry_queue.json", [])
            dead = {r.get("url") for r in retry
                    if isinstance(r, dict) and r.get("dead")}
            live = [c for c in queue if c.get("url")
                    and c["url"] not in replied and c["url"] not in dead]
            hist = BOT / "posted_history.jsonl"
            last_ok = None
            if hist.exists():
                for line in hist.read_text().splitlines():
                    try:
                        rec = json.loads(line)
                        if rec.get("ok") and rec.get("ts"):
                            last_ok = datetime.fromisoformat(
                                str(rec["ts"]).replace("Z", "+00:00"))
                    except Exception:
                        continue
            if not live and last_ok is not None:
                age_h = (datetime.now(timezone.utc) - last_ok).total_seconds() / 3600.0
                if age_h >= STALE_QUEUE_HOURS:
                    alerts.append(
                        "WATCHDOG: antrian kosong >3 jam (tidak ada post sukses); "
                        "cek scraper/refill."
                    )
        except Exception:
            pass

    # 3) Stuck cron worker (>45 min)
    try:
        out = subprocess.run(
            ["pgrep", "-f", "cron.scheduler --external-worker"],
            capture_output=True, text=True, timeout=10,
        )
        for pid in [p for p in out.stdout.strip().splitlines() if p.strip()]:
            try:
                et = subprocess.run(
                    ["ps", "-p", pid, "-o", "etimes="],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip()
                if et and int(et) > 2700:
                    alerts.append(f"WATCHDOG: cron worker STUCK >45 menit (PID {pid}).")
            except Exception:
                pass
    except Exception:
        pass

    # 4) Reply failures in last 2h (stable: sorted unique authors)
    hist = BOT / "posted_history.jsonl"
    if hist.exists():
        cutoff = datetime.now(timezone.utc).timestamp() - 7200
        recs = []
        for line in hist.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                recs.append((
                    datetime.fromisoformat(r["ts"]).timestamp(),
                    str(r.get("author") or "?"),
                    str(r.get("url") or ""),
                    bool(r.get("ok")),
                    str(r.get("skipped") or ""),
                    str(r.get("error") or ""),
                ))
            except Exception:
                continue
        # post_deleted (author removed the post) is expected, not actionable;
        # exclude from the >=3-failed alert (wd4 2026-10-08f).
        deleted_urls = {str(x.get("url") or "") for x in load_json(BOT / "retry_queue.json", [])
                        if str(x.get("skip_reason") or "") == "post_deleted"}
        last = {}
        for ts, author, url, ok, skipped, error in recs:
            if (ok or skipped == "pending_author_approval"
                    or error == "post_deleted" or url in deleted_urls):
                last[(url, author)] = ("ok", ts)
            else:
                if ts >= cutoff:
                    prev = last.get((url, author))
                    if prev is None or prev[0] == "ok" or prev[1] < ts:
                        last[(url, author)] = ("fail", ts)
        uniq = sorted({a for (u, a), (k, t) in last.items() if k == "fail"})
        if len(uniq) >= 3:
            alerts.append(
                "WATCHDOG: >=3 akun gagal di-reply dalam 2 jam terakhir: "
                + ", ".join("@" + a for a in uniq[:8])
            )

    # 5) Dead retry items (failed twice, stopped retrying) — but intentional
    # author-gate skips (skip_reason) are expected, not alerts.
    retry = load_json(BOT / "retry_queue.json", [])
    dead = sorted({str(r.get("author") or "?") for r in retry
                   if r.get("fails", 0) >= 2 and not r.get("skip_reason")})
    if dead:
        alerts.append(
            "WATCHDOG: post berhenti di-retry (gagal 2x): "
            + ", ".join("@" + a for a in dead[:8])
        )

    # 6) Browser session age (>25 days)
    st = BOT / "state.json"
    if st.exists():
        age_days = (datetime.now().timestamp() - st.stat().st_mtime) / 86400
        if age_days > 25:
            alerts.append(
                "WATCHDOG: sesi browser >25 hari; siapkan cookies baru sebelum reply mulai gagal."
            )

    # 7) Cron job missing or paused while session active
    jobs_file = CRON_DIR / "jobs.json"
    try:
        jobs = json.loads(jobs_file.read_text())
        seq = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
        job = None
        for j in seq:
            if j.get("job_id") == JOB_ID or j.get("id") == JOB_ID:
                job = j
                break
        if job is None:
            alerts.append("WATCHDOG: cron job threads-auto-cycle TIDAK DITEMUKAN di jobs.json.")
        elif session_active:
            state = str(job.get("state") or job.get("status") or "")
            if job.get("enabled") is False or state == "paused":
                alerts.append(
                    "WATCHDOG: cron threads-auto-cycle PAUSED padahal sesi masih aktif."
                )
    except Exception:
        pass

    if alerts:
        print("\n".join(sorted(set(alerts))))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"WATCHDOG: script error: {type(e).__name__}: {e}")
