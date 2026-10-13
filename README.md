# threads-bot

Dua tool otomasi Threads + X untuk promosi [Blooply](https://app.blooply.id)
(app PC pemotong video panjang jadi klip 9:16). Semuanya berbasis browser
(Playwright + CloakBrowser), tanpa API resmi Meta/X, dan tanpa layanan cloud:
semua jalan lokal di VPS/PC sendiri.

| Folder | Fungsi | Butuh apa |
|---|---|---|
| [`autopost/`](autopost/) | Posting ke **akun sendiri**: promo Blooply (Threads/X/FB), muse.ai referral, chain thread, carousel media | Python + browser |
| [`reply-bot/`](reply-bot/) | **Bot reply**: balas postingan orang lain dengan komentar relevan + promo halus, plus pipeline scrape/refill antrean | Python + browser (+ opsional penjadwal) |
| [`docs/`](docs/) | Dokumentasi arsitektur, setup per-mesin, integrasi penjadwal (Hermes), troubleshooting | — |

## Kenapa dua folder?

- **`autopost/`** — pola kerjanya *one-shot*: script dipanggil (manual atau
  cron), post, selesai. Tidak ada state antrean. Contoh pemakaian: cron
  `blooply-promo` tiap 4 jam.
- **`reply-bot/`** — pola kerjanya *kontinu*: ada antrean (`comments.json`),
  daemon yang posting terus, dan pipeline refill yang terus mencari post baru
  untuk dibalas. Butuh "otak" untuk menulis komentar (agent LLM atau script
  sendiri — lihat [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)).

## Mulai cepat

```bash
git clone https://github.com/yxxrn/threads-bot
cd threads-bot

# Pilih salah satu (atau dua-duanya):

# A. Autopost (posting ke akun sendiri)
cd autopost
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# login → lihat autopost/README (bagian Session)
.venv/bin/python post.py "hello world"

# B. Reply bot (balas postingan orang)
cd ../reply-bot
python3 -m venv venv && ./venv/bin/pip install cloakbrowser==0.5.11 playwright==1.63.0
# login → lihat reply-bot/README (bagian Setup)
```

> **Penting:** jangan pernah commit file `storage_state*.json`, `state.json`,
> `cookies*.txt`, atau file `.env`. Semua itu berisi session hidup akun.
> Setiap folder punya `.gitignore` sendiri — jangan diubah.

## Dokumentasi

| Dokumen | Isi |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arsitektur kedua sistem, alur data, file-file state, cara kerja tiap komponen |
| [`docs/SETUP.md`](docs/SETUP.md) | Setup dari nol di mesin baru: dependensi, login, konfigurasi |
| [`docs/SCHEDULING.md`](docs/SCHEDULING.md) | Cara menjadwalkan: crontab murni, systemd timer, atau Hermes cron (lengkap dengan perintah) |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Masalah umum + solusinya (session mati, selector berubah, dsb) |
| [`docs/PORTING.md`](docs/PORTING.md) | Pindah ke agent/mesin lain tanpa masalah (checklist portabilitas) |
| [`autopost/README.md`](autopost/README.md) | Detail script autopost + gotcha chain/media |
| [`reply-bot/README.md`](reply-bot/README.md) | Detail bot reply + pipeline refill |
| [`reply-bot/WATCHDOG.md`](reply-bot/WATCHDOG.md) | Playbook watchdog (yang dijalankan agent saat ada alarm) |

## Disclaimer

Otomasi akun pribadi. Patuhi ToS platform yang dipakai (Meta, X, Telegram).
Pakai atas risiko sendiri — akun bisa kena limit/suspend kalau pola postingnya
terdeteksi spam. Semua kredensial/session adalah tanggung jawab pemilik.
