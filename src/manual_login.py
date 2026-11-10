#!/usr/bin/env python3
"""Login manual Threads dengan username + password (tanpa ekspor cookies).

Dipakai saat sesi instance ini mati dan pemilik hanya bisa memberi username +
password, bukan cookies dari browser.

Cara pakai (di mesin bot, dari folder instance):
    ./venv/bin/python manual_login.py [--username NAMA]
    ./venv/bin/python manual_login.py --probe   # cek halaman login saja, tanpa login
    ./venv/bin/python manual_login.py --help

    atau lewat wrapper revival (sekaligus hidupkan daemon + promo):
    ./reactivate-blooply.sh --login [--username NAMA]

Alur:
  1. Username default = handle di account.json (boleh di-override --username).
  2. Password DITANYA saat runtime lewat getpass (tidak pernah jadi argumen
     baris perintah, tidak pernah ditulis ke file/log, tidak pernah dicetak).
  3. Browser headless (cloakbrowser, fingerprint sama seperti daemon) membuka
     halaman login Threads, mengisi form dengan gerakan manusiawi (hover dulu,
     ketik per karakter dengan jeda acak), lalu submit.
  4. Bila muncul tantangan verifikasi / 2FA / checkpoint: BERHENTI, sesi
     TIDAK disimpan, keluar kode 1. Pemilik harus menyelesaikan tantangan
     itu sendiri (di aplikasi/browser). Skrip ini tidak pernah bypass.
  5. Bila login gagal (password salah): BERHENTI, kode 2, sesi TIDAK disimpan.
  6. Bila sukses: sesi disimpan dulu ke file sementara, lalu diverifikasi
     lewat verify_account.py --state <file sementara>. Hanya bila MATCH,
     file sementara disalin ke state.json + storage_state.json (file lama
     di-backup .bak-<waktu>). Bila tidak MATCH, file sementara dihapus dan
     sesi lama TIDAK disentuh.

Exit code: 0 = sukses (MATCH, sesi tersimpan); 1 = tantangan verifikasi
(butuh tindakan pemilik); 2 = gagal lain (password salah, timeout,
halaman login tidak ditemukan, account.json hilang).
"""
from __future__ import annotations

import argparse
import getpass
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT))
import account_guard  # noqa: E402

LOGIN_URLS = ["https://www.threads.net/login", "https://www.threads.com/login"]
# Pasangan placeholder (username, password) yang dikenali, sesuai halaman
# login yang benar-benar tampil (di-probe 2026-11-10, bukan ditebak).
FIELD_PAIRS = [
    ("Username, phone or email", "Password"),
    ("Phone number, username, or email", "Password"),
]

CHALLENGE_MARKERS = [
    "verify your identity", "verification", "verify it's you",
    "check your email", "enter the code", "enter your code",
    "suspicious", "unusual login", "confirm your identity",
    "checkpoint", "two-factor", "two factor", "2-step",
    "security code", "we need to confirm", "help us confirm",
    "is this you", "confirm it's you", "we noticed an unusual",
    "verify your account",
]
WRONG_PASSWORD_MARKERS = [
    "incorrect password", "password you entered is incorrect",
    "sorry, your password", "couldn't log you in",
    "we couldn't log you in", "doesn't belong to an account",
    "username you entered doesn't belong",
    "the username or password you entered is incorrect",
]

TMP_STATE = BOT / "manual_login_tmp.json"


def fail(msg: str, code: int = 2) -> int:
    print(f"GAGAL: {msg}", file=sys.stderr)
    return code


def classify_body(body: str) -> str:
    """Klasifikasi teks halaman pasca-submit: challenge / wrong_password / unknown."""
    low = (body or "").lower()
    if any(m in low for m in CHALLENGE_MARKERS):
        return "challenge"
    if any(m in low for m in WRONG_PASSWORD_MARKERS):
        return "wrong_password"
    return "unknown"


def body_text(page) -> str:
    try:
        return page.evaluate("() => (document.body.innerText || '')")
    except Exception:
        return ""


def snippet(body: str, limit: int = 300) -> str:
    return " ".join((body or "").split())[:limit]


def human_type(locator, text: str) -> None:
    """Ketik per karakter dengan jeda acak, sesudah hover (gerak manusiawi)."""
    locator.hover()
    locator.click()
    locator.press_sequentially(text, delay=random.randint(50, 120))


