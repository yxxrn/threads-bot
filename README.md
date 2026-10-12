# threads-bot

Bot auto-reply Threads untuk promosi Blooply. Bot membalas postingan orang lain
(di Threads) dengan komentar yang relevan + satu baris promo Blooply di akhir,
dalam bahasa yang sama dengan penulis postingan (Indonesia/Inggris).

## Cara kerja

- `poster_daemon.py` — daemon yang jalan terus. Mengambil antrean balasan dari
  `comments.json` + `retry_queue.json`, posting satu per satu dengan jeda acak
  2–3 menit, sampai `session.json` kedaluwarsa. Satu lock file
  (`.auto_comment.lock`) memastikan tidak ada dua poster jalan bersamaan.
- `auto_comment.py` — logika posting (buka postingan → expand composer →
  lampirkan `promo.jpg` → ketik → Post → verifikasi).
- Antrean (`comments.json`) diisi oleh proses terpisah (agent/siklus refill) —
  daemon ini hanya mem-posting, tidak mencari postingan.
- `login.py` — login interaktif satu kali ke Threads, menyimpan sesi ke
  `state.json` (chmod 600).
- `check_login.py` — cek apakah sesi di `state.json` masih valid.

Browser memakai [CloakBrowser](https://github.com/CloakHQ/CloakBrowser)
(Chromium anti-deteksi, fingerprint Windows) lewat API Playwright.

## Setup di mesin baru

Butuh Python 3.11.

```bash
git clone <repo-ini> threads-bot
cd threads-bot
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt
```

(Chromium CloakBrowser diunduh otomatis saat pertama dipakai, ke `~/.cloakbrowser`.)

## Menjalankan

**1. Login (sekali saja per sesi):**

```bash
./venv/bin/python login.py
```

Masukkan username + password Threads/Instagram di terminal (password
disembunyikan, tidak dikirim ke mana-mana). Tangani 2FA/captcha sesuai
petunjuk di layar. Sesi tersimpan di `state.json`.

**2. Verifikasi sesi:**

```bash
./venv/bin/python check_login.py
```

**3. Buat `session.json` (jendela jalan bot):**

```bash
./venv/bin/python -c "
import json, datetime
json.dump({
  'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'duration_hours': 24
}, open('session.json', 'w'), indent=1)"
```

Isi `duration_hours` dengan `null` untuk jalan tanpa batas waktu (berhenti
manual dengan Ctrl+C).

**4. Isi antrean** — tulis `comments.json` dengan format:

```json
[
  {"url": "https://www.threads.com/@user/post/xxxx", "author": "user",
   "lang": "id", "comment": "komentar yang relevan...\n\n...promo Blooply"}
]
```

**5. Jalankan daemon:**

```bash
nohup ./venv/bin/python poster_daemon.py >> daemon.log 2>&1 &
```

Log jalan di `daemon.log`. Kalau antrean kosong, daemon menunggu 45 detik
lalu cek lagi (menunggu siklus refill).

## File-file

| File | Fungsi |
|---|---|
| `poster_daemon.py` | Daemon posting kontinu |
| `auto_comment.py` | Logika buka/ketik/posting/verifikasi |
| `login.py` | Login interaktif → `state.json` |
| `check_login.py` | Verifikasi sesi |
| `promo.jpg` | Gambar promo yang dilampirkan tiap balasan |
| `requirements.txt` | Dependensi Python |

File lokal yang dibuat saat jalan (`state.json`, `session.json`,
`comments.json`, `retry_queue.json`, `shots/`, log) semuanya di-`.gitignore` —
jangan di-commit.
