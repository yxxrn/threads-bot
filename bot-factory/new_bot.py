#!/usr/bin/env python3
"""Scaffold instance bot reply Threads baru (plug-and-play).

Satu perintah membuat satu folder instance lengkap dari kode general
(src/ + modes/<mode>/), siap dipasang sesi akunnya sendiri:

    python3 bot-factory/new_bot.py --handle @namaakun --mode affiliate
    python3 bot-factory/new_bot.py --handle @namaakun --mode text

Mode:
- affiliate: balasan bawa link katalog (model panah/clove), ada extra
  top-reply, media gate, filter title-paste + anti-generik.
- text: balasan teks saja (model blooply), tanpa link produk.

KEAMANAN (bawaan, bukan opsi):
- Instance baru SELALU lahir dengan file STOPPED: daemon menolak jalan
  sampai STOPPED dihapus atas perintah eksplisit pemilik.
- TIDAK ADA sesi yang disalin dari instance lain. state.json HANYA dari
  cookies akun itu sendiri; setiap pemasangan wajib lolos verify_account.py.
- Job Hermes baru dibuat NONAKTIF (enabled=false) sampai pemilik
  mengaktifkannya sendiri. Tanpa --apply-jobs, job hanya ditulis sebagai
  draf (jobs-draft.json) dan TIDAK menyentuh jobs.json sama sekali.
- Venv dipakai bersama (symlink) dari instance template, bukan disalin:
  affiliate -> threads-bot-panah/venv, text -> threads-bot/venv.
- Gambar katalog affiliate dipakai bersama (symlink) dari katalog panah.

Template kode dibaca dari root repo/template ini (folder yang memuat src/
dan modes/), kecuali --template-dir diubah. Job Hermes dibaca dari jobs.json
live agar prompt refill/watchdog selalu versi terbaru.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOME = Path("/home/agentuser")
DEFAULT_JOBS = HOME / ".hermes" / "cron" / "jobs.json"
DEFAULT_SCRIPTS = HOME / ".hermes" / "scripts"

# Template job Hermes (dicari berdasarkan nama dulu, lalu id).
TEMPLATE_JOBS = {
    "affiliate": {
        "dir": HOME / "threads-bot-panah",
        "venv": HOME / "threads-bot-panah" / "venv",
        "images": HOME / "threads-bot-panah" / "catalog" / "images",
        "names": ("panah-scraper", "panah-auto-cycle", "panah-watchdog"),
        "ids": ("63af158056fb", "9adfa87339ee", "a07f31ac7236"),
        "scripts": ("panah-scraper.sh", "panah-monitor.sh"),
        "handle_variants": ("@panahberuang", "panahberuang", "PANAH", "Panah"),
    },
    "text": {
        "dir": HOME / "threads-bot",
        "venv": HOME / "threads-bot" / "venv",
        "images": None,
        "names": ("threads-scraper", "threads-auto-cycle", "threads-watchdog"),
        "ids": ("2db0293bc2a4", "6e020e0bb0cd", "d5d893898807"),
        "scripts": ("threads_scraper.sh", "threads_monitor_all.sh"),
        "handle_variants": (),
    },
}

SRC_FILES = [
    "account_guard.py", "verify_account.py", "queue_status.py",
    "build_pool.py", "scraper_cycle.py", "check_login.py",
    "check_reply_session.py", "threads_monitor_all.py",
]
MODE_FILES = {
    "affiliate": [
        "poster_daemon.py", "auto_comment.py", "merge_comments.py",
        "pick_drafts.py", "fetch_top_reply.py", "top_reply_config.json",
        "scraper_keywords.json", "catalog.json",
    ],
    "text": [
        "poster_daemon.py", "auto_comment.py", "merge_comments.py",
        "pick_drafts.py", "scraper_keywords.json", "photo_disabled.json",
    ],
}
JOB_INTERVALS = {"scraper": 30, "auto-cycle": 15, "watchdog": 30}


def fail(msg: str) -> None:
    print(f"new_bot: ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def bounded_sub(text: str, old: str, new: str) -> str:
    """Ganti old hanya bila tidak ditempel kata lain (cegah tabrakan prefix
    seperti threads-bot vs threads-bot-panah)."""
    return re.sub(re.escape(old) + r"(?![A-Za-z0-9_-])", new, text)


def display_name(slug: str) -> str:
    first = re.split(r"[._-]+", slug)[0]
    return first[:1].upper() + first[1:] if first else slug


def load_jobs(path: Path):
    data = json.loads(path.read_text())
    seq = data if isinstance(data, list) else data.get("jobs", [])
    return data, seq


def find_template_job(seq, name: str, jid: str):
    for j in seq:
        if j.get("name") == name:
            return j
    for j in seq:
        if j.get("id") == jid:
            return j
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold instance bot Threads baru.")
    ap.add_argument("--handle", required=True, help="Handle akun, pakai @ (mis. @namaakun)")
    ap.add_argument("--mode", required=True, choices=["affiliate", "text"])
    ap.add_argument("--template-dir", default=None,
                    help="Root template (berisi src/ + modes/). Default: parent folder script ini.")
    ap.add_argument("--jobs-file", default=str(DEFAULT_JOBS))
    ap.add_argument("--scripts-dir", default=str(DEFAULT_SCRIPTS))
    ap.add_argument("--apply-jobs", action="store_true",
                    help="Tulis 3 job ke jobs.json (NONAKTIF) + pasang 2 script. Tanpa flag ini hanya draf.")
    args = ap.parse_args()

    handle = args.handle.strip()
    if not re.fullmatch(r"@[A-Za-z0-9._]{1,30}", handle):
        fail(f"handle tidak valid: {handle!r} (pakai @ + huruf/angka/titik/underscore)")
    slug = handle[1:].lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
        fail(f"slug tidak valid dari handle: {slug!r}")
    mode = args.mode
    tpl = TEMPLATE_JOBS[mode]

    root = Path(args.template_dir) if args.template_dir else Path(__file__).resolve().parent.parent
    src_dir, mode_dir = root / "src", root / "modes" / mode
    for d in (src_dir, mode_dir):
        if not d.is_dir():
            fail(f"template tidak ditemukan: {d} (pakai --template-dir bila perlu)")

    target = HOME / f"threads-bot-{slug}"
    if target.exists():
        fail(f"folder sudah ada: {target} (pakai nama lain / remove_bot.py dulu)")

    jobs_path = Path(args.jobs_file)
    scripts_dir = Path(args.scripts_dir)
    if not jobs_path.exists():
        fail(f"jobs.json tidak ditemukan: {jobs_path}")
    jobs_data, seq = load_jobs(jobs_path)
    existing_ids = {j.get("id") for j in seq}

    # --- 1. Salin kode general ---
    target.mkdir()
    (target / "shots").mkdir()
    for f in SRC_FILES:
        src = src_dir / f
        if not src.exists():
            fail(f"file template hilang: {src}")
        shutil.copy2(src, target / f)
    for f in MODE_FILES[mode]:
        src = mode_dir / f
        if not src.exists():
            fail(f"file template hilang: {src}")
        shutil.copy2(src, target / f)

    # --- 2. Venv bersama (symlink) + gambar katalog bersama (affiliate) ---
    venv_path = tpl["venv"]
    (target / "venv").symlink_to(venv_path, target_is_directory=True)
    if not (target / "venv" / "bin" / "python").exists():
        print(f"new_bot: PERINGATAN: venv template tidak ditemukan: {venv_path}")
    if mode == "affiliate" and tpl["images"] is not None:
        (target / "catalog").mkdir(exist_ok=True)
        link = target / "catalog" / "images"
        if tpl["images"].exists():
            link.symlink_to(tpl["images"], target_is_directory=True)
        else:
            print(f"new_bot: PERINGATAN: gambar katalog template tidak ada: {tpl['images']}")

    # --- 3. Identitas + pengaman bawaan ---
    (target / "account.json").write_text(json.dumps(
        {"handle": slug, "guard": "account_guard.py"}, indent=2) + "\n")
    (target / "session_meta.json").write_text(json.dumps({
        "handle": slug, "mode": mode,
        "session_status": "NONE (belum ada sesi; pasang cookies akun ini dulu)",
        "daemon": "STOPPED sejak scaffold (bawaan factory; hapus STOPPED hanya "
                  "setelah verify_account.py MATCH + perintah eksplisit pemilik)",
        "guard": "account_guard.py + verify_account.py",
        "venv_shared_from": str(venv_path),
    }, indent=2, ensure_ascii=False) + "\n")
    (target / "STOPPED").write_text(
        "Parkir bawaan factory: instance baru, belum ada sesi akun ini.\n"
        "Hapus file ini HANYA setelah cookies akun ini terpasang dan "
        "verify_account.py mencetak MATCH, atas perintah eksplisit pemilik.\n")
    for name in ("comments.json", "comments_new.json", "replied_urls.json"):
        (target / name).write_text("[]\n")
    unit = f"threads-poster-daemon-{slug}"
    new_job_names = (f"{slug}-scraper", f"{slug}-auto-cycle", f"{slug}-watchdog")
    new_script_names = (f"{slug}-scraper.sh", f"{slug}-monitor.sh")

    (target / "WATCHDOG.md").write_text(
        f"# Playbook watchdog instance @{slug} (mode {mode})\n\n"
        f"- Folder instance: {target}\n"
        f"- Unit daemon: {unit} (transient, systemd-run --user)\n"
        f"- Venv (dipakai bersama): {venv_path}\n"
        f"- Perintah start daemon:\n"
        f"  systemd-run --user --unit={unit} --collect \\\n"
        f"    --working-directory={target} \\\n"
        f"    {venv_path}/bin/python {target}/poster_daemon.py\n"
        f"- Verifikasi: `pgrep -f poster_daemon.py` (cek cwd == folder instance)\n"
        f"  + `tail -3 {target}/daemon.log`.\n\n"
        f"## ATURAN STOP SENGAJA (mengalahkan perintah restart apa pun)\n"
        f"Selama file STOPPED ada di folder instance, daemon yang TIDAK jalan\n"
        f"BUKAN masalah dan JANGAN di-restart. STOPPED hanya boleh dihapus atas\n"
        f"perintah eksplisit pemilik, atau saat sesi baru akun ini dipasang dan\n"
        f"guard identitas lolos (verify_account.py MATCH).\n\n"
        f"## ATURAN SESI (pelajaran insiden 2026-11-03)\n"
        f"- JANGAN PERNAH menyalin state.json dari instance lain. Sesi tiap akun\n"
        f"  hanya berasal dari cookies akun itu sendiri.\n"
        f"- Setiap pemasangan sesi: backup state.json lama dulu, lalu wajib lolos\n"
        f"  `verify_account.py` (MATCH) sebelum daemon boleh jalan.\n"
        f"- Bukti login yang sah HANYA tautan profil navigasi (aria-profile/nav);\n"
        f"  tautan feed BUKAN bukti (guard menolaknya sebagai feed-only).\n"
        f"- Sesi reply WAJIB diverifikasi di halaman post (check_reply_session.py),\n"
        f"  bukan halaman home (cek home pernah memberi false positive).\n")

    (target / "SETUP.md").write_text(
        f"# Aktivasi instance @{slug} (mode {mode})\n\n"
        f"Instance ini dibuat oleh bot-factory dan lahir dalam keadaan PARKIR\n"
        f"(file STOPPED ada, job Hermes belum aktif). Urutan aktivasi:\n\n"
        f"1. SESI (wajib dari akun ini sendiri): minta cookies segar akun @{slug}\n"
        f"   (format Netscape dari Cookie-Editor), konversi ke Playwright\n"
        f"   storage_state, tulis ke {target}/state.json (backup dulu bila ada).\n"
        f"   JANGAN PERNAH menyalin state.json dari instance lain.\n"
        f"2. VERIFIKASI: `{venv_path}/bin/python {target}/verify_account.py`\n"
        f"   harus mencetak MATCH. Bila MISMATCH/UNDETERMINED: berhenti, jangan\n"
        f"   lanjut (sesi salah atau logout).\n"
        f"3. HAPUS STOPPED hanya atas perintah eksplisit pemilik:\n"
        f"   `rm {target}/STOPPED`\n"
        f"4. JOB: {'aktifkan 3 job di bawah (dibuat nonaktif oleh factory)' if args.apply_jobs else 'pasang job dari draf jobs-draft.json (lihat --apply-jobs)'}\n"
        f"   lalu start daemon:\n"
        f"   `systemd-run --user --unit={unit} --collect "
        f"--working-directory={target} {venv_path}/bin/python {target}/poster_daemon.py`\n"
        f"5. VERIFIKASI POST PERTAMA: 1 post OK sebagai @{slug} di daemon.log\n"
        f"   sebelum menyatakan instance jalan.\n\n"
        f"## Yang masih perlu disesuaikan manual (template dari akun {mode})\n"
        + ("- PERSONA: prompt refill memakai persona template (panah). Sesuaikan\n"
           "  bagian persona di job auto-cycle dengan karakter akun baru.\n"
           "- KEYWORD: scraper_keywords.json disalin dari template. Bila akun ini\n"
           "  jalan BERSAMAAN dengan akun template, pisahkan keyword dulu (nol\n"
           "  tumpang tindih) supaya tidak berebut target yang sama. Bila akun ini\n"
           "  MENGGANTIKAN akun template, keyword boleh dipakai apa adanya.\n"
           "- GAMBAR: catalog/images adalah symlink ke katalog panah. Bila katalog\n"
           "  panah diarsipkan, arahkan ulang symlink ini.\n" if mode == "affiliate" else
           "- PROMOSI: prompt refill memakai promosi halus Blooply sebagai template.\n"
           "  Ganti dengan produk/layanan akun baru sebelum mengaktifkan refill.\n"
           "- KEYWORD: scraper_keywords.json disalin dari template blooply. Bila akun\n"
           "  ini jalan bersamaan dengan blooply, pisahkan keyword dulu.\n")
        + f"\nUnit: {unit} | Venv: {venv_path} | Job: {', '.join(new_job_names)}\n")

    # --- 4. Job Hermes (draf; opsional diterapkan nonaktif) ---
    new_ids = []
    for _ in range(3):
        while True:
            nid = secrets.token_hex(6)
            if nid not in existing_ids and nid not in new_ids:
                new_ids.append(nid)
                break
    old_dir = str(tpl["dir"])
    new_dir = str(target)
    disp = display_name(slug)
    entries = []
    for role, (tname, tid) in enumerate(zip(tpl["names"], tpl["ids"])):
        tmpl = find_template_job(seq, tname, tid)
        if tmpl is None:
            fail(f"job template tidak ditemukan: {tname} / {tid}")
        e = json.loads(json.dumps(tmpl))
        prompt = e.get("prompt") or ""
        prompt = bounded_sub(prompt, old_dir, new_dir)
        for tn, nn in zip(tpl["names"], new_job_names):
            prompt = prompt.replace(tn, nn)
        if mode == "affiliate":
            for old_v in tpl["handle_variants"]:
                new_v = {"@panahberuang": "@" + slug,
                         "panahberuang": slug, "PANAH": disp.upper(),
                         "Panah": disp}.get(old_v, old_v)
                prompt = prompt.replace(old_v, new_v)
        prompt = re.sub(r"threads-poster-daemon(?![A-Za-z0-9_-])", unit, prompt)
        prompt += (
            f"\n\n[INSTANCE FACTORY] Akun: @{slug} | Folder: {new_dir} | "
            f"Unit daemon: {unit} | Venv: {venv_path}. "
            f"ATURAN STOP SENGAJA: selama file STOPPED ada di folder instance, "
            f"daemon yang tidak jalan BUKAN masalah dan JANGAN di-restart; "
            f"STOPPED hanya boleh dihapus atas perintah eksplisit pemilik atau "
            f"saat sesi baru akun ini lolos verify_account.py.")
        e["prompt"] = prompt
        e["id"] = new_ids[role]
        e["name"] = new_job_names[role]
        e["workdir"] = new_dir if tmpl.get("workdir") else None
        if role == 0:
            e["script"] = new_script_names[0]
        if role == 2:
            e["monitor_script"] = new_script_names[1]
        e["enabled"] = False
        e["state"] = "scheduled"
        e["paused_at"] = None
        e["paused_reason"] = None
        e["created_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        e["next_run_at"] = None
        e["last_run_at"] = None
        e["last_status"] = None
        e["last_error"] = None
        e["last_delivery_error"] = None
        e["last_delivery_unverified"] = None
        e["failure_streak"] = 0
        e["last_dispatch"] = None
        e["fire_claim"] = None
        e["repeat"] = {"times": None, "completed": 0}
        e["monitor_state"] = None
        entries.append(e)
    (target / "jobs-draft.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n")

    # --- 5. Script .sh (draf) ---
    scripts_draft = target / "scripts-draft"
    scripts_draft.mkdir()
    for role, tscript in enumerate(tpl["scripts"]):
        src = scripts_dir / tscript
        if not src.exists():
            fail(f"script template tidak ditemukan: {src}")
        text = src.read_text()
        text = bounded_sub(text, old_dir, new_dir)
        text = text.replace(tpl["ids"][1], new_ids[1])
        text = text.replace(tpl["names"][0], new_job_names[0])
        text = text.replace(tpl["names"][1], new_job_names[1])
        text = text.replace(tpl["names"][2], new_job_names[2])
        (scripts_draft / new_script_names[role]).write_text(text)

    # --- 6. Cek sisa template (peringatan, bukan gagal) ---
    # Catatan: path venv bersama (mis. threads-bot-panah/venv) memang sengaja
    # dipertahankan, dan folder baru (threads-bot-dummytext) mengandung path
    # template (threads-bot) sebagai prefix. Karena itu pengecekan memakai
    # pola berbatas + mengecualikan path venv, bukan substring mentah.
    leftovers = []
    for f in list(target.glob("*.py")) + list(target.glob("*.json")):
        if f.name in ("jobs-draft.json", "account.json", "session_meta.json"):
            continue
        t = f.read_text(errors="replace")
        if re.search(re.escape(old_dir) + r"(?![A-Za-z0-9_-])", t):
            leftovers.append(f"{f.name}: sisa path template")
    draft_text = (target / "jobs-draft.json").read_text()
    draft_check = draft_text.replace(str(venv_path), "")
    if re.search(re.escape(old_dir) + r"(?![A-Za-z0-9_-])", draft_check):
        leftovers.append("jobs-draft.json: sisa path template")
    for probe in (tpl["names"][0], tpl["names"][1], tpl["names"][2],
                  "@panahberuang"):
        if probe in draft_text:
            leftovers.append(f"jobs-draft.json: sisa {probe!r}")
    for w in leftovers:
        print(f"new_bot: PERINGATAN: {w}")

    manifest = {
        "handle": slug, "mode": mode, "slug": slug, "unit": unit,
        "instance_dir": new_dir, "venv_shared_from": str(venv_path),
        "template_root": str(root),
        "job_ids": None, "scripts": None,
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }
    if args.apply_jobs:
        bak = jobs_path.with_name(
            jobs_path.name + ".bak-" +
            datetime.now().strftime("%Y%m%d-%H%M") + "-factory")
        shutil.copy2(jobs_path, bak)
        if isinstance(jobs_data, list):
            jobs_data.extend(entries)
        else:
            jobs_data.setdefault("jobs", []).extend(entries)
        tmp = jobs_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(jobs_data, indent=2, ensure_ascii=False) + "\n")
        json.loads(tmp.read_text())
        tmp.replace(jobs_path)
        for role in range(2):
            dst = scripts_dir / new_script_names[role]
            if dst.exists():
                fail(f"script sudah ada (batal, jobs sudah tertulis): {dst}")
            shutil.copy2(scripts_draft / new_script_names[role], dst)
            dst.chmod(0o755)
        manifest["job_ids"] = {"scraper": new_ids[0], "auto-cycle": new_ids[1],
                               "watchdog": new_ids[2]}
        manifest["scripts"] = list(new_script_names)
        manifest["jobs_backup"] = str(bak)
        print(f"new_bot: job diterapkan NONAKTIF (backup: {bak})")
    (target / "factory.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print(f"new_bot: instance @{slug} ({mode}) siap di {target}")
    print(f"new_bot: unit={unit} job={', '.join(new_job_names)} "
          f"({'diterapkan nonaktif' if args.apply_jobs else 'draf saja'})")
    print(f"new_bot: aktivasi: pasang cookies @{slug} -> verify MATCH -> "
          f"hapus STOPPED -> aktifkan job -> start daemon -> verifikasi post pertama")


if __name__ == "__main__":
    main()