def find_login_fields(page):
    """Cari pasangan field login yang tampil; kembalikan (user_loc, pass_loc) atau None."""
    for user_ph, pass_ph in FIELD_PAIRS:
        user_loc = page.locator(f'input[placeholder="{user_ph}"]').first
        pass_loc = page.locator(f'input[placeholder="{pass_ph}"]').first
        try:
            if user_loc.is_visible(timeout=5000) and pass_loc.is_visible(timeout=5000):
                return user_loc, pass_loc
        except Exception:
            continue
    return None


def open_login_page(page) -> bool:
    """Buka halaman login (coba threads.net dulu, lalu threads.com)."""
    last_err = None
    for url in LOGIN_URLS:
        for attempt in (1, 2):
            try:
                page.goto(url, timeout=120000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                return True
            except Exception as e:  # noqa: BLE001 - laporkan, coba lagi / URL berikut
                last_err = e
                print(f"-- gagal buka {url} (percobaan {attempt}): {type(e).__name__}")
                time.sleep(5)
    print(f"GAGAL: halaman login tidak bisa dibuka: {last_err}")
    return False


def quick_logged_in(page) -> bool:
    """Cek cepat (bukan bukti akhir): ada tautan profil di halaman ini?"""
    try:
        found = page.evaluate(
            """() => {
              const p = document.querySelector('a[aria-label="Profile"]')
                || document.querySelector('a[aria-label="Profil"]');
              if (p) return true;
              return document.querySelectorAll('nav a[href^="/@"]').length > 0;
            }"""
        )
        return bool(found)
    except Exception:
        return False


def dismiss_save_login(page) -> bool:
    """Tutup prompt 'Save your login info?' bila muncul (pilih Not Now)."""
    try:
        btn = page.get_by_text("Not Now", exact=True).first
        if btn.is_visible(timeout=3000):
            btn.hover()
            btn.click()
            page.wait_for_timeout(2000)
            return True
    except Exception:
        pass
    return False


def submit_login(page) -> None:
    """Submit form: Enter di field password, lalu fallback klik submit bila diam."""
    pw = page.locator('input[type="password"]').first
    pw.press("Enter")
    page.wait_for_timeout(5000)
    fields = find_login_fields(page)
    if fields is not None:
        print("-- Enter belum mengirim form, coba klik tombol submit...")
        try:
            sub = page.locator('input[type="submit"]').first
            if sub.is_visible(timeout=3000):
                sub.hover()
                sub.click()
                return
        except Exception:
            pass
        try:
            btn = page.get_by_text("Log in", exact=True).first
            if btn.is_visible(timeout=3000):
                btn.hover()
                btn.click()
        except Exception:
            pass


def save_session(ctx) -> int:
    """Simpan sesi ke file sementara, verifikasi MATCH, baru ganti file sesi.

    Mengembalikan 0 bila MATCH dan file sesi terganti, 2 bila tidak.
    """
    if TMP_STATE.exists():
        TMP_STATE.unlink()
    ctx.storage_state(path=str(TMP_STATE))
    print(f"-- sesi sementara tersimpan di {TMP_STATE.name}, verifikasi...")
    try:
        proc = subprocess.run(
            [sys.executable, str(BOT / "verify_account.py"), "--state", TMP_STATE.name],
            capture_output=True, text=True, cwd=str(BOT), timeout=180,
        )
    except Exception as e:  # noqa: BLE001
        print(f"GAGAL: verify_account.py tidak jalan: {e}")
        TMP_STATE.unlink(missing_ok=True)
        return 2
    out = (proc.stdout or "").strip()
    if out:
        print(out)
    if proc.returncode != 0 or "MATCH" not in out:
        print("GAGAL: sesi sementara tidak MATCH, file sesi lama TIDAK disentuh.")
        TMP_STATE.unlink(missing_ok=True)
        return 2
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in ("state.json", "storage_state.json"):
        target = BOT / name
        if target.exists():
            target.rename(BOT / f"{name}.bak-{ts}")
        shutil.copy2(TMP_STATE, target)
        target.chmod(0o600)
    TMP_STATE.unlink(missing_ok=True)
    print("OK: sesi tersimpan ke state.json + storage_state.json (backup .bak-"
          f"{ts})")
    return 0


def do_probe() -> int:
    """Mode --probe: muat halaman login, laporkan form yang tampil, tanpa login."""
    from cloakbrowser import launch

    browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
    try:
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        if not open_login_page(page):
            return 2
        print(f"URL: {page.url}")
        print(f"Judul: {page.title()}")
        fields = find_login_fields(page)
        if fields is None:
            print("GAGAL: field username/password tidak ditemukan di halaman login.")
            print("Cuplikan halaman:", snippet(body_text(page)))
            return 2
        print("OK: field login ditemukan (username + password, keduanya terlihat).")
        print("Cuplikan halaman:", snippet(body_text(page), 200))
        return 0
    finally:
        try:
            browser.close()
        except Exception:
            pass


def do_login(username: str) -> int:
    """Login penuh dengan username + password (password ditanya via getpass)."""
    from cloakbrowser import launch

    try:
        password = getpass.getpass("Password Threads/Instagram: ")
    except Exception:
        print("-- getpass gagal, baca password dari stdin (satu baris).")
        password = sys.stdin.readline().rstrip("\n")
    if not password:
        return fail("password kosong, batal.")
    browser = launch(headless=True, humanize=True, args=["--fingerprint=71529"])
    try:
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        if not open_login_page(page):
            return 2
        fields = find_login_fields(page)
        if fields is None:
            print("GAGAL: field username/password tidak ditemukan di halaman login.")
            print("Cuplikan halaman:", snippet(body_text(page)))
            return 2
        user_loc, pass_loc = fields
        print("-- mengisi username...")
        human_type(user_loc, username)
        time.sleep(random.uniform(0.5, 1.5))
        print("-- mengisi password...")
        human_type(pass_loc, password)
        # Hapus password dari memori sesegera mungkin setelah dipakai.
        password = "x" * 8
        del password
        time.sleep(random.uniform(0.5, 1.5))
        print("-- submit...")
        submit_login(page)

        deadline = time.time() + 90
        while time.time() < deadline:
            body = body_text(page)
            cls = classify_body(body)
            if cls == "challenge":
                print("TANTANGAN VERIFIKASI: Threads meminta verifikasi tambahan.")
                print("Cuplikan:", snippet(body))
                print("BERHENTI: selesaikan tantangan itu sendiri (di aplikasi "
                      "atau browser), lalu jalankan lagi skrip ini. Sesi TIDAK disimpan.")
                return 1
            if cls == "wrong_password":
                print("GAGAL: username/password salah (atau akun tidak ditemukan).")
                print("Cuplikan:", snippet(body))
                print("Periksa kredensial lalu jalankan lagi. Sesi TIDAK disimpan.")
                return 2
            if quick_logged_in(page):
                break
            time.sleep(3)

        ok, exp, found, via = account_guard.verify(page, BOT)
        if not ok and "save your login info" in body_text(page).lower():
            print("-- prompt 'Save login info' muncul, tutup dengan Not Now...")
            if dismiss_save_login(page):
                ok, exp, found, via = account_guard.verify(page, BOT)
        if not ok:
            print(f"GAGAL: verifikasi identitas tidak lolos (expected=@{exp} "
                  f"found={found} via={via}).")
            print("URL saat ini:", page.url)
            print("Cuplikan:", snippet(body_text(page)))
            return 2
        print(f"OK: guard lolos, sesi adalah @{found} (via={via})")
        return save_session(ctx)
    finally:
        try:
            browser.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Login manual Threads (username + password) untuk instance ini.",
    )
    ap.add_argument("--username", default=None,
                    help="username login (default: handle di account.json)")
    ap.add_argument("--probe", action="store_true",
                    help="cek halaman login saja, tanpa login dan tanpa password")
    args = ap.parse_args()

    if args.probe:
        return do_probe()

    expected = account_guard.load_expected(BOT)
    if not expected:
        return fail("account.json hilang/rusak di folder ini; tidak tahu akun mana "
                    "yang harus diloginkan. Batal.")
    username = (args.username or expected).strip().lstrip("@")
    if not username:
        return fail("username kosong, batal.")
    print(f"-- login sebagai {username} (akun instance: @{expected})")
    if username.lower() != expected.lower():
        print("-- PERINGATAN: username login berbeda dari handle instance. "
              "Sesi tetap diverifikasi terhadap account.json; bila tidak MATCH, "
              "sesi TIDAK disimpan.")
    return do_login(username)


if __name__ == "__main__":
    sys.exit(main())
