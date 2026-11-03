#!/usr/bin/env python3
"""Lepas (bongkar) satu instance bot reply Threads.

    python3 bot-factory/remove_bot.py /home/agentuser/threads-bot-nama

Yang dilakukan, berurutan:
1. Baca factory.json di folder instance (asal-usul job + script + unit).
2. Hentikan unit daemon bila masih jalan.
3. Hapus 3 job Hermes milik instance dari jobs.json (backup dulu).
4. Hapus 2 script Hermes milik instance.
5. PINDAHKAN folder instance ke bots-archive/<slug>-<waktu>/ (bukan hapus).

Instance TIDAK pernah dihapus permanen oleh script ini; arsip selalu bisa
dikembalikan manual. Instance warisan (threads-bot, threads-bot-panah,
threads-bot-clove) tidak punya factory.json dan DITOLAK kecuali --force
disertai --job-ids dan --scripts eksplisit.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOME = Path("/home/agentuser")
DEFAULT_JOBS = HOME / ".hermes" / "cron" / "jobs.json"
DEFAULT_SCRIPTS = HOME / ".hermes" / "scripts"
ARCHIVE_ROOT = HOME / "bots-archive"
LEGACY = {"threads-bot", "threads-bot-panah", "threads-bot-clove"}


def fail(msg: str) -> None:
    print(f"remove_bot: ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Lepas satu instance bot Threads.")
    ap.add_argument("instance", help="Folder instance (mis. /home/agentuser/threads-bot-nama)")
    ap.add_argument("--jobs-file", default=str(DEFAULT_JOBS))
    ap.add_argument("--scripts-dir", default=str(DEFAULT_SCRIPTS))
    ap.add_argument("--force", action="store_true",
                    help="Izinkan instance warisan tanpa factory.json.")
    ap.add_argument("--job-ids", default="",
                    help="Daftar id job dipisah koma (wajib bila --force tanpa factory.json).")
    ap.add_argument("--scripts", default="",
                    help="Daftar nama script dipisah koma (wajib bila --force tanpa factory.json).")
    args = ap.parse_args()

    target = Path(args.instance)
    if not target.is_dir():
        fail(f"folder tidak ada: {target}")
    slug = target.name
    manifest = {}
    mpath = target / "factory.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text())
    elif slug in LEGACY and not args.force:
        fail(f"{slug} adalah instance warisan tanpa factory.json; "
             f"pakai --force + --job-ids + --scripts bila memang mau dilepas")
    elif not args.force:
        fail(f"tidak ada factory.json di {target}; pakai --force + "
             f"--job-ids + --scripts bila memang mau dilepas")

    unit = manifest.get("unit") or f"threads-poster-daemon-{slug.replace('threads-bot-', '')}"
    job_ids = manifest.get("job_ids") or {}
    if isinstance(job_ids, dict):
        job_id_list = [v for v in job_ids.values() if v]
    else:
        job_id_list = list(job_ids)
    if args.job_ids:
        job_id_list = [x for x in args.job_ids.split(",") if x.strip()]
    script_names = manifest.get("scripts") or []
    if args.scripts:
        script_names = [x for x in args.scripts.split(",") if x.strip()]
    if not job_id_list and not script_names:
        print("remove_bot: peringatan: tidak ada job/script yang dikenali; "
              "hanya mengarsipkan folder.")

    # 1. Hentikan daemon bila jalan (unit transient/persisten milik instance).
    import subprocess
    chk = subprocess.run(["systemctl", "--user", "is-active", unit],
                         capture_output=True, text=True)
    if chk.stdout.strip() == "active":
        subprocess.run(["systemctl", "--user", "stop", unit], check=False)
        chk2 = subprocess.run(["systemctl", "--user", "is-active", unit],
                              capture_output=True, text=True)
        if chk2.stdout.strip() == "active":
            fail(f"unit {unit} masih aktif setelah stop; batalkan pelepasan")
        print(f"remove_bot: unit {unit} dihentikan")

    # 2. Hapus job dari jobs.json (backup dulu).
    jobs_path = Path(args.jobs_file)
    jobs_data = json.loads(jobs_path.read_text())
    seq = jobs_data if isinstance(jobs_data, list) else jobs_data.get("jobs", [])
    before = len(seq)
    keep = [j for j in seq if j.get("id") not in set(job_id_list)]
    removed = before - len(keep)
    if job_id_list and removed != len(job_id_list):
        print(f"remove_bot: peringatan: {len(job_id_list) - removed} id job "
              f"tidak ditemukan di jobs.json (mungkin sudah dihapus)")
    if isinstance(jobs_data, list):
        jobs_data = keep
    else:
        jobs_data["jobs"] = keep
    bak = jobs_path.with_name(jobs_path.name + ".bak-" +
                              datetime.now().strftime("%Y%m%d-%H%M") + "-factory-rm")
    shutil.copy2(jobs_path, bak)
    tmp = jobs_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(jobs_data, indent=2, ensure_ascii=False) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(jobs_path)
    print(f"remove_bot: {removed} job dihapus dari jobs.json (backup: {bak})")

    # 3. Hapus script.
    scripts_dir = Path(args.scripts_dir)
    for s in script_names:
        p = scripts_dir / s
        if p.exists():
            p.unlink()
            print(f"remove_bot: script dihapus: {p}")
        else:
            print(f"remove_bot: script tidak ada (lewati): {p}")

    # 4. Arsipkan folder (bukan hapus).
    ARCHIVE_ROOT.mkdir(exist_ok=True)
    dest = ARCHIVE_ROOT / f"{slug}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    if dest.exists():
        fail(f"tujuan arsip sudah ada: {dest}")
    shutil.move(str(target), str(dest))
    print(f"remove_bot: instance {slug} diarsipkan ke {dest}")
    print("remove_bot: SELESAI (tidak ada yang dihapus permanen)")


if __name__ == "__main__":
    main()
