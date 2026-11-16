#!/usr/bin/env python3
"""Login manual Threads dengan username + password (tanpa ekspor cookies).

Dipakai saat sesi instance ini mati dan pemilik hanya bisa memberi username +
password, bukan cookies dari browser.

Cara pakai (di mesin bot, dari folder instance):
    ./venv/bin/python manual_login.py [--username NAMA]
    ./venv/bin/python manual_login.py --probe   # cek halaman login saja, tanpa login
    ./venv/bin/python manual_login.py --help
    ./venv/bin/python manual_login.py --request-code  # login + pencet "get a code" 1x, lalu berhenti (tanpa simpan sesi)
    echo 123456 | ./venv/bin/python manual_login.py --code-stdin  # login + masukkan kode
    ./venv/bin/python manual_login.py --request-code-wait  # SATU SESI: login + pencet kode 1x + tunggu kode di stdin + masukkan, tanpa login ulang (kirim 'press' via stdin untuk pencet lagi, 'batal' untuk berhenti)

    atau lewat wrapper revival (sekaligus hidupkan daemon + promo):
    ./reactivate-blooply.sh --login [--username NAMA]
    ./reactivate-blooply.sh --login --request-code
    echo 123456 | ./reactivate-blooply.sh --login --code-stdin

Alur:
  1. Username default = handle di account.json (boleh di-override --username).
  2. Password DITANYA saat runtime lewat getpass (tidak pernah jadi argumen
     baris perintah, tidak pernah ditulis ke file/log, tidak pernah dicetak).
     Bila file .env di folder ini berisi THREADS_PASSWORD, nilai itu
     dipakai dulu (dan THREADS_USERNAME bila ada); bila tidak ada,
     password ditanya seperti biasa. File .env wajib chmod 600 dan
     tidak pernah di-commit.
  3. Browser headless (cloakbrowser, fingerprint sama seperti daemon) membuka
     halaman login Threads, mengisi form dengan gerakan manusiawi (hover dulu,
     ketik per karakter dengan jeda acak), lalu submit.
  4. Bila muncul tantangan verifikasi / 2FA / checkpoint: BERHENTI, sesi
     TIDAK disimpan, keluar kode 1. Pemilik harus menyelesaikan tantangan
     itu sendiri (di aplikasi/browser). Skrip ini tidak pernah bypass.
     Dua pengecualian opt-in (flag):
     --request-code: saat tantangan muncul, pencet tombol "get a code"
       SEKALI (aturan Amad 16 Nov 22:46 WIB: satu pencet = satu kode;
       pencet berulang mengirim banyak kode), lalu keluar kode 1 TANPA
       menyimpan sesi. Dipakai sekali saja atas perintah pemilik, karena
       setiap penekanan meminta kode baru yang mengalahkan kode lama.
     --code-stdin: baca 6 digit dari stdin (BUKAN argv/env), masukkan ke
       kolom kode di form tantangan, submit, lalu lanjut ke jalur
       simpan-sesi normal. Kode TIDAK PERNAH dicetak, dilog, atau ditulis
       ke file mana pun.
     --request-code-wait: SATU SESI penuh tanpa reload (aturan Amad 16 Nov
       22:30 WIB): login -> tantangan muncul -> pencet "get a code" 1x ->
       TUNGGU 6 digit dari stdin (browser tetap terbuka, maks 15 menit) ->
       masukkan kode di sesi yang sama -> simpan sesi -> hidupkan daemon +
       promo. Selama menunggu, stdin juga menerima perintah 'press'
       (pencet lagi 1x di sesi yang sama, tanpa login ulang) dan 'batal'.
     TANPA ketiga flag, perilaku persis seperti butir 4 lama: berhenti saat
     tantangan, tanpa klik apa pun. Cron pengawas sesi menjalankan --login
     tanpa flag, jadi tidak pernah meminta kode baru.
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
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
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

def load_env() -> None:
    """Muat BOT/.env bila ada (THREADS_USERNAME/THREADS_PASSWORD).

    File .env (chmod 600) dibaca sebagai default; environment asli yang
    sudah ada selalu menang (setdefault). Nilai tidak pernah dicetak.
    """
    env_file = BOT / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("'\"")
            if key in ("THREADS_USERNAME", "THREADS_PASSWORD"):
                os.environ.setdefault(key, val)
    except Exception:
        pass



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


# Teks tombol "minta kode" di halaman tantangan, sesuai urutan coba. Hanya
# tombol yang teksnya cocok dengan salah satu label ini yang diklik; tidak
# ada tombol lain yang disentuh. "Send a new code" muncul SETELAH hitung
# mundur cooldown habis (sebelumnya hanya teks timer, bukan tombol).
REQUEST_CODE_LABELS = [
    "Get a code", "Send code", "Send a code", "Get code",
    "Send a new code", "Resend code", "Get a new code", "Send new code",
    "Kirim kode", "Minta kode",
]
# Penanda halaman pasca-klik bahwa kode sudah dikirim.
CODE_SENT_MARKERS = [
    "code sent", "we sent", "sent a code", "check your email",
    "sent to", "kode dikirim", "kode telah dikirim", "kami mengirim",
]
# Email tersamar seperti yang ditampilkan Threads (mis. r******a@gmail.com).
MASKED_EMAIL_RE = re.compile(r"[A-Za-z0-9._*\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# Penanda timer cooldown pengiriman ulang kode, mis. "We can send a new code
# in 0:08" / "Send a new code in 1:23" / "try again in 0:45". Timer ini
# BUKTI kode benar-benar terkirim (aturan Amad 16 Nov 22:15 WIB): teks
# "code sent" di halaman tantangan saja TIDAK cukup, 12 Nov terbukti email
# kode tidak pernah sampai walau halaman mengklaim kode sudah dikirim.
# Jadi tombol "get a code" diklik BERULANG sampai timer ini muncul.
COOLDOWN_TIMER_RES = [
    re.compile(r"send a new code in\s*\d+:\d+", re.IGNORECASE),
    re.compile(r"try again in\s*\d+:\d+", re.IGNORECASE),
    re.compile(r"resend (a )?code in\s*\d+:\d+", re.IGNORECASE),
    re.compile(r"new code in\s*\d+:\d+", re.IGNORECASE),
    re.compile(r"kirim ulang kode dalam\s*\d+:\d+", re.IGNORECASE),
    re.compile(r"coba lagi dalam\s*\d+:\d+", re.IGNORECASE),
]


def wib_now_str() -> str:
    return datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S WIB")


def find_request_code_button(page):
    """Cari tombol 'minta kode' di halaman tantangan; kembalikan (locator, label) atau (None, None)."""
    for label in REQUEST_CODE_LABELS:
        try:
            btn = page.get_by_role("button", name=label, exact=True).first
            if btn.is_visible(timeout=1500):
                return btn, label
        except Exception:
            continue
    for label in REQUEST_CODE_LABELS:
        try:
            el = page.get_by_text(label, exact=True).first
            if el.is_visible(timeout=1500):
                return el, label
        except Exception:
            continue
    # Tier terakhir: teks sebagian "send a new code" / "resend code" (tombol
    # kirim ulang yang muncul setelah hitung mundur habis).
    for pat in ("send a new code", "resend code"):
        try:
            el = page.locator(f"text=/{pat}/i").first
            if el.is_visible(timeout=1500):
                return el, pat
        except Exception:
            continue
    return None, None


def cooldown_timer_text(body: str):
    """Kembalikan teks timer cooldown bila ada di halaman, atau None."""
    for rx in COOLDOWN_TIMER_RES:
        m = rx.search(body or "")
        if m:
            return m.group(0)
    return None


def cooldown_seconds(timer_text: str):
    """Ubah teks timer 'M:SS' jadi detik (int), atau None bila tidak cocok."""
    m = re.search(r"(\d+):(\d+)", timer_text or "")
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def safe_click(page, loc) -> bool:
    """Klik elemen dengan fallback berlapis.

    Lapisan 1: hover + klik biasa (gerak manusiawi via cloakbrowser).
    Lapisan 2: klik lewat koordinat mouse (bounding box) — dipakai bila
      humanize menolak selector-nya (UnsupportedHumanizeSelectorError,
      terjadi live 16 Nov 22:34 WIB pada tombol 'Get a new code').
    Lapisan 3: klik via JavaScript (terakhir, bila mouse juga gagal).
    Return True bila salah satu lapisan berhasil (tanpa exception).
    """
    try:
        loc.hover()
        loc.click()
        return True
    except Exception:
        pass
    try:
        box = loc.bounding_box(timeout=3000)
    except Exception:
        box = None
    if box:
        try:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y, steps=8)
            page.wait_for_timeout(random.randint(150, 400))
            page.mouse.click(x, y)
            return True
        except Exception:
            pass
    try:
        loc.evaluate("el => el.click()")
        return True
    except Exception:
        return False


def press_request_code_once(page) -> bool:
    """Pencet tombol 'minta kode' SEKALI, di halaman tantangan yang sama.

    Aturan Amad (16 Nov 22:46 WIB): minta kode lagi cukup SATU pencet.
    Pencet berulang malah mengirim BANYAK kode (terbukti malam ini: 5x
    pencet -> 2 kode masuk ke email). Satu pencet = satu kode.

    Bila hitung mundur cooldown masih berjalan, tombol kirim ulang BELUM
    ADA di halaman — hanya teks timer (ditemukan live 16 Nov 22:32 WIB).
    Jadi tunggu hitung mundurnya habis dulu, baru cari + pencet tombolnya.
    TIDAK ADA reload/navigasi.

    Sukses = tombol ditemukan dan berhasil diklik (safe_click). TIDAK ADA
    verifikasi timer baru: Threads tidak selalu menampilkan timer baru
    setelah kirim ulang (halaman hanya menampilkan "It may take a few
    minutes..."), jadi timer bukan bukti pengiriman. Bukti sebenarnya
    adalah email kode yang sampai — itu dicek pemilik di Gmail.

    Return True bila tombol berhasil dipencet, False bila gagal.
    """
    body = body_text(page)
    timer0 = cooldown_timer_text(body)
    if timer0:
        secs = cooldown_seconds(timer0)
        if secs is not None and secs > 0:
            wait = min(secs + 5, 300)
            print(f"-- timer cooldown tampil ('{timer0}'): tombol kirim ulang "
                  f"baru ada setelah hitung mundur habis; menunggu {wait} detik...")
            page.wait_for_timeout(wait * 1000)
    btn, label = find_request_code_button(page)
    if btn is None:
        print("GAGAL: tombol 'get a code' TIDAK ditemukan di halaman tantangan.")
        print("Teks halaman persisnya:")
        print("----")
        print(" ".join((body_text(page) or "").split())[:2000])
        print("----")
        return False
    print(f"-- tombol 'minta kode' ditemukan ('{label}'), pencet sekali...")
    if not safe_click(page, btn):
        print("GAGAL: tombol ditemukan tapi tidak bisa diklik (3 lapisan gagal).")
        return False
    page.wait_for_timeout(5000)
    after = body_text(page)
    print("Kode diminta (1x pencet). Cuplikan pasca-pencet:", snippet(after))
    print(f"Jam: {wib_now_str()}")
    masked2 = MASKED_EMAIL_RE.search(after or "")
    if masked2:
        print(f"Email tujuan (tersamar): {masked2.group(0)}")
    return True


def request_verification_code(page) -> int:
    """Pencet tombol 'minta kode' SEKALI, lalu berhenti.

    Selalu mengembalikan 1 (tantangan); sesi TIDAK disimpan. Dipakai bila
    pemilik hanya butuh kodenya dikirim, tanpa memasukkan kode di sesi ini.
    """
    body = body_text(page)
    print("TANTANGAN VERIFIKASI: Threads meminta verifikasi tambahan.")
    print("Cuplikan:", snippet(body))
    masked = MASKED_EMAIL_RE.search(body or "")
    if masked:
        print(f"Email tujuan (tersamar): {masked.group(0)}")
    press_request_code_once(page)
    print("BERHENTI: kode diminta ke email pemilik; masukkan kode itu dengan "
          "run berkode (--code-stdin). Sesi TIDAK disimpan.")
    return 1


def wait_for_code_or_command(page, timeout: float = 900):
    """Tunggu kode 6 digit dari stdin, atau perintah pencet-ulang.

    Dipakai mode --request-code-wait: browser TETAP TERBUKA di halaman
    tantangan sementara proses menunggu. Perintah yang dikenali (satu
    baris, huruf besar/kecil tidak berpengaruh):
      - 6 digit (mis. 613268): kembalikan ('code', kode). Kode tidak
        pernah dicetak.
      - press / lagi / kirim / minta / pencet / resend: pencet tombol
        'get a code' SEKALI di sesi yang sama (TANPA login ulang),
        laporkan hasilnya, lalu lanjut menunggu.
      - batal / quit / exit: kembalikan ('quit', None).
    Baris lain diabaikan. Timeout / EOF -> ('timeout', None).
    """
    import select

    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        r, _, _ = select.select([sys.stdin], [], [], 5)
        if not r:
            continue
        try:
            chunk = os.read(0, 64)
        except Exception:
            return ("timeout", None)
        if not chunk:
            return ("timeout", None)
        buf += chunk
        while b"\n" in buf:
            line, _, rest = buf.partition(b"\n")
            buf = rest
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            if re.fullmatch(r"\d{6}", text):
                return ("code", text)
            low = text.lower()
            if low in ("press", "lagi", "kirim", "minta", "pencet", "resend",
                       "get a code", "minta kode", "kirim ulang"):
                print("-- perintah pencet-ulang diterima: pencet 'get a code' "
                      "lagi di sesi yang sama (tanpa login ulang)...")
                ok = press_request_code_once(page)
                print("-- pencet-ulang " +
                      ("BERHASIL." if ok else "GAGAL.") +
                      " Menunggu kode / perintah berikutnya...")
                continue
            if low in ("batal", "quit", "exit", "stop"):
                print("-- perintah batal diterima.")
                return ("quit", None)
            print(f"-- baris stdin '{text}' bukan kode 6 digit / perintah "
                  "yang dikenal, diabaikan (menunggu kode, 'press', atau 'batal')...")
    return ("timeout", None)


def find_code_input(page):
    """Cari kolom input kode verifikasi; kembalikan locator atau None.

    Coba selector spesifik dulu, lalu fallback JS: tandai input terlihat
    yang paling cocok di halaman tantangan (di halaman itu satu-satunya
    input adalah kolom kode). Fallback diperlukan karena kolom kode
    Threads tidak selalu punya placeholder/aria-label/autocomplete yang
    dikenali (terbukti live 16 Nov 22:46 WIB: semua selector spesifik
    gagal padahal halaman tantangan tampil).
    """
    selectors = [
        'input[placeholder*="code" i]',
        'input[aria-label*="code" i]',
        'input[name*="code" i]',
        'input[placeholder*="kode" i]',
        'input[aria-label*="kode" i]',
        'input[placeholder*="otp" i]',
        'input[aria-label*="otp" i]',
        'input[name*="otp" i]',
        'input[autocomplete="one-time-code"]',
        'input[autocomplete*="code" i]',
        'input[inputmode="numeric"]',
        'input[type="tel"]',
        'input[maxlength="1"]',
        'input[maxlength="6"]',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                return loc
        except Exception:
            continue
    # Fallback JS: pilih input terlihat terbaik, tandai dengan atribut.
    try:
        marked = page.evaluate("""() => {
          const inputs = [...document.querySelectorAll('input')].filter(el => {
            const t = (el.type || '').toLowerCase();
            if (['hidden','checkbox','radio','submit','button','file'].includes(t)) return false;
            const r = el.getBoundingClientRect();
            if (!r.width || !r.height) return false;
            const cs = getComputedStyle(el);
            return cs.visibility !== 'hidden' && cs.display !== 'none';
          });
          if (!inputs.length) return 0;
          const score = el => {
            const hay = ((el.placeholder||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.name||'')+' '+(el.autocomplete||'')+' '+(el.inputMode||'')+' '+(el.id||'')).toLowerCase();
            return /code|kode|otp|verif|confirm/.test(hay) ? 2 : 0;
          };
          inputs.sort((a,b) => score(b) - score(a));
          inputs[0].setAttribute('data-rusdi-code-input', '1');
          return inputs.length;
        }""")
        if marked:
            loc = page.locator('[data-rusdi-code-input="1"]').first
            if loc.is_visible(timeout=3000):
                return loc
    except Exception:
        pass
    return None


def enter_verification_code(page, code: str) -> bool:
    """Masukkan kode ke kolom tantangan lalu submit. Kembalikan True bila
    form terkirim (bukan berarti kode benar). Kode TIDAK PERNAH dicetak."""
    inp = None
    for _ in range(3):
        inp = find_code_input(page)
        if inp is not None:
            break
        page.wait_for_timeout(3000)
    if inp is None:
        return False
    try:
        boxes = page.locator('input[maxlength="1"]')
        n = boxes.count()
    except Exception:
        n = 0
    try:
        if n and n >= len(code):
            # Kotak 6 digit terpisah: isi satu per satu.
            for i, ch in enumerate(code):
                box = boxes.nth(i)
                if not safe_click(page, box):
                    return False
                box.press_sequentially(ch, delay=random.randint(50, 120))
        else:
            human_type(inp, code)
    except Exception:
        return False
    page.wait_for_timeout(1000)
    try:
        inp.press("Enter")
    except Exception:
        pass
    page.wait_for_timeout(4000)
    if quick_logged_in(page):
        return True
    for label in ("Verify", "Continue", "Submit", "Verifikasi", "Lanjutkan"):
        try:
            btn = page.get_by_role("button", name=label, exact=True).first
            if btn.is_visible(timeout=1500):
                safe_click(page, btn)
                page.wait_for_timeout(4000)
                return True
        except Exception:
            continue
    return True


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


def do_login(username: str, request_code: bool = False, code_stdin: bool = False,
             request_code_wait: bool = False) -> int:
    """Login penuh dengan username + password (password ditanya via getpass).

    request_code: bila tantangan muncul, klik tombol "get a code" berulang
      sampai timer cooldown muncul, lalu keluar kode 1 tanpa menyimpan sesi.
    code_stdin: baca 6 digit dari stdin, masukkan ke form tantangan bila
      muncul, lalu lanjut ke jalur simpan-sesi normal. Kode tidak pernah
      dicetak/dilog/ditulis ke file.
    request_code_wait: SATU SESI penuh tanpa reload (aturan Amad 16 Nov
      22:30 WIB): login -> tantangan muncul -> pencet get-a-code 1x ->
      TUNGGU 6 digit dari stdin (browser tetap terbuka di halaman
      tantangan, maks 15 menit) -> masukkan kode di sesi yang sama ->
      lanjut ke jalur simpan-sesi normal. TIDAK ADA login ulang. Selama
      menunggu, stdin juga menerima perintah 'press' (pencet get-a-code
      lagi 1x di sesi yang sama) dan 'batal' (berhenti).
    """
    from cloakbrowser import launch

    code = None
    if code_stdin:
        # Baca kode SEBELUM apa pun memakai stdin. Password TIDAK dibaca dari
        # stdin di mesin ini (ada di .env), jadi tidak ada perebutan.
        code = (sys.stdin.readline() or "").strip()
        if not re.fullmatch(r"\d{6}", code or ""):
            return fail("kode dari stdin harus tepat 6 digit, batal.")
    try:
        password = os.environ.get("THREADS_PASSWORD") or getpass.getpass("Password Threads/Instagram: ")
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
        code_attempted = False
        code_cooldown_until = 0.0
        while time.time() < deadline:
            body = body_text(page)
            cls = classify_body(body)
            if cls == "challenge":
                if code_stdin and code and not code_attempted:
                    code_attempted = True
                    print("-- tantangan muncul, memasukkan kode dari stdin...")
                    if enter_verification_code(page, code):
                        # Hapus kode dari memori sesegera mungkin setelah dipakai.
                        code = "x" * 6
                        del code
                        code = None
                        code_cooldown_until = time.time() + 15
                        deadline = max(deadline, time.time() + 60)
                        time.sleep(5)
                        continue
                    print("GAGAL: kolom kode tidak ditemukan di halaman tantangan.")
                    print("Cuplikan:", snippet(body))
                    return 1
                if time.time() < code_cooldown_until:
                    # Baru saja memasukkan kode; beri halaman waktu beralih
                    # sebelum menyimpulkan tantangan masih ada.
                    time.sleep(3)
                    continue
                if request_code:
                    return request_verification_code(page)
                if request_code_wait and not code_attempted:
                    code_attempted = True
                    print("-- mode request-code-wait: pencet get-a-code di sesi "
                          "ini (tanpa reload)...")
                    if not press_request_code_once(page):
                        print("GAGAL: tombol tidak berhasil dipencet. Sesi "
                              "TIDAK disimpan.")
                        return 1
                    print("MENUNGGU KODE: kode sudah diminta 1x, browser TETAP "
                          "TERBUKA di halaman tantangan. Kirim 6 digit dari "
                          "email (maks 15 menit). Bila kode tak kunjung sampai, "
                          "kirim 'press' untuk pencet lagi di sesi yang sama "
                          "(tanpa login ulang), atau 'batal' untuk berhenti.")
                    kind, code = wait_for_code_or_command(page, timeout=900)
                    if kind != "code":
                        print(f"GAGAL: menunggu kode berakhir ({kind}). Sesi "
                              "TIDAK disimpan.")
                        return 1
                    print("-- memasukkan kode di sesi yang sama (tanpa login ulang)...")
                    if enter_verification_code(page, code):
                        # Hapus kode dari memori sesegera mungkin setelah dipakai.
                        code = "x" * 6
                        del code
                        code = None
                        code_cooldown_until = time.time() + 15
                        deadline = max(deadline, time.time() + 60)
                        time.sleep(5)
                        continue
                    print("GAGAL: kolom kode tidak ditemukan di halaman tantangan.")
                    print("Cuplikan:", snippet(body))
                    return 1
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
    load_env()
    ap = argparse.ArgumentParser(
        description="Login manual Threads (username + password) untuk instance ini.",
    )
    ap.add_argument("--username", default=None,
                    help="username login (default: handle di account.json)")
    ap.add_argument("--probe", action="store_true",
                    help="cek halaman login saja, tanpa login dan tanpa password")
    ap.add_argument("--request-code", action="store_true",
                    help="bila tantangan muncul, klik tombol 'get a code' berulang sampai "
                         "timer cooldown muncul, lalu keluar kode 1 tanpa menyimpan sesi")
    ap.add_argument("--code-stdin", action="store_true",
                    help="baca 6 digit kode verifikasi dari stdin dan masukkan ke "
                         "form tantangan bila muncul (kode tidak pernah dicetak/dilog)")
    ap.add_argument("--request-code-wait", action="store_true",
                    help="SATU SESI tanpa reload: login, pencet 'get a code' 1x, "
                         "lalu TUNGGU 6 digit dari stdin (maks 15 mnt) dan "
                         "masukkan di sesi yang sama, lalu simpan sesi. Selama "
                         "menunggu, kirim 'press' via stdin untuk pencet lagi "
                         "tanpa login ulang, 'batal' untuk berhenti")
    args = ap.parse_args()

    if args.probe:
        return do_probe()
    if sum((args.request_code, args.code_stdin, args.request_code_wait)) > 1:
        return fail("pilih salah satu: --request-code, --code-stdin, atau "
                    "--request-code-wait, bukan gabungan.")

    expected = account_guard.load_expected(BOT)
    if not expected:
        return fail("account.json hilang/rusak di folder ini; tidak tahu akun mana "
                    "yang harus diloginkan. Batal.")
    username = (args.username or os.environ.get("THREADS_USERNAME") or expected).strip().lstrip("@")
    if not username:
        return fail("username kosong, batal.")
    print(f"-- login sebagai {username} (akun instance: @{expected})")
    if username.lower() != expected.lower():
        print("-- PERINGATAN: username login berbeda dari handle instance. "
              "Sesi tetap diverifikasi terhadap account.json; bila tidak MATCH, "
              "sesi TIDAK disimpan.")
    return do_login(username, request_code=args.request_code,
                    code_stdin=args.code_stdin,
                    request_code_wait=args.request_code_wait)


if __name__ == "__main__":
    sys.exit(main())
